import './ui.css'

export default function Badge({ children, tone = 'neutral', dot = false, className = '' }) {
  return (
    <span className={`ui-badge ui-badge--${tone} ${className}`.trim()}>
      {dot && <span className="ui-badge-dot" aria-hidden="true" />}
      {children}
    </span>
  )
}
