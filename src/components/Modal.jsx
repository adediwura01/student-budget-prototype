import { useEffect, useId, useRef } from 'react'
import Icon from './Icon'

export default function Modal({ title, description, children, onClose, wide = false }) {
  const dialogRef = useRef(null)
  const headingId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const dialog = dialogRef.current
    dialog.showModal()
    return () => dialog.close()
  }, [])

  return <dialog ref={dialogRef} className={`modal ${wide ? 'modal-wide' : ''}`} aria-labelledby={headingId} aria-describedby={description ? descriptionId : undefined} onCancel={(event) => { event.preventDefault(); onClose() }} onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <div className="modal-content">
      <header className="modal-header"><div><h2 id={headingId}>{title}</h2>{description && <p id={descriptionId}>{description}</p>}</div><button className="icon-button" onClick={onClose} aria-label="Close dialog"><Icon name="close" /></button></header>
      {children}
    </div>
  </dialog>
}
