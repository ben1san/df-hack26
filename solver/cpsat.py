"""CP-SAT。ルール一覧を読んで解き、不充足なら原因と破れ量を返す。

設計の肝は3つ。
1. 全規則にインスタンス単位の強制リテラルを付ける。後から付け直すのは実質作り直し
2. 硬制約は assumption に入れ、不充足なら sufficient_assumptions_for_infeasibility() で原因
3. 原因が出たら二度目を解く。最小不充足集合だけでは足りず「どれだけ破れば通るか」が要る
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from app.dsl import (
    PENALTY,
    Count,
    Month,
    OneShiftPerDay,
    Request,
    Rule,
    Staffing,
    Succession,
    Ward,
    WardNightAverage,
)

SCALE = 10  # 時間を整数で持つ


@dataclass
class Broken:
    rule_id: str
    label: str
    count: int = 0          # 破れたインスタンス数
    detail: str | None = None


@dataclass
class SolveResult:
    status: str                              # OPTIMAL / FEASIBLE / INFEASIBLE
    cells: dict[str, list[str | None]] = field(default_factory=dict)
    infeasible_rules: list[Broken] = field(default_factory=list)   # 最小不充足集合
    relaxation: list[Broken] = field(default_factory=list)         # 破れ量（二度解き）
    soft_broken: list[Broken] = field(default_factory=list)        # 軟制約の破れ
    night_average: float | None = None
    wall_ms: int = 0


class _Build:
    def __init__(self, ward: Ward, month: Month, rules: list[Rule], fixed: dict[str, list[str | None]]):
        self.w, self.m, self.rules = ward, month, rules
        self.kinds = {k.id: k for k in ward.shift_kinds}
        self.nurses = ward.nurses
        self.days = list(range(1, month.days + 1))
        self.mo = cp_model.CpModel()
        self.x: dict[tuple[str, int, str], cp_model.IntVar] = {}
        self.lits: list[tuple[cp_model.IntVar, Rule]] = []   # (リテラル, 由来の規則)
        self.hard_assumptions: list[cp_model.IntVar] = []
        self.soft_terms: list[tuple[cp_model.IntVar, int, Rule]] = []

        for n in self.nurses:
            for d in self.days:
                for kid in self.kinds:
                    self.x[n.id, d, kid] = self.mo.new_bool_var(f"x_{n.id}_{d}_{kid}")
                # oneShiftPerDay は型で持つが、構造として常に入れる
                self.mo.add_exactly_one(self.x[n.id, d, kid] for kid in self.kinds)

        # 夜勤時間の集計は常に持つ。72時間ルールが無くても読み取りとして要る
        self.nh_exprs: list = []
        self.nw_vars: list = []
        for n in self.nurses:
            h = sum(self.x[n.id, d, k] * int(self.kinds[k].night_hours * SCALE)
                    for d in self.days for k in self.kinds if self.kinds[k].night_hours > 0)
            b = self.mo.new_bool_var(f"nw_{n.id}")
            self.mo.add(h >= 16 * SCALE).only_enforce_if(b)
            self.mo.add(h <= 16 * SCALE - 1).only_enforce_if(~b)
            self.nh_exprs.append(h)
            self.nw_vars.append(b)

        # 既決のセル（手修正、および段階1の夜勤段の結果）を固定する
        for nid, row in fixed.items():
            for i, kid in enumerate(row[: month.days]):
                if kid:
                    self.mo.add(self.x[nid, i + 1, kid] == 1)

    # ------------------------------------------------------------ 補助
    def _lit(self, r: Rule) -> cp_model.IntVar:
        """規則インスタンス1件ぶんのリテラル。硬なら assumption、軟なら目的関数へ。"""
        v = self.mo.new_bool_var(f"lit_{r.id}_{len(self.lits)}")
        self.lits.append((v, r))
        if r.strength == "絶対":
            self.hard_assumptions.append(v)
        else:
            self.soft_terms.append((v, PENALTY[r.strength], r))
        return v

    def _people(self, sel) -> list[str]:
        return [n.id for n in self.nurses if sel.match(n)]

    def _days(self, sel) -> list[int]:
        return [d for d in self.days if sel.match(d, self.m.weekday(d), self.w.day_groups)]

    def _shifts(self, sel) -> list[str]:
        return [k for k in self.kinds if sel.match(k)]

    def _in(self, nid: str, d: int, kids: list[str]):
        return sum(self.x[nid, d, k] for k in kids)

    # ------------------------------------------------------------ 6型
    def add_all(self):
        for r in self.rules:
            if isinstance(r, OneShiftPerDay):
                continue                      # 構造として既に入っている
            getattr(self, f"_add_{r.type}")(r)

    def _add_staffing(self, r: Staffing):
        people, kids = self._people(r.people), self._shifts(r.shifts)
        for d in self._days(r.days):
            tot = sum(self._in(p, d, kids) for p in people)
            if r.at_least is not None:
                self.mo.add(tot >= r.at_least).only_enforce_if(self._lit(r))
            if r.at_most is not None:
                self.mo.add(tot <= r.at_most).only_enforce_if(self._lit(r))

    def _add_request(self, r: Request):
        kids = self._shifts(r.shifts)
        for p in self._people(r.people):
            for d in self._days(r.days):
                want = self._in(p, d, kids)
                self.mo.add(want >= 1 if r.want else want == 0).only_enforce_if(self._lit(r))

    def _add_succession(self, r: Succession):
        people = self._people(r.people)
        if r.max_run is not None:
            work = [k for k, v in self.kinds.items() if not v.is_off]
            n = r.max_run
            for p in people:
                for s in range(1, self.m.days - n + 1):
                    # 窓 n+1 日のうち、勤務は n 日まで（＝休みが1日は入る）
                    self.mo.add(sum(self._in(p, s + i, work) for i in range(n + 1)) <= n
                                ).only_enforce_if(self._lit(r))
            return
        pat = [self._shifts(s) for s in r.pattern]
        L = len(pat)
        for p in people:
            for s in range(1, self.m.days - L + 2):
                ms = []
                for i, kids in enumerate(pat):
                    b = self.mo.new_bool_var(f"m_{r.id}_{p}_{s}_{i}")
                    self.mo.add(self._in(p, s + i, kids) == 1).only_enforce_if(b)
                    self.mo.add(self._in(p, s + i, kids) == 0).only_enforce_if(~b)
                    ms.append(b)
                lit = self._lit(r)
                if r.forbid:
                    self.mo.add_bool_or([~b for b in ms]).only_enforce_if(lit)
                else:
                    self.mo.add_bool_and(ms).only_enforce_if(lit)

    def _add_count(self, r: Count):
        kids, ds = self._shifts(r.shifts), self._days(r.days)
        for p in self._people(r.people):
            if r.unit == "回":
                tot = sum(self._in(p, d, kids) for d in ds)
                lo = r.at_least, r.at_most
            else:
                tot = sum(self.x[p, d, k] * int(self.kinds[k].hours * SCALE) for d in ds for k in kids)
                lo = (None if r.at_least is None else r.at_least * SCALE,
                      None if r.at_most is None else r.at_most * SCALE)
            if lo[0] is not None:
                self.mo.add(tot >= int(lo[0])).only_enforce_if(self._lit(r))
            if lo[1] is not None:
                self.mo.add(tot <= int(lo[1])).only_enforce_if(self._lit(r))

    def _add_wardNightAverage(self, r: WardNightAverage):
        """月平均夜勤時間数 ＝ 夜勤時間数の総和 / 夜勤従事者数 ≦ cap

        分母が解に依存するので非線形に見えるが、両辺に分母を掛けると線形になる。
        """
        self.mo.add(sum(self.nh_exprs) <= int(r.cap * SCALE) * sum(self.nw_vars)
                    ).only_enforce_if(self._lit(r))


def _rows(sol, b: _Build) -> dict[str, list[str | None]]:
    out = {}
    for n in b.nurses:
        out[n.id] = [next((k for k in b.kinds if sol.value(b.x[n.id, d, k])), None) for d in b.days]
    return out


def solve(ward: Ward, month: Month, rules: list[Rule], *,
          fixed: dict[str, list[str | None]] | None = None,
          time_limit: float = 10.0, seed: int = 0) -> SolveResult:
    t0 = time.time()
    b = _Build(ward, month, rules, fixed or {})
    b.add_all()

    if b.soft_terms:
        b.mo.minimize(sum(p * (1 - v) for v, p, _ in b.soft_terms))

    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.random_seed = seed
    s.parameters.num_workers = 8
    for lit in b.hard_assumptions:
        b.mo.add_assumption(lit)

    st = s.solve(b.mo)
    name = s.status_name(st)
    res = SolveResult(status=name, wall_ms=int((time.time() - t0) * 1000))

    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res.cells = _rows(s, b)
        agg: dict[str, Broken] = {}
        for v, _, r in b.soft_terms:
            if not s.value(v):
                k = agg.setdefault(r.id, Broken(r.id, r.label))
                k.count += 1
        res.soft_broken = list(agg.values())
        if b.nh_exprs:
            tot = sum(s.value(e) for e in b.nh_exprs) / SCALE
            cnt = sum(s.value(v) for v in b.nw_vars)
            res.night_average = round(tot / cnt, 1) if cnt else 0.0
        return res

    # ---- 不充足。原因と破れ量を返す
    idx = set(s.sufficient_assumptions_for_infeasibility())
    culprits: dict[str, Broken] = {}
    lit_of_rule: dict[str, list] = {}
    for i, lit in enumerate(b.hard_assumptions):
        rule = next(r for v, r in b.lits if v is lit)
        lit_of_rule.setdefault(rule.id, []).append(lit)
        if lit.index in idx or i in idx:
            culprits.setdefault(rule.id, Broken(rule.id, rule.label))
    res.infeasible_rules = list(culprits.values())   # 補助情報。headlineにはしない

    # 二度解き — 全硬制約を軟にして「最小で何件破れば通るか」を測る。
    # sufficient_assumptions_for_infeasibility() は広い集合を返すので headline には使えない
    # （12人病棟の実測で9本中9本が返った）。使えるのはこちらの破れ量。
    # 法令由来は重く置き、師長のルールが先に破れるようにする。
    b2 = _Build(ward, month, rules, fixed or {})
    b2.add_all()
    relax = [(lit, r) for lit, r in b2.lits if r.strength == "絶対"]
    b2.mo.minimize(sum((100 if r.locked else 1) * (1 - lit) for lit, r in relax))
    s2 = cp_model.CpSolver()
    s2.parameters.max_time_in_seconds = time_limit
    s2.parameters.num_workers = 8
    if s2.solve(b2.mo) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        agg: dict[str, Broken] = {}
        inst: dict[str, int] = {}
        for lit, rule in relax:
            inst[rule.id] = inst.get(rule.id, 0) + 1
            if not s2.value(lit):
                agg.setdefault(rule.id, Broken(rule.id, rule.label)).count += 1
        for rid, bk in agg.items():
            bk.detail = f"{bk.count}/{inst[rid]}件"
        if b2.nh_exprs:
            tot = sum(s2.value(e) for e in b2.nh_exprs) / SCALE
            cnt = sum(s2.value(v) for v in b2.nw_vars)
            res.night_average = round(tot / cnt, 1) if cnt else 0.0
        res.relaxation = sorted(agg.values(), key=lambda x: -x.count)
    return res
