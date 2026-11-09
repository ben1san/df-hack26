import { Pane } from '../components/Pane'
import { useStore } from '../lib/store'
import type { ShiftKind } from '../lib/types'

/* 3交代の既定を入れておく。おたくのものに直してもらう。 */
export function WardSetup() {
  const setup = useStore(s => s.setup)
  const patch = useStore(s => s.patchSetup)

  const setKind = (i: number, p: Partial<ShiftKind>) =>
    patch({ kinds: setup.kinds.map((k, j) => (j === i ? { ...k, ...p } : k)) })

  return (
    <Pane step="A / 5" title="病棟と、勤務の種類。" wide
      lede={<>3交代の既定を入れてあります。<b>おたくのものに直してください。</b></>}
      back="/" next={{ label: '次へ', to: '/setup/nurses', disabled: !setup.wardName.trim() }}>

      <div className="sec"><h2>病棟の名前</h2><div className="in">
        <input className="nm" style={{ maxWidth: 360, fontSize: 16, padding: '11px 14px' }}
          placeholder="3階東病棟" value={setup.wardName}
          onChange={e => patch({ wardName: e.target.value })} />
      </div></div>

      <div className="sec">
        <h2>勤務の種類<span className="r muted">{setup.kinds.length}種</span></h2>
        <div className="kh">
          <div>記号</div><div>名前</div><div className="r">拘束</div>
          <div className="r">うち夜勤</div><div>休み</div><div>人員</div><div />
        </div>
        {setup.kinds.map((k, i) => (
          <div className={`kr${k.is_off ? ' off' : ''}`} key={i}>
            <input className="symin" value={k.id} maxLength={2}
              onChange={e => setKind(i, { id: e.target.value })} />
            <input className="nm" value={k.name} onChange={e => setKind(i, { name: e.target.value })} />
            <input className="n2" type="number" step="0.5" value={k.hours}
              onChange={e => setKind(i, { hours: +e.target.value })} />
            <input className="n2" type="number" step="0.5" value={k.night_hours}
              disabled={k.is_off}
              onChange={e => setKind(i, { night_hours: +e.target.value })} />
            <input className="ck" type="checkbox" checked={k.is_off}
              onChange={e => setKind(i, { is_off: e.target.checked, night_hours: 0 })} />
            <input className="ck" type="checkbox" checked={k.counts_as_staff}
              onChange={e => setKind(i, { counts_as_staff: e.target.checked })} />
            <button className="del" title="消す"
              onClick={() => patch({ kinds: setup.kinds.filter((_, j) => j !== i) })}>×</button>
          </div>
        ))}
        <div className="in">
          <button className="add" onClick={() => patch({
            kinds: [...setup.kinds, {
              id: '', name: '', hours: 8, night_hours: 0,
              crosses_midnight: false, is_off: false, counts_as_staff: true,
            }],
          })}>種類を足す</button>
        </div>
      </div>

      <div className="sec"><h2>夜勤時間帯</h2><div className="in">
        <div className="row">
          <span className="muted">22時〜翌5時を含む連続16時間の範囲で、病院が定めます。</span>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <span>開始</span>
          <div className="num">
            <button onClick={() => patch({ nightBandStart: Math.max(0, setup.nightBandStart - 1) })}>−</button>
            <input value={setup.nightBandStart} readOnly />
            <button onClick={() => patch({ nightBandStart: Math.min(22, setup.nightBandStart + 1) })}>＋</button>
          </div>
          <span className="muted">時 〜 翌 {(setup.nightBandStart + 16) % 24} 時</span>
          <span className={`ok ${setup.nightBandStart <= 22 && setup.nightBandStart + 16 >= 29 ? 'good' : 'bad'}`}>
            {setup.nightBandStart <= 22 && setup.nightBandStart + 16 >= 29 ? '22〜5時を含む' : '22〜5時を含まない'}
          </span>
        </div>
      </div></div>

      <div className="sec"><h2>様式9</h2><div className="in">
        <div className="y9">
          <label>
            <input type="checkbox" checked={setup.youshiki9}
              onChange={e => patch({ youshiki9: e.target.checked })} />
            様式9の形で出力する
          </label>
          <span className="muted">全国一律なので、こちらで固定の形を持ちます。</span>
        </div>
      </div></div>
    </Pane>
  )
}
