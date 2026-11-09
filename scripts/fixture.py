"""デモ用の過去月を作る。

反復検出は編集ログの上にしか見えず、履歴はこの製品を使い始めてからしか貯まらない。
そこで「この病棟は8月から使っている」状態を作る。

**何を作り物にしているかを明示する。**
  本物 — 各月の提案は、その月のルールで実際に CP-SAT が解いた出力
  本物 — 各月の編集は、その提案に対する実際の差分（from はソルバが置いたもの）
  作り物 — 師長が毎月そこを直す、という振る舞いの脚本
"""
from __future__ import annotations

import json
import random
import sys
import urllib.request as U
from calendar import monthrange
from datetime import date

B = "http://localhost:8077"
WID = "w1"
TARGET_NURSE = "2"       # 佐藤 恵
TARGET_WEEKDAY = 5       # 金
TARGET_KIND = "深"
HISTORY = ["2026-08", "2026-09", "2026-10"]
IMPORTED = "2026-07"     # 段階0で取り込む手作りの表
NOISE_PER_MONTH = 7
WD = ["日", "月", "火", "水", "木", "金", "土"]


def call(path, body=None, method=None):
    r = U.Request(B + path, method=method or ("POST" if body is not None else "GET"),
                  data=None if body is None else json.dumps(body).encode(),
                  headers={"Content-Type": "application/json"})
    with U.urlopen(r) as f:
        return json.load(f)


def cal(m: str) -> tuple[int, int]:
    y, mo = map(int, m.split("-"))
    return monthrange(y, mo)[1], (date(y, mo, 1).weekday() + 1) % 7   # 0=日


def main() -> int:
    rng = random.Random(20261109)
    ward = json.load(open("seed/ward.json"))
    cells = json.load(open("seed/october.json"))["cells"]

    print("── 段階0  病棟と、取り込んだ手作りの表")
    w = call("/api/ward", ward)
    print(f"   法令由来 — {', '.join(w['law_rules'])}")
    d, fw = cal(IMPORTED)
    call(f"/api/ward/{WID}/import",
         {"month": IMPORTED, "days": d, "first_weekday": fw, "cells": cells})
    cands = call(f"/api/ward/{WID}/candidates?month={IMPORTED}")["candidates"]
    made = 0
    for c in cands:
        ch = c["choices"][0]
        if ch["rule"]:
            call(f"/api/ward/{WID}/rules", {"rule": ch["rule"], "expires_on": ch.get("expires_on")})
            made += 1
    print(f"   {IMPORTED} の表から {len(cands)}問 → {made}本")

    name = next(n["name"] for n in ward["nurses"] if n["id"] == TARGET_NURSE)
    print(f"\n── 8月から使っている状態を作る（脚本: {name} の金曜の{TARGET_KIND}を毎月外す）")

    for m in HISTORY:
        days, fw = cal(m)
        # この病棟の構造だと、その人がその曜日に置かれる。それを再現するための一時ルール
        tmp = {"type": "request", "id": "fx_tmp", "label": f"{name} を金曜の{TARGET_KIND}に置く",
               "people": {"ids": [TARGET_NURSE]}, "days": {"weekdays": [TARGET_WEEKDAY]},
               "shifts": {"ids": [TARGET_KIND]}, "want": True, "strength": "できれば",
               "origin": {"kind": "手入力", "evidence": "fixture"}}
        call(f"/api/ward/{WID}/rules", {"rule": tmp})
        r = call(f"/api/ward/{WID}/month/{m}/solve",
                 {"stage": "day", "days": days, "first_weekday": fw})
        call(f"/api/ward/{WID}/rules/fx_tmp", None, "DELETE")
        if r["status"] not in ("OPTIMAL", "FEASIBLE"):
            print(f"   {m} 解けなかった ({r['status']})")
            return 1

        prop = r["proposal"]
        fri = [x for x in range(1, days + 1) if (fw + x - 1) % 7 == TARGET_WEEKDAY]
        hit = next((x for x in fri if prop[TARGET_NURSE][x - 1] == TARGET_KIND), None)
        if hit is None:
            print(f"   {m} 脚本どおりに置けなかった")
            return 1
        e = call(f"/api/ward/{WID}/month/{m}/edits",
                 {"nurse_id": TARGET_NURSE, "day": hit, "to": "休"})

        # 雑音。これが無いと閾値が低く出て、2ヶ月で発火してしまう
        noise = 0
        others = [n["id"] for n in ward["nurses"] if n["id"] != TARGET_NURSE]
        while noise < NOISE_PER_MONTH:
            nid, day = rng.choice(others), rng.randrange(1, days + 1)
            cur = prop[nid][day - 1]
            if not cur or cur == "休":
                continue
            call(f"/api/ward/{WID}/month/{m}/edits", {"nurse_id": nid, "day": day, "to": "休"})
            noise += 1
        print(f"   {m}  {r['status']} {r['wall_ms']:>4}ms   "
              f"{hit}日({WD[TARGET_WEEKDAY]}) {e['edit']['from']}→{e['edit']['to']}  ＋雑音{noise}件")

    print("\n── 11月を作る")
    days, fw = cal("2026-11")
    r = call(f"/api/ward/{WID}/month/2026-11/solve",
             {"stage": "night", "days": days, "first_weekday": fw})
    print(f"   夜勤 {r['status']} {r['wall_ms']}ms  月平均 {r['night_average']}h")

    b = call(f"/api/ward/{WID}/month/2026-11")
    print(f"\n── 反復検出   鍵の数 K={b['n_keys']}")
    for rp in b["repeats"][:4]:
        print(f"   {'★発火' if rp['fired'] else '  沈黙'}  {rp['streak']}/{rp['threshold']}ヶ月  "
              f"{rp['evidence']}")
        for c in rp["candidates"]:
            print(f"        {c['scope']:6} {c['rule']['label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
