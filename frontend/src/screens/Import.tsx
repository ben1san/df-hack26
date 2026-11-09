import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Pane } from '../components/Pane'
import { useStore } from '../lib/store'

/* 空白から始めない。最初の1枚は師長が自分で作った先月の表。 */
export function Import() {
  const nav = useNavigate()
  const patch = useStore(s => s.patchSetup)
  const notify = useStore(s => s.notify)
  const [file, setFile] = useState<string | null>(null)
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const take = (name: string) => {
    setFile(name)
    patch({ importedMonth: '2026-10' })
  }

  return (
    <Pane step="はじめに" title="いつも使っている勤務表を、1つ入れてください。"
      lede={<>新しく作る必要はありません。<b>先月のもの、そのままで構いません。</b></>}
      next={{ label: '次へ', disabled: !file, to: '/setup/ward' }}>

      <div className={`drop${over ? ' over' : ''}`}
        onClick={() => input.current?.click()}
        onDragOver={e => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={e => {
          e.preventDefault(); setOver(false)
          const f = e.dataTransfer.files[0]
          if (f) take(f.name)
        }}>
        <div className="big">{file ?? 'ここに Excel か CSV を置いてください'}</div>
        <div className="muted">{file ? '読み取りました' : 'クリックして選ぶこともできます'}</div>
        <input ref={input} type="file" accept=".xlsx,.xls,.csv" hidden
          onChange={e => { const f = e.target.files?.[0]; if (f) take(f.name) }} />
      </div>

      {file && (
        <div className="box ok">
          <div className="hd"><span className="ico ok">✓</span>2026年10月の表として読みました</div>
          12人 / 31日。<b>この表を数えて、決まりの候補をこちらから出します。</b>
          師長が決まりを書く必要はありません。
        </div>
      )}

      <div className="note">
        <h3>持っていない場合</h3>
        <p>
          手元に無くても進められます。
          <span className="back" style={{ marginLeft: 6 }}
            onClick={() => { take('（見本の表）'); notify('見本の表で進めます'); nav('/setup/ward') }}>
            見本の表で進む
          </span>
        </p>
      </div>
    </Pane>
  )
}
