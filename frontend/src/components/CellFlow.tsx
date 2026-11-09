import { useState } from 'react'
import { SCOPE_LABEL, WD, type Rule, type Scope, type TranslateResult } from '../lib/types'

type Step = 'cell' | 'say' | 'scope' | 'term'

/* 段階2と3。モード切替は無く、表の上で全部起きる。
   セルを直すだけなら何も聞かれない。言葉にしたときだけ、ここが開く。 */
export function CellFlow(props: {
  nurseName: string; day: number; weekday: number; kind: string | null
  proposal: string | null
  onFix: (to: string | null) => void
  onTranslate: (text: string) => Promise<TranslateResult>
  onConfirm: (rule: Rule, expiresOn: string | null) => Promise<void>
  onClose: () => void
  kinds: string[]
}) {
  const [step, setStep] = useState<Step>('cell')
  const [text, setText] = useState('')
  const [res, setRes] = useState<TranslateResult | null>(null)
  const [picked, setPicked] = useState<Rule | null>(null)
  const [busy, setBusy] = useState(false)

  const head = `${props.nurseName} / ${props.day}日(${WD[props.weekday]}) / いま ${props.kind ?? '空き'}`

  async function say() {
    setBusy(true)
    try { setRes(await props.onTranslate(text)); setStep('scope') }
    finally { setBusy(false) }
  }

  async function confirm(expiresOn: string | null) {
    if (!picked) return
    setBusy(true)
    try { await props.onConfirm(picked, expiresOn); props.onClose() }
    finally { setBusy(false) }
  }

  return (
    <div className="sec">
      <h2>
        {step === 'cell' ? 'このセル' : step === 'say' ? '言葉にする' :
          step === 'scope' ? 'どこまで当てますか' : 'いつまでですか'}
        <span className="r back" onClick={props.onClose}>閉じる</span>
      </h2>
      <div className="in">
        <div className="muted" style={{ marginBottom: 12 }}>{head}</div>

        {step === 'cell' && (
          <>
            <div className="row tight" style={{ marginBottom: 12 }}>
              {props.kinds.map(k => (
                <button key={k} className={`sym k-${k}`} style={{ border: 'none', cursor: 'pointer' }}
                  onClick={() => { props.onFix(k); props.onClose() }}>{k}</button>
              ))}
              <button className="add" onClick={() => { props.onFix(null); props.onClose() }}>空ける</button>
            </div>
            <p className="muted" style={{ margin: '0 0 12px' }}>
              直すだけなら、何も聞きません。記録だけ残ります。
            </p>
            <button className="add" onClick={() => setStep('say')}>これは駄目だと伝える</button>
          </>
        )}

        {step === 'say' && (
          <>
            <input className="nm" autoFocus placeholder="例: 金曜の深夜勤はこの人には無理です"
              value={text} onChange={e => setText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && text.trim() && say()} />
            <div className="row" style={{ marginTop: 12 }}>
              <span className="back" onClick={() => setStep('cell')}>戻る</span>
              <button className="go spread" disabled={!text.trim() || busy}
                style={{ padding: '9px 22px', fontSize: 14 }} onClick={say}>
                {busy ? '読んでいます…' : '読み取る'}
              </button>
            </div>
          </>
        )}

        {step === 'scope' && res && (
          <>
            <div className="box ok" style={{ marginBottom: 12 }}>
              <div className="hd"><span className="ico ok">✓</span>{res.draft.label_ja}</div>
              <span className="muted">経路 {res.route}　型 {res.draft.type}</span>
            </div>
            <p className="muted" style={{ margin: '0 0 10px' }}>
              <b>どこまで当てるかは、こちらでは決めません。</b>選んでください。
            </p>
            <div className="side">
              {res.candidates.map(c => (
                <button key={c.scope} className="add" style={{ textAlign: 'left' }}
                  onClick={() => { setPicked(c.rule); setStep('term') }}>
                  <div style={{ fontWeight: 600 }}>{c.rule.label}</div>
                  <div className="muted">{SCOPE_LABEL[c.scope as Scope]}</div>
                </button>
              ))}
            </div>
          </>
        )}

        {step === 'term' && picked && (
          <>
            <div className="box ok" style={{ marginBottom: 12 }}>
              <div className="hd"><span className="ico ok">✓</span>{picked.label}</div>
            </div>
            <p className="muted" style={{ margin: '0 0 10px' }}>
              一時的な事情が恒久の決まりになると、理由を誰も覚えていないまま効き続けます。
            </p>
            <div className="row tight">
              <button className="add" disabled={busy} onClick={() => confirm('2027-03-31')}>
                年度末まで（2027-03-31）
              </button>
              <button className="add" disabled={busy} onClick={() => confirm('2026-12-31')}>
                今年いっぱい
              </button>
              <button className="add" disabled={busy} onClick={() => confirm(null)}>
                恒久
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
