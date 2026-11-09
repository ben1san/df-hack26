import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Pane } from '../components/Pane'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import type { Ward } from '../lib/types'

/* 入れさせないことを明示する画面。他社製品が設定で入れさせているものを、ここで断る。 */
const SKIPPED = [
  ['シフト交換', '確定した表の配布以降は、いまの業務のままにします'],
  ['休暇の承認', '同じ理由で持ちません'],
  ['勤務表の公開', '配布の方法は変えません'],
  ['希望休の収集画面', 'V1は師長が代行入力します。紙でもExcelでも構いません'],
  ['重みの数値', '「絶対・強く・できれば」の3段階に写します。桁を手で積む必要はありません'],
]

export function Optional() {
  const nav = useNavigate()
  const setup = useStore(s => s.setup)
  const notify = useStore(s => s.notify)
  const [busy, setBusy] = useState(false)

  /* ここで病棟を登録し、過去の表を取り込む。次の画面が、その表を数えて問いを出す。 */
  async function register() {
    setBusy(true)
    try {
      const ward: Ward = {
        id: 'w1',
        name: setup.wardName || '3階東病棟',
        shift_kinds: setup.kinds,
        nurses: setup.nurses.map((n, i) => ({
          id: String(i + 1), name: n.name, qual: n.qual, groups: [],
        })),
        night_band_start: setup.nightBandStart,
        night_average_cap: 72,
        day_groups: {},
      }
      await api.putWard(ward)
      const r = await api.importSample()
      notify(`${r.month} の表を取り込みました（${r.nurses}人 / ${r.days}日）`)
      nav('/setup/derive')
    } catch (e) {
      notify(`登録できませんでした — ${(e as Error).message}`)
    } finally { setBusy(false) }
  }

  return (
    <Pane step="D / 5" title="ここは入れなくて大丈夫です。" wide
      lede={<>他の製品が設定を求めるもののうち、<b>こちらが持たないと決めたもの</b>です。</>}
      back="/setup/prev"
      next={{ label: busy ? '取り込んでいます…' : '決まりの候補を見る', disabled: busy, onClick: register }}>

      <div className="sec"><h2>持たないもの</h2>
        {SKIPPED.map(([k, why]) => (
          <div className="rule" key={k}>
            <div className="lb">{k}</div>
            <div className="mt">{why}</div>
          </div>
        ))}
      </div>

      <div className="note">
        <h3>なぜ書いてあるのか</h3>
        <p>
          入れさせないことを決めたのも設計です。<b>あとから足せます。</b>
          足すのが高いものだけ先に決めてあり、これらは全部あとから安く足せる側にあります。
        </p>
      </div>
    </Pane>
  )
}
