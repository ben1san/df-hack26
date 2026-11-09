import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { QKIND_LABEL, type Candidate, type Choice } from '../lib/types'

/* 段階0。師長はルールを1本も書かないまま、初期ルールセットを持って段階1に入る。

   一度に多く聞かない。1画面1問。
   そして候補ごとに選択肢の形が違う — 可否 / 境界の値 / いつまで。
   答えは最後まで溜める。途中では何も作らない。 */
export function Derive() {
  const nav = useNavigate()
  const boot = useStore(s => s.boot)
  const notify = useStore(s => s.notify)
  const [cands, setCands] = useState<Candidate[] | null>(null)
  const [i, setI] = useState(0)
  const [answers, setAnswers] = useState<Record<string, Choice>>({})
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.candidates('2026-10')
      .then(r => setCands(r.candidates))
      .catch(e => setErr((e as Error).message))
  }, [])

  if (err) {
    return (
      <div className="pane">
        <h1>過去の表がまだありません。</h1>
        <p className="lede">{err}</p>
        <div className="bar"><button className="go" onClick={() => nav('/')}>はじめから</button></div>
      </div>
    )
  }
  if (!cands) return <div className="pane"><p className="lede">表を数えています…</p></div>

  const done = i >= cands.length
  const c = cands[i]
  const chosen = Object.values(answers).filter(a => a.rule)

  async function finish() {
    setBusy(true)
    try {
      for (const a of chosen) {
        if (a.rule) await api.confirmRule(a.rule, a.expires_on)
      }
      await boot('2026-11')
      notify(`${chosen.length}本の決まりができました`)
      nav('/roster')
    } catch (e) {
      notify(`確定できませんでした — ${(e as Error).message}`)
    } finally { setBusy(false) }
  }

  return (
    <div className="pane">
      <div className="step">
        {done ? 'E / 5　確認' : `E / 5　${i + 1} / ${cands.length} 問目`}
      </div>

      {!done && c ? (
        <>
          <h1>{c.question}</h1>
          <p className="lede">
            <b>{c.evidence}</b>　— 数えただけです。判断はしていません。
          </p>

          <div className="side">
            {c.choices.map((ch, j) => (
              <button key={j} className="add" style={{ textAlign: 'left', padding: '13px 16px' }}
                onClick={() => {
                  setAnswers(a => ({ ...a, [c.id]: ch }))
                  setI(i + 1)
                }}>
                <div style={{ fontWeight: 600, fontSize: 15 }}>{ch.label}</div>
                {ch.rule && (
                  <div className="muted">
                    {ch.rule.label}
                    {ch.expires_on && ` — ${ch.expires_on} まで`}
                    {ch.rule.strength !== '絶対' && `（${ch.rule.strength}）`}
                  </div>
                )}
              </button>
            ))}
          </div>

          <div className="bar">
            {i > 0 && <span className="back" onClick={() => setI(i - 1)}>ひとつ戻る</span>}
            <span className="muted spread">{QKIND_LABEL[c.kind]}を聞いています</span>
          </div>
        </>
      ) : (
        <>
          <h1>{chosen.length}本の決まりができます。</h1>
          <p className="lede">
            <b>師長は1本も書いていません。</b>過去の表を数えて、答えてもらっただけです。
          </p>
          <div className="sec">
            <h2>決まり<span className="r muted">{chosen.length}本</span></h2>
            {chosen.map((a, j) => (
              <div className="rule" key={j}>
                <div className="lb">{a.rule!.label}</div>
                <div className="mt">
                  <span className="pill">段階0逆算</span>
                  <span className="pill">{a.rule!.strength}</span>
                  <span className="pill">{a.expires_on ? `${a.expires_on} まで` : '恒久'}</span>
                </div>
                <div className="mt">{a.rule!.origin.evidence}</div>
              </div>
            ))}
            {!chosen.length && (
              <div className="in muted">1本も選ばれていません。このまま進めます。</div>
            )}
          </div>
          <div className="note">
            <h3>このあと</h3>
            <p>
              足りない決まりは、表を直しているうちに出てきます。
              <b>いま全部決める必要はありません。</b>
            </p>
          </div>
          <div className="bar">
            <span className="back" onClick={() => setI(cands.length - 1)}>ひとつ戻る</span>
            <button className="go" disabled={busy} onClick={finish}>
              {busy ? '作っています…' : '表を作る'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
