import { useState } from 'react'
import Card from '../ui/Card'
import Badge from '../ui/Badge'
import EmptyState from '../ui/EmptyState'
import Icon from '../Icon'
import MonthPicker from '../dashboard/MonthPicker'
import ProgressBar from '../dashboard/ProgressBar'
import { money } from '../../finance/dashboard'
import { formatTransactionDate } from '../../finance/transactions'

const tones = { 'on-track': 'success', warning: 'warning', exhausted: 'warning', over: 'danger', none: 'neutral' }

export default function BudgetPerformance({ report }) {
  const [selectedMonth, setSelectedMonth] = useState(report.budgets[0].month)
  const budget = report.budgets.find((item) => item.month === selectedMonth) ?? report.budgets[0]
  return (
    <Card className="report-budget-card" title="Budget Performance" description="Confirmed monthly spending against monthly allocations."
      actions={<MonthPicker months={report.budgets.map((item) => item.month)} value={budget.month} onChange={setSelectedMonth} label="Budget performance month" />}>
      <p className="report-budget-coverage">{budget.monthLabel}: actual spending from <strong>{formatTransactionDate(budget.from)}</strong> through <strong>{formatTransactionDate(budget.asOf)}</strong>.</p>
      <dl className="report-budget-totals">
        <div><dt>Monthly allocation</dt><dd>{money(budget.allocated, true)}</dd></div>
        <div><dt>Actual monthly spending</dt><dd>{money(budget.spent, true)}</dd></div>
        <div><dt>{budget.remaining < 0 ? 'Allocation exceeded' : 'Monthly remaining'}</dt><dd className={budget.remaining < 0 ? 'is-negative' : ''}>{money(Math.abs(budget.remaining), true)}</dd></div>
      </dl>

      {budget.categories.length ? (
        <ul className="report-budget-rows" aria-label="Monthly budget category performance">
          {budget.categories.map((category) => (
            <li key={category.budgetId} className={`report-budget-row tone-${category.tone}`}>
              <div className="report-budget-category"><span className="budget-category-icon"><Icon name={category.icon} size={17} /></span><div><strong>{category.name}</strong><Badge tone={tones[category.status]}>{category.label}</Badge></div></div>
              <dl className="report-budget-figures">
                <div><dt>Allocated</dt><dd>{money(category.allocation, true)}</dd></div>
                <div><dt>Actual spending</dt><dd>{money(category.spent, true)}</dd></div>
                <div><dt>{category.remaining < 0 ? 'Exceeded' : 'Remaining'}</dt><dd className={category.remaining < 0 ? 'is-negative' : ''}>{money(Math.abs(category.remaining), true)}</dd></div>
              </dl>
              <div className="report-budget-progress"><ProgressBar value={category.progress} tone={category.status === 'none' ? 'none' : tones[category.status]} label={category.allocation ? `${category.name}: ${Math.round(category.percent)}% of monthly allocation used` : `${category.name}: no allocation`} /><span>{category.allocation ? `${Math.round(category.percent)}% used` : 'No allocation'}</span></div>
            </li>
          ))}
        </ul>
      ) : <EmptyState icon="budget" title="No monthly allocations" description={`There are no active category budgets for ${budget.monthLabel}. Actual spending is still included in your reports.`} />}

      {budget.unbudgeted.length > 0 && (
        <div className="report-unbudgeted"><h3>Spending without an allocation</h3><ul>{budget.unbudgeted.map((category) => <li key={category.id}><span>{category.name}</span><strong>{money(category.spent, true)}</strong></li>)}</ul></div>
      )}
      <p className="card-note">Full calendar-month allocations are not prorated. A custom start date does not restart monthly spending; the selected end date sets the cutoff. Daily and weekly tracking limits are not additional budgets.</p>
    </Card>
  )
}
