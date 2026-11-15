import { useEffect, useId, useRef } from 'react'
import Button from './ui/Button'

export default function Modal({ title, description, children, onClose, wide = false }) {
  const dialogRef = useRef(null)
  const headingId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const dialog = dialogRef.current
    const previouslyFocused = document.activeElement
    const overflow = document.body.style.overflow
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    return () => {
      dialog.close()
      document.body.style.overflow = overflow
      if (previouslyFocused?.isConnected) previouslyFocused.focus({ preventScroll: true })
    }
  }, [])

  return <dialog ref={dialogRef} className={`modal ${wide ? 'modal-wide' : ''}`} aria-labelledby={headingId} aria-describedby={description ? descriptionId : undefined} onCancel={(event) => { event.preventDefault(); onClose() }} onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <div className="modal-content">
      <header className="modal-header"><div><h2 id={headingId}>{title}</h2>{description && <p id={descriptionId}>{description}</p>}</div><Button variant="icon" icon="close" onClick={onClose} aria-label="Close dialog" /></header>
      {children}
    </div>
  </dialog>
}
