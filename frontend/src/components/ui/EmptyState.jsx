import { useId } from 'react'
import Icon from '../Icon'
import './ui.css'

export default function EmptyState({
  icon = 'wallet',
  title,
  description,
  children,
}) {
  const titleId = useId()

  return (
    <section className="ui-empty-state" aria-labelledby={title ? titleId : undefined}>
      <span className="ui-empty-state-icon" aria-hidden="true"><Icon name={icon} size={28} /></span>
      {title && <h3 className="ui-empty-state-title" id={titleId}>{title}</h3>}
      {description && <p className="ui-empty-state-description">{description}</p>}
      {children && <div className="ui-empty-state-content">{children}</div>}
    </section>
  )
}
