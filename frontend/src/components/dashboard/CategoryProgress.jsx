import Card from '../ui/Card'
import Icon from '../Icon'
import Badge from '../ui/Badge'
import ProgressBar from './ProgressBar'
import { money } from '../../finance/dashboard'

const badge = { 'on-track': 'success', warning: 'warning', exhausted: 'warning', over: 'danger' }
const bar = { 'on-track': 'success', warning: 'warning', exhausted: 'warning', over: 'danger' }

export default function CategoryProgress({ dashboard }) {
  const categories = dashboard.budget.categories

  return (
    <Card
      className="category-card"
      title="Category budgets"
      description={`${dashboard.monthLabel} allocation and confirmed spending.`}
      actions={<a className="card-link" href="#/budgets">All budgets<Icon name="chevron-right" size={13} /></a>}
    >
      {categories.length === 0 ? <p className="card-note">No category allocations for this month.</p> : (
        <ul className="category-list">
          {categories.map((category) => (
            <li key={category.id} className={`category-row tone-${category.tone}`}>
              <span className="category-head">
                <span className="category-icon"><Icon name={category.icon} size={16} /></span>
                <span className="category-name">{category.name}</span>
                <span className="category-value">{money(category.spent)} <span>of {money(category.allocated)}</span></span>
                <Badge tone={badge[category.status]}>{category.label}</Badge>
              </span>
              <ProgressBar value={category.progress} label={`${category.name}: ${Math.round(category.percent)}% of allocation used`} tone={bar[category.status]} />
              <span className="category-foot">
                {category.remaining < 0
                  ? `${money(-category.remaining)} over allocation`
                  : `${money(category.remaining)} left`}
                <span>{Math.round(category.percent)}%</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}