import Card from '../ui/Card'
import Badge from '../ui/Badge'
import ProgressBar from '../dashboard/ProgressBar'
import { money } from '../../finance/dashboard'

const badgeTone = { 'on-track': 'success', warning: 'warning', exhausted: 'warning', over: 'danger', none: 'neutral' }
const barTone = { 'on-track': 'success', warning: 'warning', exhausted: 'warning', over: 'danger', none: 'none' }

export default function BudgetOverview({ budget }) {
  const remainingLabel = budget.remaining < 0 ? 'Over budget' : 'Remaining'
  const budgetedSpent = budget.categories.reduce((total, category) => total + category.spent, 0)
  const unbudgeted = budget.spent - budgetedSpent
  const budgetedPercent = budget.allocated ? Math.round(budgetedSpent / budget.allocated * 100) : 0

  return (
    <Card
      className="budget-overview-card"
      title={`${budget.monthLabel} budget`}
      description="Confirmed expenses against category allocations."
      actions={<Badge tone={badgeTone[budget.status]}>{budget.label}</Badge>}
    >
      <div className="budget-overview-figures">
        <div className="budget-overview-figure">
          <span>Allocated</span>
          <strong>{money(budget.allocated, true)}</strong>
          <small>Across {budget.categories.length} {budget.categories.length === 1 ? 'category' : 'categories'}</small>
        </div>
        <div className="budget-overview-figure">
          <span>Spent</span>
          <strong>{money(budget.spent, true)}</strong>
          <small>{unbudgeted > 0 ? `${money(unbudgeted, true)} in unbudgeted categories` : 'Confirmed expenses'}</small>
        </div>
        <div className={`budget-overview-figure ${budget.remaining < 0 ? 'is-negative' : ''}`}>
          <span>{remainingLabel}</span>
          <strong>{budget.remaining < 0 ? '−' : ''}{money(Math.abs(budget.remaining), true)}</strong>
          <small>{budget.remaining < 0 ? 'Spending exceeds allocation' : 'Available to spend'}</small>
        </div>
      </div>

      <div className="budget-overview-progress">
        <div className="budget-progress-head">
          <span>{budget.allocated ? `${budgetedPercent}% of allocation used` : 'No allocation'}</span>
          <span>{budget.allocated ? `${money(budgetedSpent, true)} of ${money(budget.allocated, true)} allocated-category spending` : 'Add an allocation to start tracking'}</span>
        </div>
        <ProgressBar
          value={budget.progress}
          label={budget.allocated ? `${budgetedPercent}% of allocated-category spending used` : 'No monthly allocation'}
          tone={barTone[budget.status]}
        />
      </div>

      <p className="card-note">
        Monthly allocations only; daily and weekly limits are not included.
        {unbudgeted > 0 && ` Includes ${money(unbudgeted, true)} of confirmed spending in categories without an allocation.`}
      </p>
    </Card>
  )
}