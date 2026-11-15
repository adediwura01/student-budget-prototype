import Icon from '../Icon'
import Button from './Button'
import './ui.css'

export default function Toast({ title, message, tone = 'success', onClose }) {
  const icon = tone === 'success' ? 'check' : tone === 'danger' ? 'alert' : 'info'

  return (
    <div
      className={`ui-toast ui-toast--${tone}`}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      onKeyDown={(event) => {
        if (event.key === 'Escape' && onClose) {
          event.preventDefault()
          event.stopPropagation()
          onClose()
        }
      }}
    >
      <span className="ui-toast-icon" aria-hidden="true"><Icon name={icon} size={20} /></span>
      <div className="ui-toast-body">
        {title && <p className="ui-toast-title">{title}</p>}
        {message != null && <p className="ui-toast-message">{message}</p>}
      </div>
      {onClose && (
        <Button variant="icon" icon="close" onClick={onClose} aria-label="Dismiss notification" />
      )}
    </div>
  )
}
