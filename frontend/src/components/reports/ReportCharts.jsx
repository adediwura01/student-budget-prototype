import { useId, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import Card from '../ui/Card'
import Button from '../ui/Button'
import EmptyState from '../ui/EmptyState'
import useChartTheme from '../../hooks/useChartTheme'
import useMediaQuery from '../../hooks/useMediaQuery'
import { money } from '../../finance/dashboard'
import { formatTransactionDate } from '../../finance/transactions'

const intervalLabels = { daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly', yearly: 'Yearly' }
const axisMoney = (kobo) => new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', notation: 'compact', maximumFractionDigits: 1 }).format(kobo / 100)

function ReportTooltip({ active, payload, expensesOnly = false }) {
  const bucket = active ? payload?.[0]?.payload : null
  if (!bucket) return null
  return (
    <div className="chart-tooltip report-tooltip">
      <p className="chart-tooltip-title">{bucket.fullLabel}</p>
      {bucket.partial && <p className="report-tooltip-note">Partial period: {formatTransactionDate(bucket.start)} - {formatTransactionDate(bucket.end)}</p>}
      <dl className="chart-tooltip-figures">
        {!expensesOnly && <div><dt>Income</dt><dd>{money(bucket.income, true)}</dd></div>}
        <div><dt>Expenses</dt><dd>{money(bucket.expenses, true)}</dd></div>
        {!expensesOnly && <div className="is-total"><dt>Net cash flow</dt><dd>{money(bucket.net, true)}</dd></div>}
      </dl>
      {bucket.income === 0 && bucket.expenses === 0 && <p className="chart-tooltip-empty">No confirmed activity</p>}
    </div>
  )
}

function ReportData({ buckets, expensesOnly = false }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <div className="report-data">
      <Button variant="tertiary" icon="transactions" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
        {open ? 'Hide data' : 'View data'}
      </Button>
      <div id={id} className={open ? 'report-data-body' : 'sr-only'}>
        <ul className="report-data-list" aria-label={expensesOnly ? 'Spending trend figures' : 'Income and expense figures'}>
          {buckets.map((bucket) => (
            <li key={bucket.start}>
              <span className="report-data-period">{bucket.fullLabel}{bucket.partial && <small>Partial: {formatTransactionDate(bucket.start)} - {formatTransactionDate(bucket.end)}</small>}</span>
              <dl>
                {!expensesOnly && <div><dt>Income</dt><dd>{money(bucket.income, true)}</dd></div>}
                <div><dt>Expenses</dt><dd>{money(bucket.expenses, true)}</dd></div>
              </dl>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export function IncomeExpenses({ report }) {
  const theme = useChartTheme()
  const compact = useMediaQuery('(max-width: 640px)')
  return (
    <Card className="report-flow-card" title="Income vs Expenses"
      description={`${intervalLabels[report.flowInterval]} totals from confirmed transactions.`}
      actions={<span className="chart-legend"><span className="chart-key"><i className="is-income" />Income</span><span className="chart-key"><i className="is-expense" />Expenses</span></span>}>
      {report.summary.count > 0 ? (
        <div className="report-chart-canvas" role="group" aria-label={`Income and expenses for ${report.range.label}. Income ${money(report.summary.income, true)}, expenses ${money(report.summary.expenses, true)}.`}>
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <BarChart data={report.flow} margin={{ top: 12, right: 8, bottom: 0, left: 0 }} barCategoryGap="24%" accessibilityLayer>
              <CartesianGrid vertical={false} stroke={theme.grid} strokeDasharray="3 4" />
              <XAxis dataKey="label" interval="preserveStartEnd" minTickGap={compact ? 22 : 16} tickLine={false} axisLine={{ stroke: theme.grid }} tickMargin={10} tick={{ fontSize: 11, fill: theme.axis }} />
              <YAxis domain={[0, 'auto']} allowDecimals={false} tickCount={5} tickFormatter={axisMoney} width={58} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: theme.axis }} />
              <Tooltip content={<ReportTooltip />} cursor={{ fill: theme.cursor }} wrapperStyle={{ outline: 'none' }} />
              <Bar dataKey="income" name="Income" fill={theme.income} radius={[4, 4, 0, 0]} maxBarSize={compact ? 20 : 30} isAnimationActive={false} />
              <Bar dataKey="expenses" name="Expenses" fill={theme.expense} radius={[4, 4, 0, 0]} maxBarSize={compact ? 20 : 30} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : <EmptyState icon="report" title="No confirmed activity" description="There are no actual income or expense transactions in this range. Planned amounts are not included." />}
      <p className="card-note">Only dates within the selected range are shown. Partial periods are identified in the tooltip and data view.</p>
      <ReportData buckets={report.flow} />
    </Card>
  )
}

export function SpendingTrends({ report }) {
  const theme = useChartTheme()
  const compact = useMediaQuery('(max-width: 640px)')
  const comparison = report.comparison
  const change = comparison?.difference
  const changeLabel = change === 0 ? 'No change' : change > 0 ? 'Increase' : 'Decrease'
  return (
    <Card className="report-trends-card" title="Spending Trends" description={`${intervalLabels[report.trendInterval]} expenses across your selected range.`}>
      {report.summary.expenses > 0 ? (
        <>
          <div className="report-trend-insights">
            <div><span>Highest spending period</span><strong>{money(report.highestSpending.expenses, true)}</strong><small>{report.highestSpending.fullLabel}{report.highestSpending.partial ? ' (partial)' : ''}</small></div>
            <div><span>Latest complete-period comparison</span>
              {comparison ? <><strong>{changeLabel}{change !== 0 ? ` of ${money(Math.abs(change), true)}` : ''}</strong><small>{comparison.current.fullLabel} vs {comparison.previous.fullLabel}{comparison.percent !== null ? ` (${Math.abs(comparison.percent).toFixed(1)}%)` : '. No prior spending; percentage unavailable.'}</small></>
                : <><strong>Not enough complete periods</strong><small>Partial periods are not used for change comparisons.</small></>}
            </div>
          </div>
          <div className="report-chart-canvas report-chart-canvas--trend" role="group" aria-label={`Spending trends for ${report.range.label}. The expense axis starts at zero.`}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <LineChart data={report.trends} margin={{ top: 12, right: 12, bottom: 0, left: 0 }} accessibilityLayer>
                <CartesianGrid vertical={false} stroke={theme.grid} strokeDasharray="3 4" />
                <XAxis dataKey="label" interval="preserveStartEnd" minTickGap={compact ? 24 : 20} tickLine={false} axisLine={{ stroke: theme.grid }} tickMargin={10} tick={{ fontSize: 11, fill: theme.axis }} />
                <YAxis domain={[0, 'auto']} allowDecimals={false} tickCount={5} tickFormatter={axisMoney} width={58} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: theme.axis }} />
                <Tooltip content={<ReportTooltip expensesOnly />} cursor={{ stroke: theme.axis, strokeDasharray: '3 4' }} wrapperStyle={{ outline: 'none' }} />
                <Line type="linear" dataKey="expenses" name="Expenses" stroke={theme.expense} strokeWidth={2} dot={{ r: 3, fill: theme.expense, stroke: theme.expense }} activeDot={{ r: 5 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="card-note">A zero baseline and straight lines keep changes in proportion. Comparisons use the latest two complete {report.trendInterval === 'daily' ? 'days' : report.trendInterval === 'weekly' ? 'weeks' : report.trendInterval === 'monthly' ? 'months' : 'years'}; partial periods are not compared.</p>
        </>
      ) : <EmptyState icon="report" title="No spending in this range" description="Spending trends will appear when this period has confirmed expense transactions." />}
      <ReportData buckets={report.trends} expensesOnly />
    </Card>
  )
}
