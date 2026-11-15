import Card from '../ui/Card'
import Icon from '../Icon'
import { money } from '../../finance/dashboard'

const cells = [
  { key: 'balance', label: 'Balance', icon: 'wallet', tone: 'brand', note: 'All confirmed activity' },
  { key: 'income', label: 'Money in', icon: 'income', tone: 'success', note: 'Confirmed income' },
  { key: 'expenses', label: 'Money out', icon: 'expense', tone: 'danger', note: 'Confirmed expenses' },
]

export default function SummaryCards({ dashboard }) {
  return (
    <Card
      className="summary-card"
      title="Your money this month"
      description={`Confirmed transactions up to ${dashboard.asOfLabel}.`}
    >
      <ul className="summary-cells">
        {cells.map((cell) => (
          <li key={cell.key} className={`summary-cell summary-cell--${cell.tone}`}>
            <span className="summary-cell-head">
              <span className="summary-cell-icon"><Icon name={cell.icon} size={17} /></span>
              <span>{cell.label}</span>
            </span>
            <strong className="summary-cell-value">{money(dashboard.money[cell.key])}</strong>
            <span className="summary-cell-note">{cell.note}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}