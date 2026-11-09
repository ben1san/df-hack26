import type { Rule } from '../lib/types'

const KIND_PILL: Record<string, string> = {
  法令: 'law', ガイドライン: 'law', 反復検出: 'rep',
}

/* ルール一覧に由来が載っていれば、引き継ぎ画面は作らなくていい。
   次の師長はこれを読むだけで前任者の暗黙知を受け取る。 */
export function RulesPanel(props: {
  rules: Rule[]
  onStop: (id: string, stopped: boolean) => void
}) {
  const live = props.rules.filter(r => !r.lifecycle.stopped)
  return (
    <div className="sec">
      <h2>決まり<span className="r muted">{live.length} / {props.rules.length}本</span></h2>
      {props.rules.map(r => (
        <div className={`rule${r.lifecycle.stopped ? ' stopped' : ''}`} key={r.id}>
          <div className="lb">{r.label}</div>
          <div className="mt">
            <span className={`pill ${KIND_PILL[r.origin.kind] ?? ''}`}>{r.origin.kind}</span>
            <span className="pill">{r.strength}</span>
            {r.lifecycle.expires_on
              ? <span className="pill">{r.lifecycle.expires_on} まで</span>
              : <span className="pill">恒久</span>}
            {r.locked && <span className="pill law">解除に理由が要る</span>}
          </div>
          {r.origin.evidence && <div className="mt">{r.origin.evidence}</div>}
          <div className="mt">
            {r.origin.approved_by && <>承認 {r.origin.approved_by} {r.origin.approved_at}　</>}
            {!r.locked && (
              <span className="back"
                onClick={() => props.onStop(r.id, !r.lifecycle.stopped)}>
                {r.lifecycle.stopped ? '戻す' : '止める'}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
