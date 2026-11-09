import { useStore } from '../lib/store'

export function Toast() {
  const note = useStore(s => s.note)
  return <div id="note" className={note ? 'on' : ''}>{note}</div>
}
