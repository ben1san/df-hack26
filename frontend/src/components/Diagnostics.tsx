import { useState } from 'react'
import type { Death, Repeat, Rule, SolveResult } from '../lib/types'
import { SCOPE_LABEL, WD } from '../lib/types'

/* 不充足は「両立しない対」ではなく「どれだけ破れば通るか」で出す。
   最小不充足集合は実測で9本中9本返ったので、headline に使えない。 */
export function UnsatBox(props: { unsat: SolveResult; onRetry: () => void }) {
  const { unsat } = props
  return (
    <div className="box c">
      <div className="hd"><span className="ico c">!</span>この決まりでは表が作れません</div>
      {unsat.relaxation.length > 0 ? (
        <>
          <p style={{ margin: '0 0 8px' }}>どれかを諦める必要があります。</p>
          <ul style={{ margin: '0 0 8px', paddingLeft: 19 }}>
            {unsat.relaxation.map(b => (
              <li key={b.rule_id}>
                <b>{b.label}</b> を {b.detail ?? `${b.count}件`} 破る
              </li>
            ))}
          </ul>
          {unsat.night_average != null && (
            <p style={{ margin: 0 }}>
              そうすると月平均夜勤時間数は <b>{unsat.night_average} 時間</b>（上限 72.0 時間）。
            </p>
          )}
        </>
      ) : (
        <p style={{ margin: 0 }}>原因を特定できませんでした（{unsat.status}）。</p>
      )}
      <div className="row" style={{ marginTop: 10 }}>
        <span className="back" onClick={props.onRetry}>もう一度解く</span>
      </div>
    </div>
  )
}

/* 1回目と2回目は黙る。沈黙を挟むから反復に意味が出る。
   出すのは事実だけ。範囲（この人だけ／この曜日全体／全員）も期限も師長が選ぶ。 */
export function RepeatBox(props: {
  repeat: Repeat
  onConfirm: (rule: Rule, expiresOn: string | null) => Promise<void>
  onDismiss: () => void
}) {
  const r = props.repeat
  const [step, setStep] = useState<'fact' | 'scope' | 'term'>('fact')
  const [picked, setPicked] = useState<Rule | null>(null)
  const [busy, setBusy] = useState(false)

  async function confirm(expiresOn: string | null) {
    if (!picked) return
    setBusy(true)
    try { await props.onConfirm(picked, expiresOn) } finally { setBusy(false) }
  }

  return (
    <div className="box w">
      <div className="hd"><span className="ico w">!</span>
        {r.nurse} の{WD[r.weekday]}曜の{r.kind}
      </div>

      {step === 'fact' && (
        <>
          <p style={{ margin: '0 0 8px' }}>{r.evidence}。<b>毎回同じ理由ですか。</b></p>
          <p className="muted" style={{ margin: '0 0 10px' }}>
            {r.streak}/{r.threshold} ヶ月。閾値はこの病棟の手修正の量から計算しています
            （固定値ではありません）。
          </p>
          <div className="row tight">
            <button className="add" onClick={() => setStep('scope')}>はい、決まりにする</button>
            <span className="back" onClick={props.onDismiss}>いまは違う</span>
          </div>
        </>
      )}

      {step === 'scope' && (
        <>
          <p style={{ margin: '0 0 10px' }}>
            <b>どこまで当てますか。</b>こちらでは決めません。
          </p>
          <div className="side">
            {r.candidates.map(c => (
              <button key={c.scope} className="add" style={{ textAlign: 'left' }}
                onClick={() => { setPicked(c.rule); setStep('term') }}>
                <div style={{ fontWeight: 600 }}>{c.rule.label}</div>
                <div className="muted">{SCOPE_LABEL[c.scope]}</div>
              </button>
            ))}
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <span className="back" onClick={() => setStep('fact')}>戻る</span>
          </div>
        </>
      )}

      {step === 'term' && picked && (
        <>
          <p style={{ margin: '0 0 6px' }}><b>{picked.label}</b></p>
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
            <button className="add" disabled={busy} onClick={() => confirm(null)}>恒久</button>
            <span className="back" onClick={() => setStep('scope')}>戻る</span>
          </div>
        </>
      )}
    </div>
  )
}

/* 月送りの副作用。専用画面に置くと、置いた時点で死ぬ。 */
export function DeathBox(props: { deaths: Death[]; onRevive: (id: string) => void }) {
  return (
    <div className="box w">
      <div className="hd"><span className="ico w">!</span>
        {props.deaths.length}本の決まりが止まりました
      </div>
      <ul style={{ margin: '0 0 8px', paddingLeft: 19 }}>
        {props.deaths.map(d => (
          <li key={d.rule_id}>
            {d.label}（{d.why}）
            <span className="back" style={{ marginLeft: 8 }}
              onClick={() => props.onRevive(d.rule_id)}>延ばす</span>
          </li>
        ))}
      </ul>
      <p className="muted" style={{ margin: 0 }}>
        止まったぶんは、表の上でも変わっています。
      </p>
    </div>
  )
}
