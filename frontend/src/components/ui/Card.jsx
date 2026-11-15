import { useId } from 'react'
import './ui.css'

export default function Card({ children, title, description, actions, className = '', ...props }) {
  const titleId = useId()

  return (
    <section
      {...props}
      className={`ui-card ${className}`.trim()}
      aria-labelledby={props['aria-labelledby'] ?? (title && !props['aria-label'] ? titleId : undefined)}
    >
      {(title || description || actions) && (
        <header className="ui-card-header">
          {(title || description) && (
            <div className="ui-card-heading">
              {title && <h2 className="ui-card-title" id={titleId}>{title}</h2>}
              {description && <p className="ui-card-description">{description}</p>}
            </div>
          )}
          {actions && <div className="ui-card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
