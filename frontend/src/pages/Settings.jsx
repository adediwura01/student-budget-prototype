import { useId, useState } from 'react'
import PageHeader from '../components/PageHeader'
import AppearanceSelector from '../components/AppearanceSelector'
import Modal from '../components/Modal'
import Card from '../components/ui/Card'
import Avatar from '../components/ui/Avatar'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Select from '../components/ui/Select'
import { formatTransactionDate } from '../finance/transactions'
import { notificationOptions } from '../utils/settingsPreferences'
import '../settings.css'

function NotificationPreference({ option, enabled, onChange }) {
  const id = useId()
  return (
    <div className="settings-row settings-notification-row">
      <div className="settings-row-copy"><h3 id={`${id}-title`}>{option.title}</h3><p id={`${id}-description`}>{option.description}</p></div>
      <Button variant="icon" className="settings-switch" role="switch" aria-checked={enabled} aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`}
        onClick={() => onChange(option.id, !enabled)}>
        <span className="settings-switch-track" aria-hidden="true"><span /></span>
      </Button>
    </div>
  )
}

const securityItems = [
  { title: 'Password management', description: 'Password changes require a signed-in account and authenticated account services. Neither is connected in this prototype.' },
  { title: 'Active sessions', description: 'Account sessions and sign-out controls will be available after authentication is implemented. This open demo is not an authenticated session.' },
  { title: 'Account deletion', description: 'No account-deletion action is available. A future authenticated deletion flow will require your explicit confirmation; preference changes never delete financial records.' },
]

export default function Settings({ workspace, workspaceName, appearance, resolvedTheme, appearancePersistent, preferences, onAppearanceChange, onPreferenceChange, onEditWorkspace, onRestoreDefaults }) {
  const [confirmRestore, setConfirmRestore] = useState(false)
  const appearanceLabel = `${appearance[0].toUpperCase()}${appearance.slice(1)}`

  function restoreDefaults() {
    setConfirmRestore(false)
    onRestoreDefaults()
  }

  return (
    <>
      <PageHeader eyebrow="Workspace" title="Settings" description="Manage your account, preferences and FinSet experience." />
      <div className="settings-page">
        <Card title="Profile & Account" description="Your demo identity and workspace details." actions={<Badge>Demo profile</Badge>}>
          <div className="settings-profile"><Avatar name={workspace.profile.name} /><div><h3>{workspace.profile.name}</h3><p>{workspace.profile.course}</p></div></div>
          <dl className="settings-account-details">
            <div><dt>Email address</dt><dd>Not connected</dd></div>
            <div><dt>Account status</dt><dd>No authenticated account</dd></div>
            <div><dt>Data source</dt><dd>Synthetic demo records</dd></div>
          </dl>
          <div className="settings-row settings-workspace-row"><div className="settings-row-copy"><h3>Workspace label</h3><p className="settings-workspace-name">{workspaceName}</p></div><Button variant="secondary" icon="profile" onClick={onEditWorkspace}>Edit workspace label</Button></div>
          <p className="settings-note">The sample profile is read-only. Only your workspace label can be edited for this open session; it is not saved to an account or browser storage.</p>
        </Card>

        <Card title="Appearance" description="Choose the same appearance used throughout FinSet." actions={<Badge tone={appearancePersistent ? 'brand' : 'neutral'}>{appearancePersistent ? 'This browser' : 'Session only'}</Badge>}>
          <div className="settings-appearance-options"><AppearanceSelector appearance={appearance} onChange={onAppearanceChange} /></div>
          <p className="settings-appearance-status" role="status">Selected: <strong>{appearanceLabel}</strong>{appearance === 'system' ? `. Your device currently resolves to ${resolvedTheme}.` : '. Applied immediately across FinSet.'}</p>
          <p className="settings-note">{appearancePersistent ? 'Your appearance choice is saved in this browser using the existing FinSet preference. System follows changes to your device theme.' : 'Browser storage is unavailable. Appearance still changes immediately, but this choice is only applied for this session.'}</p>
        </Card>

        <Card title="Financial Preferences" description="Supported reporting preferences, without changing your financial records." actions={<Badge>Session only</Badge>}>
          <div className="settings-row"><div className="settings-row-copy"><h3>Display currency</h3><p>All amounts use Nigerian naira. Other currencies and currency conversion are not supported.</p></div><span className="settings-currency">{'NGN (\u20A6)'}</span></div>
          <div className="settings-row settings-week-row"><div className="settings-row-copy"><h3>Reporting week</h3><p>Changes the existing weekly charts and tracking views. Monthly allocations, income, expenses and balances stay unchanged.</p></div>
            <div className="settings-week-control"><Select label="Week starts on" value={preferences.weekStart} onChange={(event) => onPreferenceChange('weekStart', Number(event.target.value))}><option value={1}>Monday</option><option value={7}>Sunday</option></Select></div>
          </div>
          <p className="settings-note">The week-start choice applies immediately and resets on refresh. Financial reporting uses the demo date, {formatTransactionDate(workspace.asOf)}.</p>
        </Card>

        <Card title="Notifications" description="Choose which alerts appear in the header while FinSet is open." actions={<Badge>In-app only</Badge>}>
          <div className="settings-notification-list">{notificationOptions.map((option) => <NotificationPreference key={option.id} option={option} enabled={preferences.notifications[option.id]} onChange={onPreferenceChange} />)}</div>
          <p className="settings-note">Changes apply immediately for this open session and reset on refresh. Alerts follow the selected workspace month and demo date. No push notifications, email or SMS are sent; planning reminders are opt-in.</p>
        </Card>

        <Card title="Privacy & Security" description="A clear view of what this prototype can and cannot manage." actions={<Badge>Account services unavailable</Badge>}>
          <div className="settings-security-list">{securityItems.map((item) => <div key={item.title} className="settings-row settings-security-row"><div className="settings-row-copy"><h3>{item.title}</h3><p>{item.description}</p></div><Badge>Unavailable</Badge></div>)}</div>
          <p className="settings-note">Only appearance is saved in browser storage when available. Credentials and sensitive account details are never stored there. Demo financial changes and other preferences are held in memory for this open session.</p>
        </Card>

        <div className="settings-defaults"><div className="settings-row-copy"><h3>Preference defaults</h3><p>Restore appearance, week-start and alert choices. Your workspace label and financial records are not affected.</p></div><Button variant="secondary" icon="refresh" onClick={() => setConfirmRestore(true)}>Restore defaults</Button></div>
      </div>

      {confirmRestore && <Modal title="Restore preference defaults?" description="Use Light appearance, start weeks on Monday, enable budget alerts and turn off planning reminders." onClose={() => setConfirmRestore(false)}>
        <p className="settings-restore-description">This only restores preferences. It does not change your workspace label, transactions, monthly budgets or plans, and it does not delete an account.</p>
        <div className="modal-actions"><Button variant="secondary" onClick={() => setConfirmRestore(false)}>Cancel</Button><Button icon="refresh" onClick={restoreDefaults}>Restore preferences</Button></div>
      </Modal>}
    </>
  )
}
