"""段階0の逆算を端末で見る。ロジックは app/derive.py にあり、ここは表示だけ。"""
from __future__ import annotations
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.derive import derive
from app.dsl import Month, Nurse, ShiftKind, Ward

KINDS = [
    ShiftKind(id="日", name="日勤",   hours=8.0, night_hours=0.0),
    ShiftKind(id="準", name="準夜勤", hours=8.5, night_hours=8.5, crosses_midnight=True),
    ShiftKind(id="深", name="深夜勤", hours=8.5, night_hours=7.5, crosses_midnight=True),
    ShiftKind(id="休", name="公休",   hours=0.0, is_off=True),
    ShiftKind(id="研", name="研修",   hours=8.0, counts_as_staff=False),
]
WARD = json.load(open("seed/ward.json"))
OCT = json.load(open("seed/october.json"))
W = Ward(id="w1", name="3階東病棟", shift_kinds=KINDS,
         nurses=[Nurse(**n) for n in WARD["nurses"]],
         night_band_start=16, night_average_cap=72.0)
M = Month(month=OCT["month"], days=OCT["days"],
          first_weekday=OCT["first_weekday"], current=OCT["cells"])

cands = derive(W, M)
print(f"=== {M.month} の表（{len(W.nurses)}人 / {M.days}日）から {len(cands)} 問\n")
for i, c in enumerate(cands, 1):
    print(f"{i}. [{c.kind:8}] {c.question}")
    print(f"   {c.evidence}")
    for ch in c.choices:
        mark = "—" if ch.rule is None else "→"
        term = f"（{ch.expires_on} まで）" if ch.expires_on else ""
        print(f"     {mark} {ch.label}{term}" + (f"  … {ch.rule.label} [{ch.rule.strength}]" if ch.rule else ""))
    print()
