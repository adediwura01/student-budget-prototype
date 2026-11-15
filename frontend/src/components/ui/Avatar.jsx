import './ui.css'

export default function Avatar({ name = 'FinSet workspace', initials, size = 'md' }) {
  const accessibleName = String(name || 'FinSet workspace').trim() || 'FinSet workspace'
  const displayInitials = String(initials ?? '').trim() || accessibleName
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => Array.from(word)[0])
    .join('')
    .toUpperCase() || 'FW'

  return (
    <span className={`ui-avatar ui-avatar--${size}`} role="img" aria-label={accessibleName}>
      {displayInitials}
    </span>
  )
}
