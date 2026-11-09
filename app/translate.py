"""自然言語 → 制約候補1本。LLMが出るのはここだけ。

初回求解の前には置かない。文章全体から網羅抽出すると、落ちた制約が気づかれないまま
最初の1枚に乗る。指したセル1つ → 制約1本にすると、落ちれば直前の操作が通らないとして即分かる。

範囲（この人だけ／この曜日全体／全員）と期限はLLMに当てさせない。師長が段階3で選ぶ。
"""
from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

from app.dsl import (Count, DaySel, Origin, PeopleSel, Request, Rule, ShiftSel,
                     Succession, Ward)

WD = ["日", "月", "火", "水", "木", "金", "土"]

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


class RuleDraft(BaseModel):
    """LLMが埋められる唯一の形。これ以外は構造上生成できない。"""
    type: Literal["request", "succession", "count"] = Field(
        description="request=その人がその勤務に入る/入らない, succession=勤務の連なり, count=回数や時間の上下限")
    shift_ids: list[str] = Field(default_factory=list, description="対象の勤務区分ID")
    want: bool | None = Field(default=None, description="request のとき True=希望 False=回避")
    after_shift_ids: list[str] = Field(default_factory=list, description="succession のとき、直後に置かせない勤務")
    max_run: int | None = Field(default=None, description="succession のとき、連続勤務の上限日数")
    at_least: int | None = None
    at_most: int | None = None
    label_ja: str = Field(description="師長が読む1行。主語と対象を省略しない")


PROMPT = """あなたは看護師勤務表の制約を書き起こす。勤務表そのものは作らない。

病棟の勤務区分: {kinds}
師長が指したセル: {nurse} / {month}月{day}日({wd}曜) / いま {kind}
師長の言葉: 「{text}」

このセル1つについての制約を1本だけ書き起こす。
- 範囲を広げない。指された人・その曜日・その勤務区分だけを対象にする
- 言葉に無い条件を足さない
- 勤務区分は上の一覧のIDだけを使う
"""


def _stub(text: str, kind: str) -> RuleDraft:
    """資格情報が無いときの代替。開発を止めないためのもので、本番経路ではない。"""
    t = text.replace(" ", "")
    if "連続" in t or "連勤" in t:
        n = next((int(c) for c in t if c.isdigit()), 5)
        return RuleDraft(type="succession", max_run=n, label_ja=f"連続勤務は{n}日まで")
    if "あと" in t or "翌日" in t or "後に" in t:
        return RuleDraft(type="succession", shift_ids=[kind], after_shift_ids=["日", "準", "深"],
                         label_ja=f"{kind}のあとに勤務を置かない")
    return RuleDraft(type="request", shift_ids=[kind], want=False,
                     label_ja=f"{kind}に入らない")


def draft(ward: Ward, *, nurse_id: str, month: str, day: int, weekday: int,
          kind: str, text: str) -> tuple[RuleDraft, str]:
    """(候補, どの経路で出したか) を返す。"""
    kinds = ", ".join(f"{k.id}={k.name}" for k in ward.shift_kinds)
    nurse = next((n.name for n in ward.nurses if n.id == nurse_id), nurse_id)
    p = PROMPT.format(kinds=kinds, nurse=nurse, month=month.split("-")[1], day=day,
                      wd=WD[weekday], kind=kind, text=text)
    try:
        from google import genai
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "1":
            client = genai.Client(vertexai=True,
                                  project=os.environ["GOOGLE_CLOUD_PROJECT"],
                                  location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
            route = f"vertex:{MODEL}"
        else:
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            route = f"aistudio:{MODEL}"
        r = client.models.generate_content(
            model=MODEL, contents=p,
            config={"response_mime_type": "application/json", "response_schema": RuleDraft,
                    "temperature": 0.0},
        )
        return RuleDraft.model_validate_json(r.text), route
    except Exception as e:                      # 鍵が無い・落ちた・形が違う
        return _stub(text, kind), f"stub({type(e).__name__})"


def to_rules(d: RuleDraft, *, rid: str, nurse_id: str, nurse_name: str,
             weekday: int, origin: Origin) -> list[tuple[str, Rule]]:
    """候補1本から、範囲3通りを組む。選ぶのは師長。機械は一般化を当てない。"""
    wd = WD[weekday]
    out: list[tuple[str, Rule]] = []

    def mk(scope: str, label: str, people: PeopleSel, days: DaySel) -> None:
        if d.type == "request":
            r: Rule = Request(id=f"{rid}_{scope}", label=label, people=people, days=days,
                              shifts=ShiftSel(ids=d.shift_ids or None),
                              want=bool(d.want), origin=origin)
        elif d.type == "succession":
            r = Succession(id=f"{rid}_{scope}", label=label, people=people,
                           max_run=d.max_run,
                           pattern=None if d.max_run else
                           [ShiftSel(ids=d.shift_ids or None), ShiftSel(ids=d.after_shift_ids or None)],
                           forbid=True, origin=origin)
        else:
            r = Count(id=f"{rid}_{scope}", label=label, people=people, days=days,
                      shifts=ShiftSel(ids=d.shift_ids or None),
                      at_least=d.at_least, at_most=d.at_most, origin=origin)
        out.append((scope, r))

    mk("one", f"{nurse_name} は{wd}曜の{d.label_ja}", PeopleSel(ids=[nurse_id]),
       DaySel(weekdays=[weekday]))
    mk("allwd", f"{nurse_name} は{d.label_ja}", PeopleSel(ids=[nurse_id]), DaySel())
    mk("allp", f"{wd}曜は全員 {d.label_ja}", PeopleSel(), DaySel(weekdays=[weekday]))
    return out
