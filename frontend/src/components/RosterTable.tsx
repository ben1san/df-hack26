import { nightHours, perDay, weekdayOf } from '../lib/store'
import { WD, type Grid, type Month, type Rule, type Ward } from '../lib/types'

/* 集計行は装飾ではなく、段階2の構成要素。
   手修正で人数が足りなくなったことを、問いかけずに事実だけ動かして伝える。 */
function minimums(rules: Rule[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const r of rules) {
    if (r.type !== 'staffing' || r.lifecycle.stopped || r.at_least == null) continue
    for (const k of r.shifts.ids ?? []) out[k] = Math.max(out[k] ?? 0, r.at_least)
  }
  return out
}

export function RosterTable(props: {
  ward: Ward; month: Month; proposal: Grid; current: Grid; rules: Rule[]
  selected: { nurseId: string; day: number } | null
  onCell: (nurseId: string, day: number) => void
}) {
  const { ward, month, proposal, current } = props
  const days = Array.from({ length: month.days }, (_, i) => i + 1)
  const mins = minimums(props.rules)
  const counted = ward.shift_kinds.filter(k => k.night_hours > 0)
  const offKind = ward.shift_kinds.find(k => k.is_off)

  return (
    <div className="scroll">
      <table className="roster">
        <thead>
          <tr>
            <th className="nmc">看護師</th>
            {days.map(d => {
              const w = weekdayOf(month, d)
              return (
                <th key={d} className={w === 0 || w === 6 ? 'we' : undefined}>
                  {d}<u>{WD[w]}</u>
                </th>
              )
            })}
            {counted.map(k => <th className="sumh" key={k.id}>{k.name}</th>)}
            <th className="sumh">公休</th>
          </tr>
        </thead>
        <tbody>
          {ward.nurses.map(n => (
            <tr key={n.id}>
              <td className="nmc">{n.name}</td>
              {days.map(d => {
                const w = weekdayOf(month, d)
                const cur = current[n.id]?.[d - 1] ?? null
                const prop = proposal[n.id]?.[d - 1] ?? null
                const rejected = !!prop && prop !== cur
                const sel = props.selected?.nurseId === n.id && props.selected.day === d
                return (
                  <td className={`c${w === 0 || w === 6 ? ' we' : ''}`} key={d}>
                    <button
                      className={`cellbtn${cur ? ` k-${cur}` : ''}${rejected ? ' rej' : ''}${sel ? ' sel' : ''}`}
                      title={rejected ? `ソルバの提案は ${prop}。直されています` : undefined}
                      onClick={() => props.onCell(n.id, d)}>
                      {cur ?? ''}
                    </button>
                  </td>
                )
              })}
              {counted.map(k => (
                <td className="sum" key={k.id}>
                  {(current[n.id] ?? []).filter(c => c === k.id).length}
                </td>
              ))}
              <td className="sum">
                {offKind ? (current[n.id] ?? []).filter(c => c === offKind.id).length : 0}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          {counted.map(k => (
            <tr key={k.id}>
              <td className="nmc">{k.name}</td>
              {days.map(d => {
                const c = perDay(ward, current, d, k.id)
                const need = mins[k.id]
                return (
                  <td key={d} className={need != null && c < need ? 'bad' : undefined}>{c}</td>
                )
              })}
              {counted.map(x => <td className="sum" key={x.id} />)}
              <td className="sum" />
            </tr>
          ))}
          <tr>
            <td className="nmc">夜勤時間</td>
            <td colSpan={month.days}>
              <div className="row" style={{ justifyContent: 'center', gap: 14, fontSize: 11 }}>
                {ward.nurses.map(n => (
                  <span key={n.id}>
                    {n.name.split(' ')[0]} {nightHours(ward, current, n.id).toFixed(0)}h
                  </span>
                ))}
              </div>
            </td>
            {counted.map(x => <td className="sum" key={x.id} />)}
            <td className="sum" />
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
