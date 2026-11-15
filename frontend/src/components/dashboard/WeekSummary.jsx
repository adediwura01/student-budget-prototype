import Card from '../ui/Card'
import Icon from '../Icon'
import { money } from '../../finance/dashboard'

export default function WeekSummary({ dashboard, weekStart }) {
  const week = dashboard.week
  const cells = [
    { key: 'income', label: 'Money in', icon: 'income', tone: 'success' },
    { key: 'expenses', label: 'Money out', icon: 'expense', tone: 'danger' },
    { key: 'balance', label: 'Net this week', icon: 'wallet', tone: 'brand' },
  ]

  return (
    <Card
      className="week-card"
      title="Your week in money"
      description={`${week.label} · Weeks start on ${weekStart === 7 ? 'Sunday' : 'Monday'}.`}
      actions={<Icon name="clock" size={17} className="card-note-icon" />}
    >
      <ul className="week-cells">
        {cells.map((cell) => (
          <li key={cell.key} className={`week-cell week-cell--${cell.tone}`}>
            <span className="week-cell-head"><Icon name={cell.icon} size={16} />{cell.label}</span>
            <strong>{money(week[cell.key])}</strong>
          </li>
        ))}
        <li className="week-cell week-cell--largest">
          <span className="week-cell-head"><Icon name="report" size={16} />Largest category</span>
          <strong>{week.largest ? week.largest.name : 'Nothing yet'}</strong>
          <span className="week-cell-note">{week.largest ? money(week.largest.amount) : 'No spending this week'}</span>
        </li>
      </ul>
    </Card>
  )
}