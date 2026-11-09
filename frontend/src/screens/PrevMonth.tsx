import { Pane } from '../components/Pane'
import { useStore } from '../lib/store'

/* 月初の連続勤務と夜勤間隔を正しく数えるには、先月の終わりが要る。 */
const TAIL = 5

export function PrevMonth() {
  const setup = useStore(s => s.setup)
  const patch = useStore(s => s.patchSetup)
  const syms = setup.kinds.map(k => k.id)

  const get = (name: string, i: number) => setup.prevTail[name]?.[i] ?? null
  const set = (name: string, i: number, v: string | null) => {
    const row = [...(setup.prevTail[name] ?? Array<string | null>(TAIL).fill(null))]
    row[i] = v
    patch({ prevTail: { ...setup.prevTail, [name]: row } })
  }
  const filled = setup.nurses.filter(n => (setup.prevTail[n.name] ?? []).some(Boolean)).length

  return (
    <Pane step="C / 5" title="先月の終わりを入れてください。" wide
      lede={<>10月27日〜31日の5日ぶんだけです。<b>月初の連勤と夜勤間隔を正しく数えるために要ります。</b></>}
      back="/setup/nurses" next={{ label: '次へ', to: '/setup/optional' }}>

      <div className="sec">
        <h2>2026年10月の終わり<span className="r muted">{filled}/{setup.nurses.length}人 入力済み</span></h2>
        <div className="scroll" style={{ maxHeight: '48vh', border: 'none', borderRadius: 0 }}>
          <table className="roster">
            <thead><tr>
              <th className="nmc">看護師</th>
              {Array.from({ length: TAIL }, (_, i) => (
                <th key={i} style={{ minWidth: 54 }}>{27 + i}<u>{['火', '水', '木', '金', '土'][i]}</u></th>
              ))}
            </tr></thead>
            <tbody>
              {setup.nurses.map(n => (
                <tr key={n.name}>
                  <td className="nmc">{n.name}</td>
                  {Array.from({ length: TAIL }, (_, i) => (
                    <td className="c" key={i} style={{ width: 54 }}>
                      <select value={get(n.name, i) ?? ''} className="cellbtn"
                        style={{ appearance: 'none', textAlign: 'center' }}
                        onChange={e => set(n.name, i, e.target.value || null)}>
                        <option value="">·</option>
                        {syms.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="box w">
        <div className="hd"><span className="ico w">!</span>空欄のままでも進めます</div>
        入れなかった人は、月初の連勤がゼロから数え直されます。<b>深夜勤が月末に入っていた人だけ入れてください。</b>
      </div>
    </Pane>
  )
}
