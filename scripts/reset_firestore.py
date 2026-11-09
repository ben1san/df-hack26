"""Firestore の病棟を1つ消す。デモを作り直す前に走らせる。

    GOOGLE_CLOUD_PROJECT=<id> python scripts/reset_firestore.py [ward_id]

編集ログは追記専用なので、消さずに fixture.py を再実行すると手修正が二重に積まれ、
反復検出の閾値が狂う。JsonRepo の `rm -rf data` に対応するものがこれ。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.repo import FirestoreRepo  # noqa: E402

WID = sys.argv[1] if len(sys.argv) > 1 else "w1"
r = FirestoreRepo()
w = r._w(WID)
n = 0
for m in w.collection("months").stream():
    for e in w.collection("months").document(m.id).collection("edits").stream():
        e.reference.delete(); n += 1
    m.reference.delete(); n += 1
for x in w.collection("rules").stream():
    x.reference.delete(); n += 1
if w.get().exists:
    w.delete(); n += 1
print(f"{WID} を削除（{n}ドキュメント）")
