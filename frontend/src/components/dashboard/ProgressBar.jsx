export default function ProgressBar({ value, label, tone = 'brand' }) {
  const clamped = Math.min(100, Math.max(0, value))
  return (
    <div
      className={`progress progress--${tone}`}
      role="progressbar"
      aria-label={label}
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span style={{ width: `${clamped}%` }} />
    </div>
  )
}