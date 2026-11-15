import Icon from '../Icon'
import './ui.css'

export default function Button({
  variant = 'primary',
  type = 'button',
  icon,
  children,
  loading = false,
  disabled = false,
  className = '',
  ...props
}) {
  return (
    <button
      {...props}
      type={type}
      className={`ui-button ui-button--${variant} ${className}`.trim()}
      disabled={disabled || loading}
      aria-busy={loading ? true : props['aria-busy']}
    >
      {loading ? (
        <span className="ui-button-spinner" aria-hidden="true" />
      ) : icon ? (
        <Icon name={icon} size={18} className="ui-button-icon" />
      ) : null}
      {children}
    </button>
  )
}
