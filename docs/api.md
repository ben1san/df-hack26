# API と保存の形

**表を上書きするエンドポイントが無い。** 表は状態ではなく（提案 ＋ 編集ログ）の射影で、`PUT /roster` を1本でも許すと差分が消え、反復検出が丸ごと成立しなくなる。この1点が他の設計を全部決めている。

## エンドポイント

`app/main.py`。番号は同ファイルの区切りコメントに対応する。

| # | メソッド・パス | 何をするか |
|---|---|---|
| 1 | `GET /api/ward/{wid}/month/{mo}` | 画面が1回で必要なもの全部。病棟・月・現状・ルール・編集ログ・反復検出・期限切れ。**ブラウザはFirestoreを直接触らない** |
| 2 | `POST /api/ward/{wid}/month/{mo}/solve` | CP-SATで解く。`stage=night` → `stage=day` の二段階。**LLMは関与しない** |
| 3 | `POST /api/ward/{wid}/month/{mo}/edits` | 1セル1件、追記のみ。何も聞かない |
| 4 | `POST /api/ward/{wid}/rules`<br>`PATCH /api/ward/{wid}/rules/{rid}`<br>`DELETE /api/ward/{wid}/rules/{rid}` | ルールを増やす／止める・延ばす／消す。**法令由来（`locked`）は消せず、止めるには理由の記録が要る** |
| 5 | `POST /api/ward/{wid}/translate` | 自然言語1文 → 制約候補1本。**LLMが出る唯一の経路**。範囲（この人だけ／この曜日全体／全員）は3通り返すだけで、選ぶのは師長 |
| 6 | `POST /api/ward` | 病棟登録。このとき法令由来ルールを投入する |
| 段階0 | `POST /api/ward/{wid}/import`<br>`POST /api/ward/{wid}/import/sample`<br>`GET /api/ward/{wid}/candidates` | 過去の表を取り込み、数えてルール候補を返す。**作りはしない** |
| — | `GET /api/health` | `repo` にどの保存実装が載っているかを返す |

対話的な仕様は `/api/docs`（FastAPIの自動生成）。

### 2つの不変条件

1. **`solve` は `month.proposal` に書き、`current` には書かない。** 現状は `_fold(proposal, edits)` でその場で畳み込む
2. **取り込んだ過去の表だけは `proposal` を持たない。** 師長が手で作ったものでソルバの出力ではないため。このとき「棄却」は定義されない

## Firestore のコレクション構成

`app/repo.py` の `FirestoreRepo`。

```text
wards/{wid}                                  … Ward（勤務区分の語彙・名簿・夜勤時間帯・72時間の上限）
wards/{wid}/rules/{rid}                      … Rule（6型のどれか。origin に来歴）
wards/{wid}/months/{mo}                      … Month（proposal / current / rules_snapshot / solved_at）
wards/{wid}/months/{mo}/edits/{eid}          … Edit（from / to / at / server_at）追記専用
```

| 置き方 | なぜ |
|---|---|
| `edits` は `create()` のみ | 同じIDの2回目は `AlreadyExists`。**上書きの経路をコードに持たせない** |
| `edits.server_at` にサーバ側タイムスタンプ | クライアント時刻を信用しない。並びは `order_by("at")`（複合インデックス不要） |
| `months/{mo}.rules_snapshot` | 解いた時点のルールIDを残す。**後から作れない**ので回帰の前提になる |
| security rules は deny all | ブラウザはFirestoreを直接触らない。触るのは Cloud Run のプロセスだけで、認証はサービスアカウントのADC。**APIキーが1本も存在しない** |

## 保存実装の差し替え

`REPO` 環境変数1本。`app/repo.py` の `make_repo()`。

| `REPO` | 実装 | 用途 |
|---|---|---|
| 未指定 | `JsonRepo` | ローカル開発。`data/` にJSON。GCPを一切使わない |
| `firestore` | `FirestoreRepo` | 本番、およびエミュレータ（`FIRESTORE_EMULATOR_HOST` を見る） |

【実測】2026-11-09、本物の Firestore（`asia-northeast1`）で全経路が通り、**アプリが返す値は `JsonRepo` と完全に一致した**（ルール10本・反復検出8件・鍵の数 K=308・棄却0件）。差はレイテンシだけで、1操作あたり一律 +35〜50ms。再現は `scripts/bench_repo.py` と `scripts/verify_firestore.py`。

【推論】この固定費は往復1回ぶんであって操作の重さではないので、効く対策は「1リクエストあたりの往復回数を減らす」だけ。エンドポイント1がまとめて返す形にしているのはそのため。**Cloud Run を Firestore と同じ `asia-northeast1` に置くことが前提条件。**
