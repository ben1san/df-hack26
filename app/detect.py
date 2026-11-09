"""反復検出。鍵の一致と、観測量から決まる閾値。

鍵 ＝ (人, 曜日, 外された勤務)。構造比較はしない。
「直した後」は鍵に入れない — ある月は休、別の月は日でも、共通しているのは「深夜勤を外した」こと。
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from app.dsl import Edit, Month

WD = ["日", "月", "火", "水", "木", "金", "土"]


def key_of(e: Edit, m: Month) -> tuple[str, int, str] | None:
    """手修正1件から鍵を作る。勤務を外した修正だけが鍵を持つ。"""
    if not e.frm or e.frm == e.to:
        return None
    return (e.nurse_id, m.weekday(e.day), e.frm)


def threshold(n_keys: int, edits_per_month: float, *, false_per_year: float = 1.0) -> int:
    """誤検出を年 false_per_year 件未満に抑える最小の連続月数。

    鍵の数を K、ある月にある鍵で手修正が起きる確率を p とすると
    n ヶ月連続が偶然そろう期待数 ＝ K × pⁿ。固定値の「3回」は使わない。
    """
    if n_keys <= 0 or edits_per_month <= 0:
        return 3
    p = min(edits_per_month / n_keys, 0.999)
    for n in range(2, 13):
        if 12 * n_keys * p ** n < false_per_year:
            return n
    return 12


def n_keys(n_nurses_on_night: int, n_shift_kinds: int) -> int:
    """鍵の数。夜勤に入れる人 × 7曜日 × 勤務区分。"""
    return n_nurses_on_night * 7 * n_shift_kinds


@dataclass
class Repeat:
    nurse_id: str
    weekday: int
    kind_id: str
    months: list[str]
    streak: int
    threshold: int
    edit_ids: list[str]

    @property
    def fired(self) -> bool:
        return self.streak >= self.threshold

    def evidence(self, nurse_name: str, kind_name: str) -> str:
        return (f"過去{self.streak}ヶ月（{'・'.join(self.months)}）、"
                f"{nurse_name} の{WD[self.weekday]}曜の{kind_name}を毎月外している")


def detect(months: list[Month], edits: dict[str, list[Edit]], *,
           n_key: int, upto: str) -> list[Repeat]:
    """月ごとに重複排除して連続月数を数える。upto は「今月」。"""
    seen: dict[tuple, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    total = 0
    for m in months:
        for e in edits.get(m.month, []):
            total += 1
            k = key_of(e, m)
            if k:
                seen[k][m.month].append(e.id)   # 同じ月に2回直しても1回と数える

    order = sorted({m.month for m in months})
    # 分母は「使った月」だけ。取り込んだ過去の表や、作成中の今月を入れると
    # 1ヶ月あたりの手修正が薄まり、閾値が実際より低く出る。
    used = {mo for mo in order if any(key_of(e, m) for m in months if m.month == mo
                                      for e in edits.get(mo, []))}
    per_month = total / max(len(used), 1)
    th = threshold(n_key, per_month)

    out = []
    for k, by_month in seen.items():
        # 連続の終わりは「今月」または「先月」でよい。
        # 今月の表をいま作っている最中は、まだ今月の修正が無い。
        # そこで切ると「過去3ヶ月、毎回直しています」を4回目を直す前に言えなくなる。
        last = next((i for i in range(len(order) - 1, -1, -1) if order[i] in by_month), None)
        if last is None or last < len(order) - 2:
            continue
        run, ids = [], []
        for i in range(last, -1, -1):
            mo = order[i]
            if mo in by_month:
                run.append(mo); ids += by_month[mo]
            else:
                break
        out.append(Repeat(k[0], k[1], k[2], list(reversed(run)), len(run), th, ids))
    return sorted(out, key=lambda r: -r.streak)
