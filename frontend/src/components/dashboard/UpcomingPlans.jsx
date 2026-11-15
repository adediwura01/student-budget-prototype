import Card from '../ui/Card'
import Icon from '../Icon'
import Badge from '../ui/Badge'
import EmptyState from '../ui/EmptyState'
import { money } from '../../finance/dashboard'

export default function UpcomingPlans({ dashboard }) {
  const { items, expectedIncome, plannedExpenses } = dashboard.plans

  return (
    <Card
      className="plans-card"
      title="Upcoming financial plans"
      description="Expected amounts, not yet confirmed."
      actions={<Badge tone="brand" dot>Planned</Badge>}
    >
      {items.length === 0 ? (
        <EmptyState icon="planning" title="No plans left this month" description="Planned income and expenses will appear here until they are confirmed." />
      ) : (
        <ul className="plan-list">
          {items.map((plan) => (
            <li key={plan.id} className="plan-row">
              <span className="plan-date"><Icon name="calendar3" size={15} />{plan.dateLabel}</span>
              <span className="plan-copy">
                <strong>{plan.name}</strong>
                <small>{plan.type === 'income' ? 'Expected income' : 'Planned expense'} · {plan.categoryName}</small>
              </span>
              <span className={`plan-amount ${plan.type === 'income' ? 'is-income' : 'is-expense'}`}>
                {plan.type === 'income' ? '+' : '−'}{money(plan.amount)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <dl className="plan-totals">
        <div><dt>Expected income</dt><dd className="is-income">{money(expectedIncome)}</dd></div>
        <div><dt>Planned expenses</dt><dd className="is-expense">{money(plannedExpenses)}</dd></div>
      </dl>
      <p className="card-note">Plans never change your balance until the transaction is confirmed.</p>
    </Card>
  )
}