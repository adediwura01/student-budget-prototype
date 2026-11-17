import { useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import Card from '../ui/Card'
import Button from '../ui/Button'
import EmptyState from '../ui/EmptyState'
import { money } from '../../finance/dashboard'

function CategoryTooltip({ active, payload }) {
  const category = active ? payload?.[0]?.payload : null
  if (!category) return null
  return <div className="chart-tooltip report-tooltip"><p className="chart-tooltip-title">{category.name}</p><strong>{money(category.amount, true)}</strong><p className="report-tooltip-note">{category.percent.toFixed(1)}% of expenses</p></div>
}

export default function SpendingCategories({ report }) {
  const [expanded, setExpanded] = useState(false)
  const grouped = report.categories.length > 6
  const visible = expanded ? report.categories : report.chartCategories
  return (
    <Card className="report-categories-card" title="Spending by Category" description="Where your confirmed expenses went.">
      {report.categories.length ? (
        <>
          <div className="report-category-chart" role="group" aria-label={`Expense distribution for ${report.range.label}. Total ${money(report.summary.expenses, true)}. The category breakdown below includes amounts and percentages.`}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <PieChart accessibilityLayer>
                <Pie data={report.chartCategories} dataKey="amount" nameKey="name" cx="50%" cy="50%" innerRadius="62%" outerRadius="88%" paddingAngle={report.chartCategories.length > 1 ? 2 : 0} stroke="var(--surface)" strokeWidth={2} isAnimationActive={false}>
                  {report.chartCategories.map((category) => <Cell key={category.id} className={`tone-${category.tone}`} fill={category.tone === 'neutral' ? 'var(--text-muted)' : 'var(--tone, var(--brand))'} />)}
                </Pie>
                <Tooltip content={<CategoryTooltip />} wrapperStyle={{ outline: 'none' }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="report-category-center" aria-hidden="true"><small>Total expenses</small><strong>{money(report.summary.expenses, true)}</strong></div>
          </div>
          <ul className="report-category-list" aria-label="Expense category breakdown">
            {visible.map((category) => (
              <li key={category.id} className={`tone-${category.tone}`}>
                <span className={`report-category-dot ${category.tone === 'neutral' ? 'report-category-dot--neutral' : ''}`} aria-hidden="true" />
                <span className="report-category-name">{category.name}</span>
                <span className="report-category-amount">{money(category.amount, true)}<small>{category.percent.toFixed(1)}%</small></span>
              </li>
            ))}
          </ul>
          {grouped && <><p className="card-note">The chart groups smaller categories into Other categories. Expand the breakdown to see every category.</p><Button variant="tertiary" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Show grouped breakdown' : `View all ${report.categories.length} categories`}</Button></>}
        </>
      ) : <EmptyState icon="expense" title="No expenses to break down" description="Only confirmed expenses appear here. Income and planned purchases are not spending." />}
    </Card>
  )
}
