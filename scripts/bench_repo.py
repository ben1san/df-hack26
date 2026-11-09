"""FirestoreRepo の操作別レイテンシ。エミュレータと本物を同じ尺で測る。

    # 本物
    GOOGLE_CLOUD_PROJECT=<id> python scripts/bench_repo.py
    # エミュレータ
    FIRESTORE_EMULATOR_HOST=localhost:8181 GOOGLE_CLOUD_PROJECT=demo-roster \
      python scripts/bench_repo.py

書き込み先は ward id = bench_* の使い捨て。w1 には触らない。
"""
from __future__ import annotations

import os
import pathlib
import statistics as st
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.dsl import Edit, Month, Rule, Ward          # noqa: E402
from app.repo import FirestoreRepo, now              # noqa: E402

N = int(os.environ.get("N", "20"))
WID = f"bench_{uuid.uuid4().hex[:6]}"
MO = "2026-11"
EMU = os.environ.get("FIRESTORE_EMULATOR_HOST")
import json                                          # noqa: E402

root = pathlib.Path(__file__).resolve().parents[1]
ward = Ward(**json.load(open(root / "seed/ward.json")))
ward.id = WID
month = Month(**json.load(open(root / "data/w1/months/2026-11.json")))
rules = __import__("app.repo", fromlist=["RA"]).RA.validate_python(
    json.load(open(root / "data/w1/rules.json")))

r = FirestoreRepo()


def timed(label: str, fn, n: int = N) -> tuple[str, list[float]]:
    xs = []
    for i in range(n):
        t = time.perf_counter()
        fn(i)
        xs.append((time.perf_counter() - t) * 1000)
    return label, xs


def mk_edit(i: int) -> Edit:
    return Edit(id=f"e{i}_{uuid.uuid4().hex[:8]}", at=now(), nurse_id="2",
                day=7, **{"from": "深"}, to="休", by="師長")


ops = [
    timed("put_ward    (1doc write)", lambda i: r.put_ward(ward)),
    timed("get_ward    (1doc read)", lambda i: r.get_ward(WID)),
    timed("put_rule    (1doc write)", lambda i: r.put_rule(WID, rules[i % len(rules)])),
    timed("get_rules   (collection stream)", lambda i: r.get_rules(WID)),
    timed("put_month   (1doc write)", lambda i: r.put_month(WID, month)),
    timed("get_month   (1doc read)", lambda i: r.get_month(WID, MO)),
    timed("append_edit (create+SERVER_TS)", lambda i: r.append_edit(WID, MO, mk_edit(i))),
    timed("get_edits   (order_by at)", lambda i: r.get_edits(WID, MO)),
    timed("months      (collection ids)", lambda i: r.months(WID)),
]

print(f"{'操作':34} {'中位':>8} {'最小':>8} {'p95':>8}   n={N}  "
      f"{'エミュレータ' if EMU else '本物'} {EMU or os.environ.get('GOOGLE_CLOUD_PROJECT')}")
print("-" * 76)
for label, xs in ops:
    xs_s = sorted(xs)
    p95 = xs_s[min(len(xs_s) - 1, int(len(xs_s) * 0.95))]
    print(f"{label:34} {st.median(xs):7.1f}ms {min(xs):7.1f}ms {p95:7.1f}ms")

print(f"\nward id {WID}（使い捨て）")
