"""Vertex AI の疎通確認。資格情報が通ったら、これを1回走らせる。

    GOOGLE_CLOUD_PROJECT=<id> GOOGLE_GENAI_USE_VERTEXAI=1 python scripts/smoke_vertex.py

AI Studio の無料キーで先に試すなら:

    GEMINI_API_KEY=<key> python scripts/smoke_vertex.py

route が stub(...) のままなら、資格情報かモデル名で落ちている（例外名が括弧に出る）。
"""
from __future__ import annotations

import json
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.dsl import Origin, Ward           # noqa: E402
from app.translate import MODEL, draft, to_rules  # noqa: E402

CASES = [
    ("2", 13, 5, "深", "佐藤さんは金曜の深夜勤は無理です"),
    ("3", 7, 6, "準", "深夜勤のあとに日勤を入れないでください"),
    ("5", 2, 1, "日", "連勤は4日までにしてほしい"),
    ("7", 20, 5, "深", "この人は当分のあいだ夜勤を外してください"),
]


def main() -> int:
    vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "1"
    print(f"経路   {'Vertex AI' if vertex else 'AI Studio'}   モデル {MODEL}")
    if vertex:
        print(f"       project={os.environ.get('GOOGLE_CLOUD_PROJECT')} "
              f"location={os.environ.get('GOOGLE_CLOUD_LOCATION', 'global')}")
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            print("!! GOOGLE_CLOUD_PROJECT がない")
            return 2
    elif not os.environ.get("GEMINI_API_KEY"):
        print("!! GEMINI_API_KEY も GOOGLE_GENAI_USE_VERTEXAI=1 も無い。スタブに落ちる")

    w = Ward(**json.load(open("seed/ward.json")))
    ok = stub = 0
    for nid, day, wd, kind, text in CASES:
        d, route = draft(w, nurse_id=nid, month="2026-11", day=day,
                         weekday=wd, kind=kind, text=text)
        name = next((n.name for n in w.nurses if n.id == nid), nid)
        mark = "stub" if route.startswith("stub") else "  ok"
        if route.startswith("stub"):
            stub += 1
        else:
            ok += 1
        print(f"\n[{mark}] 「{text}」   route={route}")
        print(f"       型 {d.type}  →  {d.label_ja}")
        for sc, r in to_rules(d, rid="smoke", nurse_id=nid, nurse_name=name,
                              weekday=wd, origin=Origin(kind="師長の言葉")):
            print(f"         {sc:6} {r.label}")

    print(f"\n本物 {ok} 件 / スタブ {stub} 件")
    if stub:
        print("スタブが出ている = LLMに届いていない。route の括弧内が原因。")
        print("  KeyError         … 環境変数が無い")
        print("  PermissionDenied … サービスアカウントに roles/aiplatform.user が無い")
        print("  NotFound         … モデル名かリージョン（GEMINI_MODEL / GOOGLE_CLOUD_LOCATION）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
