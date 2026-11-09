"""API。6本だけ。

設計上の禁止 — 表を上書きするエンドポイントを作らない。
表は状態ではなく (提案 ＋ 編集ログ) の射影。1本でも上書きを許すと差分が消え、反復が観測できなくなる。
"""
from __future__ import annotations

import json
import os
import pathlib
from datetime import date

import pydantic
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.derive import Candidate, derive
from app.detect import detect, n_keys
from app.dsl import Edit, Month, Origin, Rule, Ward, WardNightAverage
from app.repo import make_repo, new_id, now
from app.translate import RuleDraft, draft, to_rules
from solver.cpsat import solve

app = FastAPI(title="看護師勤務表", docs_url="/api/docs")
repo = make_repo()
RA = pydantic.TypeAdapter(list[Rule])
TIME_LIMIT = float(os.environ.get("SOLVE_SECONDS", "10"))


def _ward(wid: str) -> Ward:
    w = repo.get_ward(wid)
    if not w:
        raise HTTPException(404, f"病棟 {wid} がない")
    return w


def _active(rules: list[Rule], on: date) -> list[Rule]:
    return [r for r in rules if r.lifecycle.active_on(on)]


def _fold(m: Month, edits: list[Edit]) -> dict[str, list[str | None]]:
    """提案に編集ログを畳み込んで現状を作る。提案は壊さない。

    取り込んだ過去の表は提案を持たない（ソルバが置いたものではない）ので、
    そのときだけ保存済みの現状から始める。棄却は定義されない。
    """
    base = m.proposal if m.proposal else m.current
    cur = {k: list(v) for k, v in base.items()}
    for e in edits:
        cur.setdefault(e.nurse_id, [None] * m.days)
        if 1 <= e.day <= m.days:
            cur[e.nurse_id][e.day - 1] = e.to
    return cur


# ------------------------------------------------------------------ 1 bootstrap
@app.get("/api/ward/{wid}/month/{mo}")
def bootstrap(wid: str, mo: str):
    """画面が1回で必要なもの全部。ブラウザはFirestoreを直接触らない。"""
    w = _ward(wid)
    m = repo.get_month(wid, mo) or Month(month=mo, days=30, first_weekday=0)
    rules = repo.get_rules(wid)
    hist = [x for x in repo.months(wid) if x <= mo]
    months = [repo.get_month(wid, x) for x in hist]
    edits = {x: repo.get_edits(wid, x) for x in hist}
    K = n_keys(sum(1 for _ in w.nurses) - 1, sum(1 for k in w.shift_kinds if not k.is_off))
    reps = detect([x for x in months if x], edits, n_key=K, upto=mo)
    nm = {n.id: n.name for n in w.nurses}
    kn = {k.id: k.name for k in w.shift_kinds}
    return {
        "ward": w.model_dump(mode="json"),
        "month": m.model_dump(mode="json"),
        "current": _fold(m, edits.get(mo, [])),
        "rules": [r.model_dump(mode="json") for r in rules],
        "edits": [e.model_dump(mode="json", by_alias=True) for e in edits.get(mo, [])],
        "n_keys": K,
        "repeats": [_repeat_json(r, nm, kn, {x.id for x in rules}) for r in reps],
        "deaths": [
            {"rule_id": r.id, "label": r.label,
             "why": "期限切れ" if r.lifecycle.expires_on else "不使用"}
            for r in rules
            if r.lifecycle.expires_on and str(r.lifecycle.expires_on) < f"{mo}-01"
        ],
    }


def _repeat_json(r, nm: dict[str, str], kn: dict[str, str],
                 rule_ids: set[str]) -> dict:
    name = nm.get(r.nurse_id, r.nurse_id)
    kind = kn.get(r.kind_id, r.kind_id)
    ev = r.evidence(name, kind)
    rid = f"rp_{r.nurse_id}_{r.weekday}_{r.kind_id}"
    # 一度答えた反復は、もう聞かない。編集ログは消えないので検出自体は続く
    answered = any(x.startswith(rid + "_") for x in rule_ids)
    out = {
        "nurse_id": r.nurse_id, "nurse": name, "weekday": r.weekday,
        "kind_id": r.kind_id, "kind": kind, "months": r.months, "streak": r.streak,
        "threshold": r.threshold, "fired": r.fired, "edit_ids": r.edit_ids,
        "evidence": ev, "answered": answered, "candidates": [],
    }
    if not r.fired or answered:
        return out
    # 発火したときだけ範囲3通りを組む。一般化は機械が当てない
    d = RuleDraft(type="request", shift_ids=[r.kind_id], want=False,
                  label_ja=f"{kind}に入らない")
    o = Origin(kind="反復検出", detected_from=r.edit_ids, evidence=ev)
    out["candidates"] = [
        {"scope": sc, "rule": rule.model_dump(mode="json")}
        for sc, rule in to_rules(d, rid=rid,
                                 nurse_id=r.nurse_id, nurse_name=name,
                                 weekday=r.weekday, origin=o)
    ]
    return out


# ------------------------------------------------------------------ 2 solve
class SolveIn(BaseModel):
    stage: str = "night"          # night → day の二段階
    days: int = 30
    first_weekday: int = 0
    seed: int = 0


@app.post("/api/ward/{wid}/month/{mo}/solve")
def do_solve(wid: str, mo: str, body: SolveIn):
    """求解は常にソルバー。LLMは関与しない。"""
    w = _ward(wid)
    m = repo.get_month(wid, mo) or Month(month=mo, days=body.days,
                                         first_weekday=body.first_weekday)
    rules = _active(repo.get_rules(wid), date.fromisoformat(f"{mo}-01"))
    fixed: dict[str, list[str | None]] = {}
    if body.stage == "day":
        night = {k.id for k in w.shift_kinds if k.night_hours > 0}
        cur = _fold(m, repo.get_edits(wid, mo))
        fixed = {nid: [c if c in night else None for c in row] for nid, row in cur.items()}

    res = solve(w, m, rules, fixed=fixed, time_limit=TIME_LIMIT, seed=body.seed)
    if res.cells:
        night = {k.id for k in w.shift_kinds if k.night_hours > 0}
        if body.stage == "night":
            res.cells = {nid: [c if c in night else None for c in row]
                         for nid, row in res.cells.items()}
        m.proposal = res.cells
        m.rules_snapshot = [r.id for r in rules]      # 回帰に要る。後から作れない
        m.solved_at = now()
        repo.put_month(wid, m)
    return {
        "status": res.status, "stage": body.stage, "wall_ms": res.wall_ms,
        "proposal": res.cells, "night_average": res.night_average,
        "infeasible_rules": [b.__dict__ for b in res.infeasible_rules],
        "relaxation": [b.__dict__ for b in res.relaxation],
        "soft_broken": [b.__dict__ for b in res.soft_broken],
    }


# ------------------------------------------------------------------ 3 edits
class EditIn(BaseModel):
    nurse_id: str
    day: int
    to: str | None = None


@app.post("/api/ward/{wid}/month/{mo}/edits")
def add_edit(wid: str, mo: str, body: EditIn):
    """1セル1件、追記のみ。何も聞かない。段階2はここ。"""
    m = repo.get_month(wid, mo)
    if not m:
        raise HTTPException(404, "まだ解いていない月")
    frm = (m.proposal.get(body.nurse_id) or [None] * m.days)[body.day - 1]
    e = Edit(id=new_id("e"), nurse_id=body.nurse_id, day=body.day,
             **{"from": frm}, to=body.to, at=now())
    repo.append_edit(wid, mo, e)
    edits = repo.get_edits(wid, mo)
    return {"edit": e.model_dump(mode="json", by_alias=True),
            "current": _fold(m, edits),
            "rejected": sum(1 for x in edits if x.frm and x.frm != x.to)}


# ------------------------------------------------------------------ 4 rules
class RuleIn(BaseModel):
    rule: dict
    expires_on: date | None = None
    approved_by: str = "師長"


@app.post("/api/ward/{wid}/rules")
def put_rule(wid: str, body: RuleIn):
    r = pydantic.TypeAdapter(Rule).validate_python(body.rule)
    r.origin.approved_by = body.approved_by
    r.origin.approved_at = date.today()
    r.lifecycle.expires_on = body.expires_on
    repo.put_rule(wid, r)
    return {"rule": r.model_dump(mode="json")}


class PatchIn(BaseModel):
    stopped: bool | None = None
    expires_on: date | None = None


@app.patch("/api/ward/{wid}/rules/{rid}")
def patch_rule(wid: str, rid: str, body: PatchIn):
    """止める・延ばす。元に戻すのは機能ではなく前提条件なので、承認者を置かない。"""
    rules = repo.get_rules(wid)
    r = next((x for x in rules if x.id == rid), None)
    if not r:
        raise HTTPException(404, rid)
    if r.locked and body.stopped:
        raise HTTPException(409, f"{r.label} は法令由来。解除には理由の記録が要る")
    if body.stopped is not None:
        r.lifecycle.stopped = body.stopped
    if body.expires_on is not None:
        r.lifecycle.expires_on = body.expires_on
    repo.put_rule(wid, r)
    return {"rule": r.model_dump(mode="json")}


@app.delete("/api/ward/{wid}/rules/{rid}")
def delete_rule(wid: str, rid: str):
    """元に戻すのは機能ではなく前提条件。承認者を置かない。
    ルールが減る経路があることが、増える経路の前提。"""
    rules = repo.get_rules(wid)
    r = next((x for x in rules if x.id == rid), None)
    if not r:
        raise HTTPException(404, rid)
    if r.locked:
        raise HTTPException(409, f"{r.label} は法令由来。消せない")
    repo.delete_rule(wid, rid)
    return {"deleted": rid}


# ------------------------------------------------------------------ 5 translate
class TranslateIn(BaseModel):
    nurse_id: str
    month: str
    day: int
    weekday: int
    kind: str
    text: str


@app.post("/api/ward/{wid}/translate")
def do_translate(wid: str, body: TranslateIn):
    """指したセル1つ → 制約1本。範囲と期限は返した3通りから師長が選ぶ。"""
    w = _ward(wid)
    d, route = draft(w, nurse_id=body.nurse_id, month=body.month, day=body.day,
                     weekday=body.weekday, kind=body.kind, text=body.text)
    nm = next((n.name for n in w.nurses if n.id == body.nurse_id), body.nurse_id)
    o = Origin(kind="師長の言葉", evidence=f"師長の言葉「{body.text}」")
    cands = to_rules(d, rid=new_id("r"), nurse_id=body.nurse_id, nurse_name=nm,
                     weekday=body.weekday, origin=o)
    return {"route": route, "draft": d.model_dump(mode="json"),
            "candidates": [{"scope": s, "rule": r.model_dump(mode="json")} for s, r in cands]}


# ------------------------------------------------------------------ 段階0
class ImportIn(BaseModel):
    month: str
    days: int
    first_weekday: int
    cells: dict[str, list[str | None]]


@app.post("/api/ward/{wid}/import")
def import_month(wid: str, body: ImportIn):
    """過去の勤務表を取り込む。師長が手で作ったものなので提案は持たない。"""
    _ward(wid)
    m = Month(month=body.month, days=body.days, first_weekday=body.first_weekday,
              current=body.cells)
    repo.put_month(wid, m)
    return {"month": body.month, "nurses": len(body.cells), "days": body.days}


@app.post("/api/ward/{wid}/import/sample")
def import_sample(wid: str):
    """見本の表。手元に無い病院でも段階0を通せるようにする。"""
    f = pathlib.Path(__file__).resolve().parents[1] / "seed" / "october.json"
    if not f.exists():
        raise HTTPException(404, "見本の表がない")
    d = json.loads(f.read_text())
    return import_month(wid, ImportIn(**d))


def _cand_json(c: Candidate) -> dict:
    return {
        "id": c.id, "question": c.question, "evidence": c.evidence, "kind": c.kind,
        "choices": [
            {"label": ch.label,
             "rule": ch.rule.model_dump(mode="json") if ch.rule else None,
             "expires_on": ch.expires_on}
            for ch in c.choices
        ],
    }


@app.get("/api/ward/{wid}/candidates")
def candidates(wid: str, month: str):
    """取り込んだ表を数えて候補を返す。**作りはしない。**選ぶのは師長。

    候補ごとに選択肢の形が違う（可否 / 境界値 / 期限）。
    一度に全部出さず、画面側で1問ずつ出す。
    """
    w = _ward(wid)
    m = repo.get_month(wid, month)
    if not m:
        raise HTTPException(404, f"{month} は取り込まれていない")
    # 数えるのは実績（提案ではなく、師長が直したあとの表）
    m = m.model_copy(update={"current": _fold(m, repo.get_edits(wid, month))})
    return {"month": month, "candidates": [_cand_json(c) for c in derive(w, m)]}


# ------------------------------------------------------------------ 6 ward
LAW_SOURCE = ("https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/"
              "iryouhoken/iryouhoken01/index.html")


def _law_rules(w: Ward) -> list[Rule]:
    """法令・ガイドライン由来。表から逆算するものではないので、段階0で投入する。

    解除可能な形で入れる（locked=True は「解除に理由の記録が要る」であって不可ではない）。
    """
    return [WardNightAverage(
        id="law_72", cap=w.night_average_cap,
        label=f"月平均夜勤時間数は{w.night_average_cap:.0f}時間以下",
        origin=Origin(kind="法令", evidence="入院基本料の施設基準", source_url=LAW_SOURCE),
    )]


@app.post("/api/ward")
def put_ward(w: Ward):
    repo.put_ward(w)
    existing = {r.id for r in repo.get_rules(w.id)}
    added = [r for r in _law_rules(w) if r.id not in existing]
    for r in added:
        repo.put_rule(w.id, r)
    return {"ward_id": w.id, "law_rules": [r.label for r in added]}


@app.get("/api/health")
def health():
    return {"ok": True, "repo": type(repo).__name__, "solve_seconds": TIME_LIMIT}


_web = pathlib.Path(__file__).resolve().parents[1] / "web"
if _web.exists():
    app.mount("/", StaticFiles(directory=_web, html=True), name="web")
