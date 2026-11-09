"""勤務表ルールのDSL。6型だけ。

この層が意味境界。LLMもUIも病院設定も、ここを通らずに求解器へ届かない。
型を増やすと保存形式と画面が全部動くので、増やす前に組み合わせで近似できないか見る。
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------- 語彙（病院側）

class ShiftKind(BaseModel):
    """勤務区分。病院ごとに自由。'新人不算人力' のような区分が実在する。"""
    id: str                      # 表に出る1文字 例 日 準 深 休 研
    name: str                    # 例 日勤 準夜勤 深夜勤 公休 研修
    hours: float = 0.0           # 拘束時間
    night_hours: float = 0.0     # うち夜勤時間数（72時間ルールの分子）
    crosses_midnight: bool = False
    is_off: bool = False         # 休みか（連続勤務の数え方が変わる）
    counts_as_staff: bool = True  # 人員に数えるか（研修・新人不算人力は False）


class Ward(BaseModel):
    id: str
    name: str
    shift_kinds: list[ShiftKind]
    nurses: list["Nurse"]
    night_band_start: int = 22   # 夜勤時間帯の開始時刻。22時〜翌5時を含む連続16時間の範囲で病院が定める
    night_average_cap: float = 72.0   # 入院基本料区分で変わる
    day_groups: dict[str, list[int]] = Field(default_factory=dict)  # 病院独自の日付群（1始まりの日）


class Nurse(BaseModel):
    id: str
    name: str
    qual: str                    # 主任 / 正 / 准 / 新人 …病院の語彙
    groups: list[str] = Field(default_factory=list)   # チーム・役割


# ---------------------------------------------------------------- 選択子

class PeopleSel(BaseModel):
    ids: list[str] | None = None
    quals: list[str] | None = None
    groups: list[str] | None = None

    def match(self, n: Nurse) -> bool:
        if self.ids is not None and n.id not in self.ids:
            return False
        if self.quals is not None and n.qual not in self.quals:
            return False
        if self.groups is not None and not (set(self.groups) & set(n.groups)):
            return False
        return True


class DaySel(BaseModel):
    """日付群。曜日は 0=日 .. 6=土。dates は1始まりの日。"""
    weekdays: list[int] | None = None
    dates: list[int] | None = None
    named: str | None = None     # ward.day_groups のキー、または 平日 / 休日

    def match(self, day: int, weekday: int, named: dict[str, list[int]]) -> bool:
        if self.weekdays is not None and weekday not in self.weekdays:
            return False
        if self.dates is not None and day not in self.dates:
            return False
        if self.named is not None:
            if self.named == "平日":
                if weekday in (0, 6):
                    return False
            elif self.named == "休日":
                if weekday not in (0, 6):
                    return False
            elif day not in named.get(self.named, []):
                return False
        return True


class ShiftSel(BaseModel):
    ids: list[str] | None = None

    def match(self, kind_id: str) -> bool:
        return self.ids is None or kind_id in self.ids


# ---------------------------------------------------------------- 重み

Strength = Literal["絶対", "強く", "できれば"]

# 段階 → 罰点。先行実装は -1/-1000/-1億/-1兆/-inf と桁を手で積んでいたが、
# 師長に数値を触らせる形は一度も試されていないので3段階に写す。
# 【要検証】この写像が機能するかは未測。一度回して分布を見る。
PENALTY: dict[Strength, int] = {"強く": 1000, "できれば": 1}


# ---------------------------------------------------------------- 来歴と寿命

OriginKind = Literal["法令", "ガイドライン", "段階0逆算", "反復検出", "師長の言葉", "手入力"]


class Origin(BaseModel):
    """来歴。これ自体が引き継ぎ機能。次の師長はルール一覧を読むだけで前任の暗黙知を受け取る。"""
    kind: OriginKind
    detected_from: list[str] = Field(default_factory=list)  # edit id の列
    evidence: str | None = None      # 例 「過去3ヶ月、金曜の深夜勤を毎回外している」
    approved_by: str | None = None
    approved_at: date | None = None
    source_url: str | None = None    # 法令・ガイドライン由来のとき


class Lifecycle(BaseModel):
    """反復が生み、期限と不使用が殺す。片方だけ作ると使うほど壊れる。"""
    expires_on: date | None = None   # None なら恒久
    last_fired_on: date | None = None
    stopped: bool = False            # 期限切れ or 師長が止めた

    def active_on(self, d: date) -> bool:
        if self.stopped:
            return False
        return self.expires_on is None or d <= self.expires_on


class RuleBase(BaseModel):
    id: str
    label: str                       # 師長が読む1行 例「佐藤 恵 は金曜の深夜勤に入らない」
    strength: Strength = "絶対"
    origin: Origin
    lifecycle: Lifecycle = Field(default_factory=Lifecycle)
    locked: bool = False             # 法令由来。解除には理由の記録を要する


# ---------------------------------------------------------------- 6型

class OneShiftPerDay(RuleBase):
    """構造制約。常に有効で、消せない。"""
    type: Literal["oneShiftPerDay"] = "oneShiftPerDay"
    strength: Strength = "絶対"
    locked: bool = True


class Staffing(RuleBase):
    """勤務区分 × 資格者群 × 日付群 ごとの必要人数。"""
    type: Literal["staffing"] = "staffing"
    shifts: ShiftSel
    people: PeopleSel = Field(default_factory=PeopleSel)
    days: DaySel = Field(default_factory=DaySel)
    at_least: int | None = None
    at_most: int | None = None

    @model_validator(mode="after")
    def _bounds(self):
        if self.at_least is None and self.at_most is None:
            raise ValueError("staffing は at_least か at_most のどちらかが要る")
        return self


class Request(RuleBase):
    """人群 × 日付群 × 勤務区分群 の希望・回避。当月の希望がここに入る。
    先行実装の実データでは183規則のうち157本がこれ。ただし毎月入れ替わるので病棟のルールではない。"""
    type: Literal["request"] = "request"
    people: PeopleSel
    days: DaySel
    shifts: ShiftSel
    want: bool = True                # True=希望 False=回避


class Succession(RuleBase):
    """勤務の連なりの禁止・奨励。例「深のあとに日を置かない」「連続勤務は5日まで」。"""
    type: Literal["succession"] = "succession"
    people: PeopleSel = Field(default_factory=PeopleSel)
    pattern: list[ShiftSel] | None = None   # 連なりの形。None なら max_run を使う
    forbid: bool = True
    max_run: int | None = None              # 休み以外の連続日数の上限

    @model_validator(mode="after")
    def _one_of(self):
        if (self.pattern is None) == (self.max_run is None):
            raise ValueError("succession は pattern か max_run のどちらか一方")
        return self


class Count(RuleBase):
    """人ごとの勤務数・時間数の上下限。人をまたいで集計しない。"""
    type: Literal["count"] = "count"
    people: PeopleSel = Field(default_factory=PeopleSel)
    shifts: ShiftSel
    days: DaySel = Field(default_factory=DaySel)
    unit: Literal["回", "時間"] = "回"
    at_least: float | None = None
    at_most: float | None = None


class WardNightAverage(RuleBase):
    """病棟集計の月平均夜勤時間数 ≦ 72。

    count と分けてある理由は、人をまたいで集計し、かつ分母（夜勤に従事した者の数）が
    解に依存するため。同じ「計数」に見えて数学的に別物。
    """
    type: Literal["wardNightAverage"] = "wardNightAverage"
    cap: float = 72.0
    min_night_hours_to_count: float = 16.0   # 【要確認】分母に数える下限。施設基準の細則を未確認
    locked: bool = True


Rule = Annotated[
    Union[OneShiftPerDay, Staffing, Request, Succession, Count, WardNightAverage],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------- 表と編集

class Cell(BaseModel):
    nurse_id: str
    day: int                     # 1始まり
    kind_id: str | None = None   # None は未定


class Edit(BaseModel):
    """手修正1件。追記のみ。これが消えると反復が観測できなくなる。"""
    id: str
    nurse_id: str
    day: int
    frm: str | None = Field(default=None, alias="from")   # 直す前（＝ソルバの提案）
    to: str | None = None                                 # 直した後
    at: str                                               # ISO8601
    synthetic: bool = False      # 擬似履歴（過去の表とソルバ出力の差分）から作ったもの

    model_config = {"populate_by_name": True}


class Month(BaseModel):
    """提案と現状を別に持つ。棄却＝提案があって現状が違うセル。
    1本の配列で持つと棄却が定義できない。後から足せない構造。"""
    month: str                   # YYYY-MM
    days: int
    first_weekday: int           # 1日の曜日 0=日
    proposal: dict[str, list[str | None]] = Field(default_factory=dict)   # nurse_id -> days
    current: dict[str, list[str | None]] = Field(default_factory=dict)
    rules_snapshot: list[str] = Field(default_factory=list)  # 解いた時点で当てていた rule id
    solved_at: str | None = None

    def weekday(self, day: int) -> int:
        return (self.first_weekday + day - 1) % 7
