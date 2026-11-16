import { useEffect, useId, useRef } from 'react'
import { destinations } from '../navigation'
import Brand from './Brand'
import Icon from './Icon'
import Button from './ui/Button'

export default function MobileNavigationDrawer({ open, onOpenChange, destination, triggerRef, mainRef }) {
  const dialogRef = useRef(null)
  const closeRef = useRef(null)
  const reasonRef = useRef('dismiss')
  const headingId = useId()

  useEffect(() => {
    if (!open) return
    const dialog = dialogRef.current
    const trigger = triggerRef.current
    const main = mainRef.current
    const bodyOverflow = document.body.style.overflow
    const rootOverflow = document.documentElement.style.overflow
    const media = matchMedia('(max-width: 640px)')
    if (!media.matches) {
      onOpenChange(false)
      main?.focus({ preventScroll: true })
      return
    }
    reasonRef.current = 'dismiss'
    dialog.showModal()
    dialog.scrollTop = 0
    document.body.style.overflow = 'hidden'
    document.documentElement.style.overflow = 'hidden'
    closeRef.current.focus({ preventScroll: true })

    const resize = () => {
      if (!media.matches) {
        reasonRef.current = 'resize'
        onOpenChange(false)
      }
    }
    const navigate = () => {
      reasonRef.current = 'navigation'
      onOpenChange(false)
    }
    media.addEventListener('change', resize)
    window.addEventListener('hashchange', navigate)

    return () => {
      media.removeEventListener('change', resize)
      window.removeEventListener('hashchange', navigate)
      dialog.close()
      document.body.style.overflow = bodyOverflow
      document.documentElement.style.overflow = rootOverflow
      const focusTarget = reasonRef.current === 'navigation' || !trigger?.getClientRects().length ? main : trigger
      if (focusTarget?.isConnected) focusTarget.focus({ preventScroll: true })
    }
  }, [open, onOpenChange, triggerRef, mainRef])

  function close(reason = 'dismiss') {
    reasonRef.current = reason
    onOpenChange(false)
  }

  function handleClick(event) {
    if (event.target.closest('a[href^="#/"]')) {
      close('navigation')
    } else if (event.target === event.currentTarget) {
      const bounds = event.currentTarget.getBoundingClientRect()
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close()
    }
  }

  function handleKeyDown(event) {
    if (event.key !== 'Tab') return
    const controls = event.currentTarget.querySelectorAll('a[href], button:not(:disabled)')
    const first = controls[0]
    const last = controls[controls.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <dialog ref={dialogRef} id="mobile-navigation-drawer" className="mobile-navigation-drawer" aria-modal="true" aria-labelledby={headingId}
      onClick={handleClick} onKeyDown={handleKeyDown} onCancel={(event) => { event.preventDefault(); close() }}>
      <div className="mobile-navigation-content">
        <h2 id={headingId} className="sr-only">FinSet navigation</h2>
        <div className="mobile-navigation-header"><Brand /><Button ref={closeRef} variant="icon" icon="close" onClick={() => close()} aria-label="Close navigation" /></div>
        <p className="mobile-navigation-section-label">WORKSPACE</p>
        <nav className="mobile-primary-navigation" aria-label="Mobile primary navigation">
          {destinations.map((item) => <a key={item.id} href={`#/${item.id}`} className={`nav-link ${destination.id === item.id ? 'is-active' : ''}`} aria-current={destination.id === item.id ? 'page' : undefined}>
            <Icon name={item.icon} size={21} /><span>{item.label}</span>
            {destination.id === item.id && <i className="nav-active-dot" aria-hidden="true" />}
          </a>)}
        </nav>
      </div>
    </dialog>
  )
}
