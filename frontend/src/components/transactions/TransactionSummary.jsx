import Card from '../ui/Card'
import Badge from '../ui/Badge'
import Icon from '../Icon'
import { money } from '../../finance/dashboard'

const cells = [
  { key: 'income', label: 'Total income', icon: 'income', tone: 'income', note: 'Confirmed money in' },
  { key: 'expenses', label: 'Total expenses', icon: 'expense', tone: 'expense', note: 'Confirmed money out' },
  { key: 'net', label: 'Net cash flow', icon: 'wallet', tone: 'net', note: 'Income minus expenses' },
]

export default function TransactionSummary({ summary, total, filtered }) {
  const count = filtered ? `${summary.count} of ${total}` : `${summary.count} ${summary.count === 1 ? 'transaction' : 'transactions'}`

  return (
    <Card
      className="tx-summary-card"
      title="Summary"
      description={filtered ? 'Totals for the transactions currently shown.' : 'Totals for all confirmed demo transactions.'}
      actions={<Badge tone="neutral">{count}</Badge>}
    >
      <ul className="tx-summary-cells">
        {cells.map((cell) => {
          const value = cell.key === 'net' ? summary.net : summary[cell.key]
          const sign = cell.key === 'net' ? (value > 0 ? '+' : value < 0 ? '−' : '') : ''
          return (
            <li key={cell.key} className={`tx-summary-cell tx-summary-cell--${cell.tone}`}>
              <span className="tx-summary-head">
                <span className="tx-summary-icon"><Icon name={cell.icon} size={17} /></span>
                {cell.label}
              </span>
              <strong className={value < 0 ? 'is-negative' : ''}>{sign}{money(Math.abs(value), true)}</strong>
              <span className="tx-summary-note">{cell.key === 'net' && value < 0 ? 'Expenses exceed income' : cell.note}</span>
            </li>
          )
        })}
      </ul>
      <p className="card-note">The summary follows the current filters. Demo amounts are not saved to a server.</p>
    </Card>
  )
}