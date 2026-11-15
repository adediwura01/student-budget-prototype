import Card from '../ui/Card'
import Icon from '../Icon'
import { money } from '../../finance/dashboard'

const groups = [
  {
    key: 'approaching',
    title: 'Approaching limit',
    icon: 'alert',
    tone: 'warning',
    rows: (budget) => budget.categories.filter((category) => category.status === 'warning'),
    metric: (category) => `${Math.round(category.percent)}% used`,
  },
  {
    key: 'exceeded',
    title: 'Exceeded',
    icon: 'alert',
    tone: 'danger',
    rows: (budget) => budget.categories.filter((category) => category.status === 'over'),
    metric: (category) => `${money(-category.remaining, true)} over`,
  },
  {
    key: 'remaining',
    title: 'Remaining funds',
    icon: 'check',
    tone: 'success',
    rows: (budget) => budget.categories.filter((category) => category.remaining > 0),
    metric: (category) => `${money(category.remaining, true)} left`,
  },
  {
    key: 'none',
    title: 'No spending',
    icon: 'clock',
    tone: 'neutral',
    rows: (budget) => budget.categories.filter((category) => category.spent === 0),
    metric: () => 'No spending yet',
  },
]

export default function BudgetInsights({ budget }) {
  if (budget.categories.length === 0) {
    return (
      <Card className="budget-insights-card" title="Budget insights" description="Factual signals from this month's allocations.">
        <p className="card-note">No allocations to inspect for {budget.monthLabel}.</p>
      </Card>
    )
  }

  return (
    <Card className="budget-insights-card" title="Budget insights" description="Factual signals from this month's allocations and confirmed spending.">
      <div className="budget-insight-grid">
        {groups.map((group) => {
          const rows = group.rows(budget)
          return (
            <section key={group.key} className={`budget-insight budget-insight--${group.tone}`}>
              <h3 className="budget-insight-title">
                <span className="budget-insight-icon"><Icon name={group.icon} size={15} /></span>
                {group.title}
                <span className="budget-insight-count">{rows.length}</span>
              </h3>
              {rows.length === 0 ? (
                <p className="budget-insight-empty">None</p>
              ) : (
                <ul className="budget-insight-list">
                  {rows.map((category) => (
                    <li key={category.budgetId} className="budget-insight-item">
                      <span>{category.name}</span>
                      <small>{group.metric(category)}</small>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )
        })}
      </div>

      {budget.unbudgeted.length > 0 && (
        <p className="card-note">
          Unbudgeted spending: {budget.unbudgeted.map((category) => `${category.name} ${money(category.spent, true)}`).join(' · ')}.
        </p>
      )}
    </Card>
  )
}