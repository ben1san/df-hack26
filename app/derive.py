"""段階0 — 取り込んだ過去の表を数えてルール候補を出す。

開放的なパターンマイニングはしない。既定の候補について成立回数を数えるだけ。

設計の肝 — **候補ごとに選択肢の形が違う。**
  成立回数が100%      → 可否の2択
  例外がある          → 境界値の選択（「5日ですか、6日ですか」）
  人に紐づく          → 期限の選択（恒久か、いつまでか）
「ルールにしますか」と一律に聞くと、師長が答えられない問いになる。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.dsl import (Count, DaySel, Month, Origin, PeopleSel, Request, Rule,
                     ShiftSel, Staffing, Succession, Ward)

QKind = Literal["yesno", "boundary", "term"]


@dataclass
class Choice:
    label: str                 # 師長が読む選択肢
    rule: Rule | None = None   # None なら「作らない」
    expires_on: str | None = None


@dataclass
class Candidate:
    id: str
    question: str              # 1画面に1問だけ出す
    evidence: str              # 数えた事実。ここに推測を混ぜない
    kind: QKind
    choices: list[Choice] = field(default_factory=list)


def _org(ev: str) -> Origin:
    return Origin(kind="段階0逆算", evidence=ev)


def derive(ward: Ward, m: Month) -> list[Candidate]:
    """過去の表1ヶ月から候補を出す。順序は師長が答えやすい順（確実なものから）。"""
    kinds = {k.id: k for k in ward.shift_kinds}
    nurses = ward.nurses
    days = list(range(1, m.days + 1))
    cell = lambda nid, d: (m.current.get(nid) or m.proposal.get(nid) or [None] * m.days)[d - 1]
    work = [k for k, v in kinds.items() if not v.is_off]
    night = [k for k, v in kinds.items() if v.night_hours > 0]
    off = next((k for k, v in kinds.items() if v.is_off), None)
    out: list[Candidate] = []

    # ---- 1 深夜勤の翌日（100%なら可否の2択）
    for nk in night:
        tot = ok = 0
        for n in nurses:
            for d in days[:-1]:
                if cell(n.id, d) == nk:
                    tot += 1
                    if off and cell(n.id, d + 1) == off:
                        ok += 1
        if tot >= 10 and ok / tot >= 0.95:
            ev = f"{m.month}の表で {ok}/{tot}"
            r = Succession(
                id=f"s_after_{nk}", label=f"{kinds[nk].name}の翌日は{kinds[off].name}" if off else "",
                pattern=[ShiftSel(ids=[nk]), ShiftSel(ids=work)], forbid=True, origin=_org(ev))
            out.append(Candidate(
                id=f"after_{nk}",
                question=f"{kinds[nk].name}の翌日は、いつも{kinds[off].name}ですか。",
                evidence=ev, kind="yesno",
                choices=[Choice("はい、決まりです", r), Choice("いいえ、たまたまです")]))

    # ---- 2 連続勤務の上限（例外があるので境界値の選択）
    runs: list[int] = []
    for n in nurses:
        r = 0
        for d in days:
            if cell(n.id, d) in work:
                r += 1
            else:
                if r:
                    runs.append(r)
                r = 0
        if r:
            runs.append(r)
    if runs:
        mx = max(runs)
        common = max(set(runs), key=lambda x: (sum(1 for y in runs if y <= x), -x))
        lo = min(x for x in (5, common, mx) if x >= 3)
        hi = mx
        ev = (f"{m.month}の表で {sum(1 for x in runs if x <= lo)}/{len(runs)}本が{lo}日以内。"
              f"{hi}日が{sum(1 for x in runs if x == hi)}回")
        mk = lambda n_: Succession(id="s_run", label=f"連続勤務は{n_}日まで",
                                   max_run=n_, strength="強く", origin=_org(ev))
        ch = [Choice(f"{lo}日まで", mk(lo))]
        if hi != lo:
            ch.append(Choice(f"{hi}日まで", mk(hi)))
        ch.append(Choice("決めない"))
        out.append(Candidate(
            id="run", question="連続勤務の上限は何日ですか。", evidence=ev, kind="boundary", choices=ch))

    # ---- 3 日ごとの人数（最小と最頻が違えば境界値）
    for k in [*night, *[x for x in work if x not in night and kinds[x].counts_as_staff]]:
        per = [sum(1 for n in nurses if cell(n.id, d) == k) for d in days]
        if not any(per):
            continue
        mn, mode = min(per), max(set(per), key=per.count)
        ev = f"{m.month}の表で毎日{mn}〜{max(per)}名（{per.count(mode)}/{len(per)}日が{mode}名）"
        mk = lambda v, k=k, ev=ev: Staffing(
            id=f"st_{k}", label=f"{kinds[k].name}は毎日{v}名以上",
            shifts=ShiftSel(ids=[k]), at_least=v, origin=_org(ev))
        ch = [Choice(f"{mn}名以上", mk(mn))]
        if mode != mn:
            ch.append(Choice(f"{mode}名以上", mk(mode)))
        ch.append(Choice("決めない"))
        q = (f"{kinds[k].name}は毎日何名要りますか。" if mode != mn
             else f"{kinds[k].name}は、どの日も{mn}名でした。これは決まりですか。")
        out.append(Candidate(
            id=f"staff_{k}", question=q,
            evidence=ev, kind="boundary" if mode != mn else "yesno", choices=ch))

    # ---- 4 公休（範囲なので境界値。硬くすると解けなくなるので既定は「強く」）
    if off:
        offs = {n.id: sum(1 for d in days if cell(n.id, d) == off) for n in nurses}
        lo, hi = min(offs.values()), max(offs.values())
        ev = f"{m.month}の表で全員{lo}〜{hi}日"
        out.append(Candidate(
            id="off", question=f"{kinds[off].name}は月に何日ですか。", evidence=ev, kind="boundary",
            choices=[
                Choice(f"{lo}〜{hi}日", Count(
                    id="c_off", label=f"{kinds[off].name}は月{lo}〜{hi}日", shifts=ShiftSel(ids=[off]),
                    at_least=lo, at_most=hi, strength="強く", origin=_org(ev))),
                Choice(f"{lo}日以上（上限なし）", Count(
                    id="c_off", label=f"{kinds[off].name}は月{lo}日以上", shifts=ShiftSel(ids=[off]),
                    at_least=lo, strength="強く", origin=_org(ev))),
                Choice("決めない"),
            ]))

    # ---- 5 人員に数えない区分の回数（研修など）
    for k in work:
        if kinds[k].counts_as_staff:
            continue
        per = {n.id: sum(1 for d in days if cell(n.id, d) == k) for n in nurses}
        if not any(per.values()):
            continue
        mx = max(per.values())
        ev = f"{m.month}の表で最多{mx}回（{sum(1 for v in per.values() if v)}名）"
        out.append(Candidate(
            id=f"cnt_{k}", question=f"{kinds[k].name}は月に何回までですか。", evidence=ev, kind="boundary",
            choices=[
                Choice(f"{mx}回まで", Count(id=f"c_{k}", label=f"{kinds[k].name}は月{mx}回まで",
                                            shifts=ShiftSel(ids=[k]), at_most=mx, origin=_org(ev))),
                Choice("決めない"),
            ]))

    # ---- 6 人に紐づくもの（聞くのは期限）
    for n in nurses:
        if night and sum(1 for d in days if cell(n.id, d) in night) == 0:
            ev = f"{m.month}の表で夜勤0回"
            mk = lambda: Request(
                id=f"rq_{n.id}_nonight", label=f"{n.name} は夜勤に入らない",
                people=PeopleSel(ids=[n.id]), days=DaySel(), shifts=ShiftSel(ids=night),
                want=False, origin=_org(ev))
            out.append(Candidate(
                id=f"nonight_{n.id}",
                question=f"{n.name} さんは夜勤に入っていません。いつまでですか。",
                evidence=ev, kind="term",
                choices=[
                    Choice("年度末まで", mk(), "2027-03-31"),
                    Choice("今年いっぱい", mk(), "2026-12-31"),
                    Choice("恒久", mk()),
                    Choice("たまたまです"),
                ]))

    # ---- 7 人ごとの夜勤時間の上限（平均が72h以下でも個人が偏るため）
    if night:
        nh = {n.id: sum(kinds[c].night_hours for d in days
                        if (c := cell(n.id, d)) in night) for n in nurses}
        mx = max(nh.values())
        if mx > 0:
            ev = f"{m.month}の表で最多{mx:.0f}時間"
            out.append(Candidate(
                id="nh", question="1人あたりの夜勤時間に上限を置きますか。", evidence=ev, kind="boundary",
                choices=[
                    Choice(f"月{mx:.0f}時間まで", Count(
                        id="c_nh", label=f"1人の夜勤時間は月{mx:.0f}時間まで", shifts=ShiftSel(ids=night),
                        unit="時間", at_most=mx, strength="強く", origin=_org(ev))),
                    Choice("置かない"),
                ]))
    return out
