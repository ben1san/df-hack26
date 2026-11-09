import { useEffect } from 'react'
import { Pane } from '../components/Pane'
import { useStore } from '../lib/store'

const SEED = [
  ['田中 美咲', '主任'], ['佐藤 恵', '正'], ['鈴木 彩', '正'], ['高橋 理恵', '正'],
  ['伊藤 奈美', '正'], ['渡辺 真由', '正'], ['山本 由紀', '正'], ['中村 さくら', '准'],
  ['小林 千尋', '准'], ['加藤 瑞希', '正'], ['吉田 遥', '新人'], ['山田 杏', '新人'],
] as const

export function NurseList() {
  const setup = useStore(s => s.setup)
  const patch = useStore(s => s.patchSetup)

  /* 取り込んだ表から読めている。空白から始めない */
  useEffect(() => {
    if (!setup.nurses.length) {
      patch({ nurses: SEED.map(([name, qual]) => ({ name, qual })) })
    }
  }, [setup.nurses.length, patch])

  const quals = [...new Set(setup.nurses.map(n => n.qual))].filter(Boolean)
  const set = (i: number, p: Partial<{ name: string; qual: string }>) =>
    patch({ nurses: setup.nurses.map((n, j) => (j === i ? { ...n, ...p } : n)) })

  return (
    <Pane step="B / 5" title="看護師の名簿を入れてください。" wide
      lede={<>取り込んだ表から<b>{setup.nurses.length}人</b>読めました。足りなければ足してください。</>}
      back="/setup/ward"
      next={{ label: '次へ', to: '/setup/prev', disabled: setup.nurses.length < 2 }}>

      <div className="sec">
        <h2>名簿<span className="r muted">{setup.nurses.length}人</span></h2>
        <div className="nh"><div className="idx">#</div><div>名前</div><div>資格</div><div /></div>
        {setup.nurses.map((n, i) => (
          <div className="nr" key={i}>
            <div className="idx">{i + 1}</div>
            <input className="nm" value={n.name} onChange={e => set(i, { name: e.target.value })} />
            <input className="nm" value={n.qual} onChange={e => set(i, { qual: e.target.value })} />
            <button className="del"
              onClick={() => patch({ nurses: setup.nurses.filter((_, j) => j !== i) })}>×</button>
          </div>
        ))}
        <div className="in">
          <button className="add"
            onClick={() => patch({ nurses: [...setup.nurses, { name: '', qual: '正' }] })}>
            看護師を足す
          </button>
        </div>
      </div>

      <div className="sec"><h2>見つかった区分</h2><div className="in">
        <div className="row tight">
          {quals.map(q => (
            <span className="chip on" key={q}>
              {q}　{setup.nurses.filter(n => n.qual === q).length}人
            </span>
          ))}
        </div>
        <p className="muted" style={{ marginTop: 10, marginBottom: 0 }}>
          この区分で「人数の決まり」を書けます。汎用の製品に無い区分があっても構いません。
        </p>
      </div></div>
    </Pane>
  )
}
