import { useEffect, useRef } from 'react'
import { destinations } from '../navigation'
import Icon from './Icon'
import Brand from './Brand'
import Avatar from './ui/Avatar'
import Button from './ui/Button'
import Dropdown from './ui/Dropdown'

export default function AppLayout({ children, destination, workspaceName, appearance, notifications = [], onAppearanceChange, onPreferences, onNotify }) {
  const mainRef = useRef(null)
  const previousRoute = useRef(destination.id)
  const modes = [{ id: 'light', label: 'Light', icon: 'sun' },
    { id: 'dark', label: 'Dark', icon: 'moon' },
    { id: 'system', label: 'System', icon: 'system' }]

  useEffect(() => {
    if (previousRoute.current !== destination.id) {
      mainRef.current.focus({ preventScroll: true })
      window.scrollTo({ top: 0, behavior: 'instant' })
      previousRoute.current = destination.id
    }
    document.title = `FinSet | ${destination.label}`
  }, [destination])

  const notificationItems = notifications.map((item) => ({
    id: item.id,
    label: item.title,
    description: item.message,
    icon: 'alert',
    onSelect: () => onNotify(item.title, item.message),
  }))

  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); mainRef.current.focus({ preventScroll: true }); mainRef.current.scrollIntoView({ block: 'start' }) }}>Skip to main content</a>
    <aside className="sidebar" aria-label="Workspace sidebar">
      <Brand />
      <span className="sidebar-section-label">WORKSPACE</span>
      <nav className="main-navigation" aria-label="Primary navigation">
        {destinations.map((item) => <a key={item.id} href={`#/${item.id}`} className={`nav-link ${destination.id === item.id ? 'is-active' : ''}`} aria-current={destination.id === item.id ? 'page' : undefined} title={item.label}>
          <Icon name={item.icon} size={19} /><span>{item.label}</span>
          {destination.id === item.id && <i className="nav-active-dot" aria-hidden="true" />}
        </a>)}
      </nav>
      <div className="sidebar-spacer" />
      <div className="sidebar-note">
        <span className="sidebar-note-icon"><Icon name="info" size={18} /></span>
        <h2>Balances stay real.</h2>
        <p>Expected income and planned expenses stay separate from confirmed money.</p>
      </div>
      <button className="sidebar-profile" onClick={onPreferences} aria-label="Open workspace preferences" title="Workspace preferences">
        <Avatar name={workspaceName} initials="FW" size="sm" />
        <span className="sidebar-profile-copy"><strong>{workspaceName}</strong><small>Local prototype</small></span>
        <Icon className="sidebar-profile-chevron" name="chevron-right" size={14} />
      </button>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <div className="breadcrumb"><span>Workspace</span><Icon name="chevron-right" size={12} /><strong>{destination.label}</strong></div>
        <div className="topbar-actions">
          <Dropdown label="Change appearance" icon={modes.find((mode) => mode.id === appearance).icon}
            triggerContent={<span className="appearance-trigger-label">{modes.find((mode) => mode.id === appearance).label}</span>}
            items={modes.map((mode) => ({ ...mode, checked: appearance === mode.id, onSelect: () => onAppearanceChange(mode.id) }))} />
          {notificationItems.length > 0
            ? <Dropdown label="Budget notifications" icon="bell" items={notificationItems}
              triggerContent={<span className="notification-count">{notificationItems.length}</span>} />
            : <Button variant="icon" icon="bell" aria-label="No budget notifications" title="No budget notifications" disabled />}
          <span className="topbar-divider" />
          <Button variant="icon" className="topbar-avatar" aria-label="Edit workspace preferences" title="Workspace preferences" onClick={onPreferences}><Avatar name={workspaceName} initials="FW" size="sm" /></Button>
        </div>
      </header>
      <main ref={mainRef} id="main-content" className="main-content" tabIndex={-1}>
        {children}
        <footer className="app-footer"><span>FinSet. Money, made clear.</span><span><i /> Demo data <span className="footer-separator">/</span> NGN</span></footer>
      </main>
    </div>
    <nav className="bottom-navigation" aria-label="Mobile primary navigation">
      {destinations.map((item) => <a key={item.id} href={`#/${item.id}`} aria-label={item.label} className={destination.id === item.id ? 'is-active' : ''} aria-current={destination.id === item.id ? 'page' : undefined}>
        <Icon name={item.icon} size={20} /><span>{item.mobileLabel}</span>
      </a>)}
    </nav>
  </div>
}