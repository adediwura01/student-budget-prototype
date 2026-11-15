import Card from '../ui/Card'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import EmptyState from '../ui/EmptyState'
import Icon from '../Icon'
import ProgressBar from '../dashboard/ProgressBar'
import { money } from '../../finance/dashboard'

const badgeTone = { 'on-track': 'success', warning: 'warning', exhausted: 'warning', over: 'danger', none: 'neutral' }
const barTone = { 'on-track': 'success', warning: 'warning', exhausted: 'warning', over: 'danger', none: 'none' }

function Figure({ label, value, negative = false }) {
  return (
    <span className="budget-figure">
      <small>{label}</small>
      <strong className={negative ? 'is-negative' : ''}>{value}</strong>
    </span>
  )
}

export default function BudgetCategories({ budget, onCreate, onEdit, onRemove }) {
  return (
    <Card
      className="budget-categories-card"
      title="Category budgets"
      description={`${budget.monthLabel} allocations and confirmed spending.`}
      actions={<Button variant="secondary" icon="plus" onClick={onCreate}>New budget</Button>}
    >
      {budget.categories.length === 0 ? (
        <EmptyState
          icon="budget"
          title="No allocations yet"
          description={`Create a monthly allocation to start tracking spending for ${budget.monthLabel}.`}
        >
          <Button icon="plus" onClick={onCreate}>New budget</Button>
        </EmptyState>
      ) : (
        <>
          <div className="budget-table-head" aria-hidden="true">
            <span>Category</span>
            <span>Allocated</span>
            <span>Spent</span>
            <span>Remaining</span>
            <span>Progress</span>
            <span className="sr-only">Actions</span>
          </div>
          <ul className="budget-rows">
            {budget.categories.map((category) => (
              <li key={category.budgetId} className={`budget-row tone-${category.tone}`}>
                <span className="budget-category">
                  <span className="budget-category-icon"><Icon name={category.icon} size={17} /></span>
                  <span className="budget-category-copy">
                    <span className="budget-category-name">
                      {category.name}
                      <Badge tone={badgeTone[category.status]}>{category.label}</Badge>
                    </span>
                    {category.note && <small>{category.note}</small>}
                  </span>
                </span>

                <span className="budget-figures">
                  <Figure label="Allocated" value={money(category.allocation, true)} />
                  <Figure label="Spent" value={money(category.spent, true)} />
                  <Figure
                    label={category.remaining < 0 ? 'Over' : 'Remaining'}
                    value={`${category.remaining < 0 ? '−' : ''}${money(Math.abs(category.remaining), true)}`}
                    negative={category.remaining < 0}
                  />
                </span>

                <span className="budget-progress-cell">
                  <ProgressBar
                    value={category.progress}
                    label={category.allocation ? `${category.name}: ${Math.round(category.percent)}% of allocation used` : `${category.name}: no allocation`}
                    tone={barTone[category.status]}
                  />
                  <span className="budget-progress-label">
                    {category.allocation ? `${Math.round(category.percent)}% used` : 'No allocation'}
                  </span>
                </span>

                <span className="budget-actions">
                  <Button variant="tertiary" onClick={() => onEdit({ ...category, category: category.id })} aria-label={`Edit ${category.name} budget`}>Edit</Button>
                  <Button variant="tertiary" className="budget-remove-action" onClick={() => onRemove(category)} aria-label={`Remove ${category.name} budget`}>Remove</Button>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}