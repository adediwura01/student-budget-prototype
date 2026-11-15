import Card from '../ui/Card'
import Badge from '../ui/Badge'
import Icon from '../Icon'
import { money } from '../../finance/dashboard'

function Figure({ tone, icon, label, value, note, negative = false }) {
  return (
    <li className={`plan-overview-figure plan-overview-figure--${tone}`}>
      <span className="plan-overview-head">
        <span className="plan-overview-icon"><Icon name={icon} size={16} /></span>
        {label}
      </span>
      <strong className={negative ? 'is-negative' : ''}>{value}</strong>
      <small>{note}</small>
    </li>
  )
}

export default function PlanOverview({ plan }) {
  const difference = plan.projected
  const differenceLabel = `${difference < 0 ? '−' : ''}${money(Math.abs(difference), true)}`
  const differenceNote = difference < 0
    ? 'Planned expenses exceed expected income'
    : difference === 0
      ? 'Expected income matches planned expenses'
      : 'Expected income is higher than planned expenses'

  return (
    <Card
      className="plan-overview-card"
      title="Plan overview"
      description={`Expected and planned amounts for ${plan.monthLabel}. Nothing here is confirmed money yet.`}
      actions={<Badge tone="brand" dot>Planned</Badge>}
    >
      <ul className="plan-overview-figures">
        <Figure
          tone="income"
          icon="income"
          label="Expected income"
          value={money(plan.expectedIncome, true)}
          note={`${plan.pending.filter((row) => row.type === 'income').length} pending ${plan.pending.filter((row) => row.type === 'income').length === 1 ? 'plan' : 'plans'}`}
        />
        <Figure
          tone="expense"
          icon="expense"
          label="Planned expenses"
          value={money(plan.plannedExpenses, true)}
          note={`${plan.pending.filter((row) => row.type === 'expense').length} pending ${plan.pending.filter((row) => row.type === 'expense').length === 1 ? 'plan' : 'plans'}`}
        />
        <Figure
          tone={difference < 0 ? 'expense' : 'income'}
          icon={difference < 0 ? 'alert' : 'piggy-bank'}
          label="Projected difference"
          value={differenceLabel}
          note={differenceNote}
          negative={difference < 0}
        />
      </ul>

      <ul className="plan-overview-counts">
        <li>
          <span className="plan-count-icon"><Icon name="calendar3" size={17} /></span>
          <span className="plan-count-copy">
            <small>Upcoming plans</small>
            <strong>{plan.upcomingCount}</strong>
            <small>Expected after {plan.asOfLabel}</small>
          </span>
        </li>
        <li className={plan.needsAttentionCount > 0 ? 'has-attention' : ''}>
          <span className="plan-count-icon"><Icon name={plan.needsAttentionCount > 0 ? 'alert' : 'check'} size={17} /></span>
          <span className="plan-count-copy">
            <small>Needs attention</small>
            <strong>{plan.needsAttentionCount}</strong>
            <small>{plan.needsAttentionCount > 0 ? `Due on or before ${plan.asOfLabel}` : 'Nothing overdue'}</small>
          </span>
        </li>
      </ul>

      <p className="card-note">
        {plan.confirmedCount > 0
          ? `${plan.confirmedCount} ${plan.confirmedCount === 1 ? 'plan' : 'plans'} confirmed this month: ${money(plan.confirmedIncome, true)} received and ${money(plan.confirmedExpenses, true)} paid. Those amounts are already counted as actual transactions.`
          : 'Plans never change your balance. Confirming a plan is the only step that creates a real transaction.'}
      </p>
    </Card>
  )
}