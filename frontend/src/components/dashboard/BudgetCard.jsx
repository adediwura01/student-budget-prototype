import Card from '../ui/Card'
import Badge from '../ui/Badge'
import ProgressBar from './ProgressBar'
import { money } from '../../finance/dashboard'

const tone = { 'on-track': 'success', warning: 'warning', exhausted: 'warning', over: 'danger' }
const progressTone = { 'on-track': 'success', warning: 'warning', exhausted: 'warning', over: 'danger' }

export default function BudgetCard({ dashboard }) {
  const budget = dashboard.budget
  const percent = Math.round(budget.percent)

  return (
    <Card
      className="budget-card"
      title="Monthly budget"
      description={`${dashboard.monthLabel} allocation and confirmed spending.`}
      actions={<Badge tone={tone[budget.status]}>{budget.label}</Badge>}
    >
      <p className="budget-total">{money(budget.spent)} <span>of {money(budget.allocated)}</span></p>
      <ProgressBar value={budget.progress} label={`${percent}% of monthly allocation used`} tone={progressTone[budget.status]} />
      <p className="budget-percent">{percent}% used</p>
      <dl className="budget-card-figures">
        <div><dt>Allocated</dt><dd>{money(budget.allocated)}</dd></div>
        <div><dt>Spent</dt><dd>{money(budget.spent)}</dd></div>
        <div><dt>{budget.remaining < 0 ? 'Over allocation' : 'Remaining'}</dt><dd className={budget.remaining < 0 ? 'is-negative' : ''}>{money(Math.abs(budget.remaining))}</dd></div>
      </dl>
      <p className="card-note">Monthly budgets only. Daily and weekly tracking limits are not included.</p>
    </Card>
  )
}