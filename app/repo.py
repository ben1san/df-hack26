"""保存層。1ファイルに閉じる。JSON実装とFirestore実装を差し替え可能にしておく。

代表者のクレジットが来るまでJSON実装で進められる。URLもデータ形も変わらない。
破壊的更新を持たない — 編集は append のみ。荒らされても状態は失われない。
"""
from __future__ import annotations

import json
import os
import pathlib
import uuid
from datetime import UTC, datetime
from typing import Protocol

import pydantic

from app.dsl import Edit, Month, Rule, Ward

RA = pydantic.TypeAdapter(list[Rule])


class Repo(Protocol):
    def get_ward(self, wid: str) -> Ward | None: ...
    def put_ward(self, w: Ward) -> None: ...
    def get_rules(self, wid: str) -> list[Rule]: ...
    def put_rule(self, wid: str, r: Rule) -> None: ...
    def delete_rule(self, wid: str, rid: str) -> None: ...
    def get_month(self, wid: str, mo: str) -> Month | None: ...
    def put_month(self, wid: str, m: Month) -> None: ...
    def append_edit(self, wid: str, mo: str, e: Edit) -> None: ...
    def get_edits(self, wid: str, mo: str) -> list[Edit]: ...
    def months(self, wid: str) -> list[str]: ...


class JsonRepo:
    """ローカル開発用。GCPを一切使わない。"""

    def __init__(self, root: str = "data"):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, *a) -> pathlib.Path:
        p = self.root.joinpath(*a)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load(self, p, d=None):
        return json.loads(p.read_text()) if p.exists() else d

    def _save(self, p, v):
        p.write_text(json.dumps(v, ensure_ascii=False, indent=1))

    def get_ward(self, wid):
        d = self._load(self._p(wid, "ward.json"))
        return Ward(**d) if d else None

    def put_ward(self, w):
        self._save(self._p(w.id, "ward.json"), w.model_dump(mode="json"))

    def get_rules(self, wid):
        return RA.validate_python(self._load(self._p(wid, "rules.json"), []))

    def put_rule(self, wid, r):
        p = self._p(wid, "rules.json")
        cur = self._load(p, [])
        cur = [x for x in cur if x["id"] != r.id] + [r.model_dump(mode="json")]
        self._save(p, cur)

    def delete_rule(self, wid, rid):
        p = self._p(wid, "rules.json")
        self._save(p, [x for x in self._load(p, []) if x["id"] != rid])

    def get_month(self, wid, mo):
        d = self._load(self._p(wid, "months", f"{mo}.json"))
        return Month(**d) if d else None

    def put_month(self, wid, m):
        self._save(self._p(wid, "months", f"{m.month}.json"), m.model_dump(mode="json"))

    def append_edit(self, wid, mo, e):
        p = self._p(wid, "months", f"{mo}.edits.jsonl")
        with p.open("a") as f:
            f.write(json.dumps(e.model_dump(mode="json", by_alias=True), ensure_ascii=False) + "\n")

    def get_edits(self, wid, mo):
        p = self._p(wid, "months", f"{mo}.edits.jsonl")
        if not p.exists():
            return []
        return [Edit(**json.loads(l)) for l in p.read_text().splitlines() if l.strip()]

    def months(self, wid):
        d = self.root / wid / "months"
        return sorted(f.stem for f in d.glob("*.json")) if d.exists() else []


class FirestoreRepo:
    """本番。コレクション構成は docs/api.md のとおり。

    ブラウザはFirestoreを直接触らない（security rules は deny all）。
    触るのはこのプロセスだけで、認証は Cloud Run のサービスアカウント（ADC）。APIキーは存在しない。
    """

    def __init__(self, project: str | None = None):
        from google.cloud import firestore
        self.db = firestore.Client(project=project or os.environ.get("GOOGLE_CLOUD_PROJECT"))
        self._fs = firestore

    def _w(self, wid):
        return self.db.collection("wards").document(wid)

    def get_ward(self, wid):
        d = self._w(wid).get()
        return Ward(**d.to_dict()) if d.exists else None

    def put_ward(self, w):
        self._w(w.id).set(w.model_dump(mode="json"))

    def get_rules(self, wid):
        return RA.validate_python([d.to_dict() for d in self._w(wid).collection("rules").stream()])

    def put_rule(self, wid, r):
        self._w(wid).collection("rules").document(r.id).set(r.model_dump(mode="json"))

    def delete_rule(self, wid, rid):
        self._w(wid).collection("rules").document(rid).delete()

    def get_month(self, wid, mo):
        d = self._w(wid).collection("months").document(mo).get()
        return Month(**d.to_dict()) if d.exists else None

    def put_month(self, wid, m):
        self._w(wid).collection("months").document(m.month).set(m.model_dump(mode="json"))

    def append_edit(self, wid, mo, e):
        # 追記のみ。上書きの経路を持たない
        (self._w(wid).collection("months").document(mo)
         .collection("edits").document(e.id)
         .create({**e.model_dump(mode="json", by_alias=True),
                  "server_at": self._fs.SERVER_TIMESTAMP}))

    def get_edits(self, wid, mo):
        c = self._w(wid).collection("months").document(mo).collection("edits")
        return [Edit(**{k: v for k, v in d.to_dict().items() if k != "server_at"})
                for d in c.order_by("at").stream()]

    def months(self, wid):
        return sorted(d.id for d in self._w(wid).collection("months").stream())


def make_repo() -> Repo:
    """REPO=firestore なら Firestore、既定はJSON。切り替えは環境変数1本。"""
    if os.environ.get("REPO") == "firestore":
        return FirestoreRepo()
    return JsonRepo(os.environ.get("DATA_DIR", "data"))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now() -> str:
    return datetime.now(UTC).isoformat()
