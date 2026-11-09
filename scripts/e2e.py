"""HTTPで段階0→1→2→3→4を1本通す。直接importせず、必ずAPIを叩く。"""
import json, urllib.request as U
B = "http://localhost:8077"

def call(path, body=None, method=None):
    r = U.Request(B + path, method=method or ("POST" if body is not None else "GET"),
                  data=None if body is None else json.dumps(body).encode(),
                  headers={"Content-Type": "application/json"})
    with U.urlopen(r) as f: return json.load(f)

WARD = json.load(open("seed/ward.json"))
WD = ["日","月","火","水","木","金","土"]
step = lambda t: print(f"\n{'─'*62}\n{t}\n{'─'*62}")

# ── 段階0 導入
step("段階0  病棟を登録し、過去の表を取り込んで、数えて問いを出す")
w = call("/api/ward", WARD)
print(f"  法令由来を自動投入 — {', '.join(w['law_rules'])}")
im = call("/api/ward/w1/import/sample", {})
print(f"  {im['month']} の表を取り込み（{im['nurses']}人 / {im['days']}日）")

cands = call("/api/ward/w1/candidates?month=2026-10")["candidates"]
print(f"  候補 {len(cands)}問 — 選択肢の形は候補ごとに違う")
made = 0
for c in cands:
    ch = c["choices"][0]                       # いちばん控えめな側を選ぶ
    kind = {"yesno":"可否", "boundary":"境界値", "term":"期限"}[c["kind"]]
    print(f"    [{kind}] {c['question']}  → {ch['label']}")
    if ch["rule"]:
        call("/api/ward/w1/rules", {"rule": ch["rule"], "expires_on": ch.get("expires_on")})
        made += 1
print(f"  師長が書いたルール 0本 / できたルール {made}本")

# ── 段階1 夜勤を先に解く
step("段階1  二段階。夜勤を先に解く")
r = call("/api/ward/w1/month/2026-11/solve", {"stage":"night","days":30,"first_weekday":0})
print(f"  {r['status']}  {r['wall_ms']}ms   月平均夜勤時間数 {r['night_average']}h")
filled = sum(1 for row in r["proposal"].values() for c in row if c)
print(f"  埋まったセル {filled}/{12*30}  ← 残りは空白のまま画面に出る（部分的に埋まった表）")

# ── 段階2 手で直す。何も聞かれない
step("段階2  師長が直す。何も聞かれない。追記されるだけ")
for day in (6, 13, 20, 27):                      # 2026-11 の金曜
    nid = next((n for n, row in r["proposal"].items() if row[day-1] in ("準","深")), None)
    if not nid: continue
    nm = next(x["name"] for x in WARD["nurses"] if x["id"] == nid)
    e = call("/api/ward/w1/month/2026-11/edits", {"nurse_id": nid, "day": day, "to": "休"})
    print(f"  11/{day}({WD[(day-1)%7]}) {nm}  {e['edit']['from']} → {e['edit']['to']}"
          f"   棄却の累計 {e['rejected']}件")

# ── 段階1 続き 日勤を解く
step("段階1  続き。夜勤を固定して日勤・公休を解く")
r2 = call("/api/ward/w1/month/2026-11/solve", {"stage":"day","days":30,"first_weekday":0})
print(f"  {r2['status']}  {r2['wall_ms']}ms   月平均夜勤時間数 {r2['night_average']}h")

# ── 段階2 言葉で言う
step("段階2  セルを指して言う。LLMが出るのはここだけ")
t = call("/api/ward/w1/translate", {"nurse_id":"2","month":"2026-11","day":13,
        "weekday":5,"kind":"深","text":"佐藤さんは金曜の深夜勤は無理です"})
print(f"  経路 {t['route']}   候補の型 {t['draft']['type']}")
for c in t["candidates"]:
    print(f"    {c['scope']:6} {c['rule']['label']}")

# ── 段階3 範囲と期限を選んで確定
step("段階3  師長が範囲と期限を選ぶ。機械は一般化しない")
chosen = next(c for c in t["candidates"] if c["scope"] == "one")
got = call("/api/ward/w1/rules", {"rule": chosen["rule"], "expires_on": "2027-03-31"})
print(f"  確定 — {got['rule']['label']}")
print(f"    由来 {got['rule']['origin']['kind']} / {got['rule']['origin']['evidence']}")
print(f"    承認 {got['rule']['origin']['approved_by']} {got['rule']['origin']['approved_at']}"
      f" / 期限 {got['rule']['lifecycle']['expires_on']}")

# ── 不充足を出す
step("不充足  師長が「準夜勤は2名です」と答えた")
two = next(c for c in cands if c["id"] == "staff_準")["choices"][1]
call("/api/ward/w1/rules", {"rule": two["rule"]})
print(f"  選び直した — {two['label']}（{two['rule']['label']}）")
r3 = call("/api/ward/w1/month/2026-11/solve", {"stage":"night","days":30,"first_weekday":0})
print(f"  {r3['status']}  {r3['wall_ms']}ms")
for b in r3["infeasible_rules"]: print(f"    両立しない — {b['label']}")
for b in r3["relaxation"]:
    print(f"    破れ量 — 「{b['label']}」を {b['count']}件 破る必要がある")
print(f"    そのときの月平均夜勤時間数 {r3['night_average']}h（上限 72.0h）")

# ── 段階4 ルールが死ぬ
step("段階4  期限で止める。専用画面は無い")
call("/api/ward/w1/rules/%s" % got["rule"]["id"], {"stopped": True}, method="PATCH")
try:
    call("/api/ward/w1/rules/law_72", {"stopped": True}, method="PATCH")
except U.HTTPError as e:
    print(f"  法令由来は止められない — {json.load(e)['detail']}")

# ── bootstrap
step("bootstrap  画面が1回で取るもの")
b = call("/api/ward/w1/month/2026-11")
print(f"  鍵の数 K={b['n_keys']}   ルール {len(b['rules'])}本   編集ログ {len(b['edits'])}件")
print(f"  反復の候補 {len(b['repeats'])}件（閾値 "
      f"{b['repeats'][0]['threshold'] if b['repeats'] else '-'}ヶ月）")
for rp in b["repeats"][:3]:
    print(f"    {rp['streak']}/{rp['threshold']}ヶ月  {rp['evidence']}  発火={rp['fired']}")
print(f"  提案と現状が違うセル {sum(1 for n in b['current'] for i,c in enumerate(b['current'][n]) if c != (b['month']['proposal'].get(n) or [None]*30)[i])}")
