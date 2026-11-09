import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

/* 画面には常に、次にやることが1つだけある。 */
export function Pane(props: {
  step?: string; title: string; lede?: ReactNode; children: ReactNode
  back?: string; next?: { to?: string; label: string; disabled?: boolean; onClick?: () => void }
  wide?: boolean | 'full'
}) {
  const nav = useNavigate()
  const cls = props.wide === 'full' ? 'pane full' : props.wide ? 'pane wide' : 'pane'
  return (
    <div className={cls}>
      {props.step && <div className="step">{props.step}</div>}
      <h1>{props.title}</h1>
      {props.lede && <p className="lede">{props.lede}</p>}
      {props.children}
      {(props.back || props.next) && (
        <div className="bar">
          {props.back && <span className="back" onClick={() => nav(props.back!)}>戻る</span>}
          {props.next && (
            <button className="go" disabled={props.next.disabled}
              onClick={() => {
                props.next!.onClick?.()
                if (props.next!.to) nav(props.next!.to)
              }}>{props.next.label}</button>
          )}
        </div>
      )}
    </div>
  )
}
