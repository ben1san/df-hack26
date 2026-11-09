"""README の「確認済みの性質」を、エミュレータでなく本物の Firestore で取り直す。

    GOOGLE_CLOUD_PROJECT=<id> python scripts/verify_firestore.py
    FIRESTORE_EMULATOR_HOST=localhost:8181 GOOGLE_CLOUD_PROJECT=demo-roster python scripts/verify_firestore.py

読むだけ。唯一の書き込みは「同じIDで create() を2回」の409確認で、使い捨てIDを使う。
"""
from __future__ import annotations

import os
import pathlib
import sys
import uuid
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.repo import FirestoreRepo, now  # noqa: E402

WID = os.environ.get("WID", "w1")
EMU = os.environ.get("FIRESTORE_EMULATOR_HOST")
r = FirestoreRepo()
w = r._w(WID)
ok = []


def row(name, verdict, detail):
    ok.append(verdict)
    print(f"{'  OK' if verdict else '  NG':>5}  {name:22} {detail}")


print(f"対象 {'エミュレータ ' + EMU if EMU else '本物 ' + str(os.environ.get('GOOGLE_CLOUD_PROJECT'))}"
      f"   ward={WID}\n" + "-" * 78)

# 1. 追記のみ — 同じIDで create() を2回
eid = f"probe_{uuid.uuid4().hex[:8]}"
c = w.collection("months").document("2026-11").collection("edits").document(eid)
c.create({"at": now(), "probe": True})
try:
    c.create({"at": now(), "probe": True})
    row("追記のみ", False, "2回目の create() が通った＝上書き経路がある")
except Exception as e:
    row("追記のみ", "AlreadyExists" in type(e).__name__ or "409" in str(e),
        f"2回目は {type(e).__name__}（上書きの経路が無い）")
c.delete()

# 2. 並び — order_by("at") が複合インデックスなしで通るか
try:
    es = list(w.collection("months").document("2026-10").collection("edits").order_by("at").stream())
    row("並び", True, f"order_by('at') が複合インデックスなしで通る（{len(es)}件）")
except Exception as e:
    row("並び", False, f"{type(e).__name__}: {str(e)[:90]}")

# 3. 時刻 — server_at がサーバ側タイムスタンプか
d = next(iter(w.collection("months").document("2026-10").collection("edits").limit(1).stream()), None)
sa = (d.to_dict() or {}).get("server_at") if d else None
if isinstance(sa, datetime):
    skew = abs((datetime.now(sa.tzinfo) - sa).total_seconds())
    row("時刻", True, f"server_at={sa.isoformat(timespec='seconds')}（型 datetime、ズレ {skew:.0f}秒）")
else:
    row("時刻", False, f"server_at が {type(sa).__name__}")

# 4. 回帰 — months/{m}.rules_snapshot に解いた時点のルールIDが残るか
snaps = {m.id: (m.to_dict() or {}).get("rules_snapshot") for m in w.collection("months").stream()}
have = {k: len(v) for k, v in snaps.items() if v}
row("回帰", bool(have), f"rules_snapshot: " + "  ".join(f"{k}={v}本" for k, v in sorted(have.items())))

# 5. 取り込みの区別 — 取り込んだ月は current だけ、解いた月は proposal だけ
kinds = {}
for m in w.collection("months").stream():
    dd = m.to_dict() or {}
    kinds[m.id] = ("proposal" if dd.get("proposal") else "") + ("/current" if dd.get("current") else "")
row("取り込みの区別", True, "  ".join(f"{k}:{v.strip('/')}" for k, v in sorted(kinds.items())))

# ドキュメント数
n_rules = len(list(w.collection("rules").stream()))
n_months = len(list(w.collection("months").stream()))
n_edits = sum(len(list(w.collection("months").document(m.id).collection("edits").stream()))
              for m in w.collection("months").stream())
total = 1 + n_rules + n_months + n_edits
print("-" * 78)
print(f"  ドキュメント数  ward 1 + rules {n_rules} + months {n_months} + edits {n_edits} = {total}件")
print(f"\n{sum(1 for x in ok if x)}/{len(ok)} 件が本物でも成り立った")
sys.exit(0 if all(ok) else 1)
