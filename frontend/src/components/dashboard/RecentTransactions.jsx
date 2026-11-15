import Card from '../ui/Card'
import Icon from '../Icon'
import EmptyState from '../ui/EmptyState'
import { money } from '../../finance/dashboard'

export default function RecentTransactions({ dashboard }) {
  return (
    <Card
      className="transactions-card"
      title="Recent transactions"
      description={`Latest confirmed activity in ${dashboard.monthLabel}.`}
      actions={<a className="card-link" href="#/transactions">View all<Icon name="chevron-right" size={13} /></a>}
    >
      {dashboard.recent.length === 0 ? (
        <EmptyState icon="transactions" title="No transactions yet" description="Confirmed income and expenses will appear here." />
      ) : (
        <ul className="tx-list">
          {dashboard.recent.map((row) => (
            <li key={row.id} className="tx-row">
              <span className={`tx-icon tone-${row.type === 'income' ? 'green' : 'lavender'}`}><Icon name={row.icon} size={17} /></span>
              <span className="tx-copy">
                <strong>{row.name}</strong>
                <small>{row.categoryName} · {row.dateLabel}</small>
              </span>
              <span className={`tx-amount ${row.type === 'income' ? 'is-income' : 'is-expense'}`}>
                {row.type === 'income' ? '+' : '−'}{money(row.amount)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}