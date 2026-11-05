import { useRef } from 'react'
import { monthLabel } from '../utils/finance'
import Icon from './Icon'

const navigation = [
  { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
  { id: 'transactions', label: 'Transactions', icon: 'transactions' },
  { id: 'income', label: 'Income', icon: 'income' },
  { id: 'expenses', label: 'Expenses', icon: 'expense' },
  { id: 'budgets', label: 'Budgets', icon: 'budget' },
  { id: 'reports', label: 'Reports', icon: 'report' },
]

function Sidebar({ profile, onNavigate, onClose }) {
  const initials = profile.name.split(' ').filter(Boolean).map((word) => word[0]).slice(0, 2).join('')
  return <aside className="sidebar">
    <div className="sidebar-brand-row">
      <button className="brand" onClick={() => onNavigate('dashboard')} aria-label="Student Budget dashboard">
        <span className="brand-mark"><Icon name="logo" size={26} /></span>
        <span className="brand-name">student<span>budget & expense tracker</span></span>
      </button>
      {onClose && <button className="icon-button mobile-close" onClick={onClose} aria-label="Close navigation"><Icon name="close" /></button>}
    </div>
    <div className="nav-label">YOUR WORKSPACE</div>
    <nav className="main-navigation" aria-label="Main navigation">
      {navigation.map((item) => <button key={item.id} className={`nav-button ${item.id === 'dashboard' ? 'is-active' : ''}`} aria-current={item.id === 'dashboard' ? 'page' : undefined} onClick={() => onNavigate(item.id)}>
        <Icon name={item.icon} size={19} /><span>{item.label}</span>{item.id === 'dashboard' && <span className="nav-active-dot" />}
      </button>)}
    </nav>
    <div className="nav-divider" />
    <nav className="main-navigation secondary-navigation" aria-label="Personal navigation">
      <button className="nav-button" onClick={() => onNavigate('profile')}><Icon name="profile" size={19} /><span>Profile</span></button>
      <button className="nav-button" onClick={() => onNavigate('settings')}><Icon name="settings" size={19} /><span>Settings</span></button>
    </nav>
    <div className="sidebar-bottom">
      <div className="sidebar-tip">
        <div className="tip-illustration" aria-hidden="true"><span className="tip-orbit" /><span className="tip-coin"><Icon name="graduation" size={30} /></span><Icon className="tip-spark" name="spark" size={17} /></div>
        <h3>A little planning.<br />A lot less stressing.</h3>
        <p>Make room for the things<br />that matter to you.</p>
        <button className="tip-link" onClick={() => onNavigate('tips')}>A little money wisdom <Icon name="arrow" size={15} /></button>
      </div>
      <button className="sidebar-profile" onClick={() => onNavigate('profile')}>
        <span className="avatar">{initials}</span><span><strong>{profile.name}</strong><small>Personal workspace</small></span><Icon name="chevron" size={16} />
      </button>
    </div>
  </aside>
}

export default function AppLayout({ children, month, months, onMonthChange, profile, onNavigate, hasNotifications }) {
  const navigationRef = useRef(null)
  const initials = profile.name.split(' ').filter(Boolean).map((word) => word[0]).slice(0, 2).join('')
  const navigate = (destination) => {
    navigationRef.current?.close()
    onNavigate(destination)
  }

  return <>
    <a className="skip-link" href="#main-content">Skip to dashboard</a>
    <div className="app-shell">
      <div className="desktop-sidebar"><Sidebar profile={profile} onNavigate={onNavigate} /></div>
      <main className="main-content" id="main-content">
        <header className="welcome-header">
          <div className="welcome-copy">
            <button className="icon-button mobile-menu-button" onClick={() => navigationRef.current.showModal()} aria-label="Open navigation"><Icon name="menu" /></button>
            <div><div className="welcome-eyebrow"><span /> YOUR MONEY, YOUR WAY</div><h1>Welcome back, {profile.name.split(' ')[0]} <span className="welcome-spark"><Icon name="spark" size={23} /></span></h1><p>A little clarity for your everyday student life.</p></div>
          </div>
          <div className="header-actions">
            <label className="month-selector"><Icon name="calendar" size={17} /><span className="sr-only">Dashboard month</span><select value={month} onChange={(event) => onMonthChange(event.target.value)}>{months.map((value) => <option key={value} value={value}>{monthLabel(value)}</option>)}</select><Icon name="chevron" size={15} /></label>
            <button className="icon-button notification-button" onClick={() => onNavigate('notifications')} aria-label="Notifications"> <Icon name="bell" size={20} />{hasNotifications && <span className="notification-dot" />}</button>
            <span className="header-divider" />
            <button className="header-profile" onClick={() => onNavigate('profile')} aria-label={`Open profile for ${profile.name}`}><span className="avatar">{initials}</span><Icon name="chevron" size={14} /></button>
          </div>
        </header>
        {children}
        <footer className="app-footer"><span><Icon name="graduation" size={16} /> Made for student life.</span><span><i /> Demo workspace <span className="footer-separator">/</span> USD</span></footer>
      </main>
    </div>
    <dialog ref={navigationRef} className="mobile-navigation-dialog" aria-label="Navigation" onClick={(event) => { if (event.target === event.currentTarget) navigationRef.current.close() }}>
      <Sidebar profile={profile} onNavigate={navigate} onClose={() => navigationRef.current.close()} />
    </dialog>
  </>
}
