# 開発・検証・デプロイ

## 動かす

```bash
# バックエンド（GCP不要。REPO 未指定なら data/ にJSONで保存）
uv venv --python 3.12 && uv pip install -e .
uvicorn app.main:app --port 8077

# フロント（開発）— /api は 8077 にプロキシされる
cd frontend && npm install && npm run dev

# フロント（本番ビルド）— 出力は ../web/ で、FastAPI がそこを配信する
cd frontend && npm run build
```

`web/` はコミットしない。Dockerfile が node ステージで作り直す。

## スクリプト

| | |
|---|---|
| `python scripts/stage0.py` | 過去の表を数えてルール候補を出す（表示だけ） |
| `python scripts/e2e.py` | 段階0→1→2→3→4をHTTPで1本通す |
| `python scripts/fixture.py` | デモ用。8月から使っている状態を作り、反復検出を発火させる |
| `python scripts/bench_repo.py` | 保存層の操作別レイテンシ。エミュレータと本物を同じ尺で測る |
| `python scripts/verify_firestore.py` | 追記専用・並び・サーバ時刻・回帰の前提を実際に確かめる |
| `python scripts/smoke_vertex.py` | LLM経路の疎通。`route` が `stub(...)` なら届いていない |
| `PROJECT=<id> ./scripts/deploy.sh` | Cloud Run へ出す |

### デモの作り方

```bash
rm -rf data && uvicorn app.main:app --port 8077 &
python scripts/fixture.py               # → /#/roster を開くと反復検出が出ている
```

`fixture.py` が作り物にしているのは**師長の振る舞いの脚本だけ**。各月の提案はその月のルールで実際に CP-SAT が解いた出力で、編集はその提案に対する実際の差分。

## Firestore

### 本物（2026-11-09 実行済み）

```bash
export GOOGLE_CLOUD_PROJECT=<id> REPO=firestore
gcloud auth application-default login
uvicorn app.main:app --port 8077 &
python scripts/verify_firestore.py      # 性質5本
python scripts/bench_repo.py            # レイテンシ
```

【実測】**課金アカウントが無くても Firestore は作れる**（`freeTier: true`）。`gcloud firestore databases create --location=asia-northeast1 --type=firestore-native`。security rules は `firebase deploy --only firestore:rules --project <id>`。

### エミュレータ（GCPプロジェクトが無いとき）

```bash
brew install openjdk                                   # エミュレータはJava
npx firebase-tools emulators:start --only firestore --project demo-roster

export FIRESTORE_EMULATOR_HOST=localhost:8181
export GOOGLE_CLOUD_PROJECT=demo-roster REPO=firestore
uvicorn app.main:app --port 8077 &
python scripts/fixture.py        # /api/health が repo:FirestoreRepo を返す
```

Python の Firestore クライアントは `FIRESTORE_EMULATOR_HOST` を見て、資格情報なしで繋ぐ。

### 本物とエミュレータの差

【実測】**差はレイテンシだけ。** 性質は5本とも本物で成立し、インデックスの追加は不要（`order_by("at")` が複合インデックスなしで通る）。クォータは `fixture.py` 1回が書き込み40件台なので触らない。

| | エミュレータ | 本物 |
|---|---|---|
| 1doc書き | 1.4〜2.4ms | **37.6〜52.4ms** |
| 1doc読み | 1.1〜1.4ms | **39.9〜41.4ms** |
| コレクション走査・`order_by` | 3.2〜3.5ms | **41.0〜43.0ms** |

【推論】倍率（12〜37倍）ではなく絶対差を読む。どの操作も一律 +35〜50ms で、往復1回ぶんの固定費。**Cloud Run を Firestore と同じ `asia-northeast1` に置くこと。**

## Vertex AI

```bash
GOOGLE_CLOUD_PROJECT=<id> GOOGLE_GENAI_USE_VERTEXAI=1 python scripts/smoke_vertex.py
```

`route` が `stub(...)` なら LLM に届いていない。括弧の中が原因。

| 括弧の中 | 原因 |
|---|---|
| `KeyError` | 環境変数が無い |
| `PermissionDenied` | サービスアカウントに `roles/aiplatform.user` が無い |
| `NotFound` | モデル名かリージョン（`GEMINI_MODEL` / `GOOGLE_CLOUD_LOCATION`） |
| `ClientError` + `BILLING_DISABLED` | プロジェクトに有効な課金アカウントが無い |

**APIキーは作らない。** Cloud Run のサービスアカウントで ADC 認証する。`_stub()` は資格情報が無いときに開発を止めないための代替で、本番経路ではない。

【実測】Gemini の構造化出力に渡すスキーマは、SDKのPydantic→Schema変換で `X | None` が `anyOf` でなく **`nullable: true`** になり、`$ref` `allOf` `oneOf` が出ない＝受け付ける形であることをオフラインで確認済み。

## デプロイ

```bash
PROJECT=<id> ./scripts/deploy.sh
firebase deploy --only firestore:rules --project <id>   # クライアント経路を全部閉じる
```

**ローカルで `docker build` して push しない。** Apple Silicon で arm イメージになり Cloud Run で落ちる。`--source` を使うと Cloud Build が amd64 で焼く。

【実測】検証目的で `docker build --platform linux/amd64` して起動したところ、イメージ155MB、`seed/` と `web/` が入り、段階0の取り込みと求解が通った（2026-11-09）。

- **`seed/` を `COPY` し忘れると `/api/ward/{wid}/import/sample` が落ちる。** 段階0の入口なのでデモが止まる
- `.dockerignore` が `web` と `scripts` を外しているのは意図通り（`web` は node ステージで作る）
- 11/10 19:00以降は `--min-instances=1` に上げる（11/14までで $1前後）
