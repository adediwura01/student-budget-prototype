import './ui.css'

export default function Skeleton({ className = '', width = '100%', height = '1em' }) {
  return (
    <span
      aria-hidden="true"
      className={`ui-skeleton ${className}`.trim()}
      style={{ width, height }}
    />
  )
}
