import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RosterTable } from '../components/RosterTable'
import { RulesPanel } from '../components/RulesPanel'
import { CellFlow } from '../components/CellFlow'
import { DeathBox, RepeatBox, UnsatBox } from '../components/Diagnostics'
import { api } from '../lib/api'
import { useStore, weekdayOf } from '../lib/store'

const daysIn = (m: string) => {
  const [y, mo] = m.split('-').map(Number)
  return new Date(y!, mo!, 0).getDate()
}
const firstWeekday = (m: string) => {
  const [y, mo] = m.split('-').map(Number)
  return new Date(y!, mo! - 1, 1).getDay()
}
const shift = (m: string, by: number) => {
  const [y, mo] = m.split('-').map(Number)
  const d = new Date(y!, mo! - 1 + by, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

/* 画面は3枚しかない。段階1・2・3・4がこの1枚に乗る。
   段階を切り替えるボタンは置かない。 */
export function Roster() {
  const nav = useNavigate()
  const s = useStore()
  const [sel, setSel] = useState<{ nurseId: string; day: number } | null>(null)
  const [hidden, setHidden] = useState<string[]>([])
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!s.booted) s.boot().catch(() => setFailed(true))
  }, [s.booted, s])

  if (failed) {
    return (
      <div className="pane">
        <h1>病棟がまだありません。</h1>
        <p className="lede">先に導入を済ませてください。</p>
        <div className="bar"><button className="go" onClick={() => nav('/')}>はじめから</button></div>
      </div>
    )
  }
  if (!s.ward || !s.monthData) {
    return <div className="pane"><p className="lede">読み込んでいます…</p></div>
  }

  const ward = s.ward
  const nurse = (id: string) => ward.nurses.find(n => n.id === id)?.name ?? id
  const key = (r: { nurse_id: string; weekday: number; kind_id: string }) =>
    `${r.nurse_id}-${r.weekday}-${r.kind_id}`
  const fired = s.repeats.filter(r => r.fired && !r.answered && !hidden.includes(key(r)))
  const nightFilled = Object.values(s.current).some(row => row.some(c => c))

  return (
    <div className="pane full">
      <div className="row" style={{ marginBottom: 14 }}>
        <h1 style={{ margin: 0 }}>{ward.name}</h1>
        <div className="row tight spread">
          <span className="back" onClick={() => {
            const m = shift(s.month, -1)
            s.goMonth(m, daysIn(m), firstWeekday(m))
          }}>← 前の月</span>
          <span className="chip on">{s.month}</span>
          <span className="back" onClick={() => {
            const m = shift(s.month, 1)
            s.goMonth(m, daysIn(m), firstWeekday(m))
          }}>次の月 →</span>
        </div>
      </div>

      <div className="row" style={{ marginBottom: 14 }}>
        <button className="go" style={{ padding: '10px 22px', fontSize: 14, marginLeft: 0 }}
          disabled={s.solving}
          onClick={() => s.solve('night', { days: daysIn(s.month), first_weekday: firstWeekday(s.month) })}>
          {s.solving ? '解いています…' : '夜勤を解く'}
        </button>
        <button className="add" disabled={s.solving || !nightFilled}
          onClick={() => s.solve('day', { days: daysIn(s.month), first_weekday: firstWeekday(s.month) })}>
          日勤と公休を解く
        </button>
        {s.nightAverage != null && (
          <span className={`ok ${s.nightAverage > 72 ? 'bad' : 'good'}`}>
            月平均夜勤時間数 {s.nightAverage}h / 72.0h
          </span>
        )}
        <span className="muted spread">
          手修正 {s.edits.length}件　鍵の数 {s.nKeys}
        </span>
      </div>

      {s.unsat && <UnsatBox unsat={s.unsat} onRetry={() =>
        s.solve('night', { days: daysIn(s.month), first_weekday: firstWeekday(s.month) })} />}
      {s.deaths.length > 0 && <DeathBox deaths={s.deaths}
        onRevive={id => s.stopRule(id, false)} />}
      {fired.map(r => (
        <RepeatBox key={key(r)} repeat={r}
          onConfirm={(rule, exp) => s.confirm(rule, exp)}
          onDismiss={() => setHidden(h => [...h, key(r)])} />
      ))}

      <div className="grid2">
        <RosterTable ward={ward} month={s.monthData} rules={s.rules}
          proposal={s.proposal} current={s.current} selected={sel}
          onCell={(nurseId, day) => setSel({ nurseId, day })} />

        <div className="side">
          {sel && (
            <CellFlow
              nurseName={nurse(sel.nurseId)}
              day={sel.day}
              weekday={weekdayOf(s.monthData, sel.day)}
              kind={s.current[sel.nurseId]?.[sel.day - 1] ?? null}
              proposal={s.proposal[sel.nurseId]?.[sel.day - 1] ?? null}
              kinds={ward.shift_kinds.map(k => k.id)}
              onFix={to => s.edit(sel.nurseId, sel.day, to).catch(() => {})}
              onTranslate={text => api.translate({
                nurse_id: sel.nurseId, month: s.month, day: sel.day,
                weekday: weekdayOf(s.monthData, sel.day),
                kind: s.current[sel.nurseId]?.[sel.day - 1] ?? '日', text,
              })}
              onConfirm={(rule, exp) => s.confirm(rule, exp)}
              onClose={() => setSel(null)}
            />
          )}
          <RulesPanel rules={s.rules} onStop={(id, stopped) => s.stopRule(id, stopped)} />
        </div>
      </div>
    </div>
  )
}
