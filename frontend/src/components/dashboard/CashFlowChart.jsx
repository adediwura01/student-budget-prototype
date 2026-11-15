import { useId, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import Card from '../ui/Card'
import Button from '../ui/Button'
import EmptyState from '../ui/EmptyState'
import useChartTheme from '../../hooks/useChartTheme'
import useMediaQuery from '../../hooks/useMediaQuery'
import { money, monthName } from '../../finance/dashboard'

function compactNaira(kobo) {
  const naira = kobo / 100
  if (!naira) return '₦0'
  if (naira >= 1000000) return `₦${+(naira / 1000000).toFixed(1)}m`
  if (naira >= 1000) return `₦${+(naira / 1000).toFixed(1)}k`
  return `₦${naira}`
}

function Legend() {
  return (
    <span className="chart-legend">
      <span className="chart-key"><i className="is-income" />Income</span>
      <span className="chart-key"><i className="is-expense" />Expenses</span>
    </span>
  )
}

function ChartTooltip({ active, payload }) {
  const bucket = active ? payload?.[0]?.payload : null
  if (!bucket) return null
  const net = bucket.income - bucket.expenses

  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-title">{bucket.fullLabel}</p>
      <dl className="chart-tooltip-figures">
        <div><dt><i className="is-income" />Income</dt><dd className="is-income">{money(bucket.income)}</dd></div>
        <div><dt><i className="is-expense" />Expenses</dt><dd className="is-expense">{money(bucket.expenses)}</dd></div>
        <div className="is-total"><dt>Net</dt><dd className={net < 0 ? 'is-expense' : 'is-income'}>{net < 0 ? '−' : ''}{money(Math.abs(net))}</dd></div>
      </dl>
      {bucket.income === 0 && bucket.expenses === 0 && <p className="chart-tooltip-empty">No confirmed activity</p>}
    </div>
  )
}

export default function CashFlowChart({ chart }) {
  const [showTable, setShowTable] = useState(false)
  const tableId = useId()
  const theme = useChartTheme()
  const compact = useMediaQuery('(max-width: 640px)')
  const label = monthName(chart.month)
  const summary = `Income versus expenses by week for ${label}. Total income ${money(chart.totalIncome)}. Total expenses ${money(chart.totalExpenses)}.`

  return (
    <Card
      className="chart-card"
      title="Income vs expenses"
      description="Weekly view, confirmed transactions only."
      actions={<Legend />}
    >
      {chart.hasData ? (
        <div className="chart-canvas" role="group" aria-label={summary}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart.buckets} margin={{ top: 8, right: 4, bottom: 0, left: 0 }} barCategoryGap={compact ? '10%' : '22%'} accessibilityLayer isAnimationActive={false}>
              <CartesianGrid vertical={false} stroke={theme.grid} strokeDasharray="3 4" />
              <XAxis dataKey="label" interval={0} tickLine={false} axisLine={{ stroke: theme.grid }} tickMargin={10}
                tick={{ fontSize: 11, fill: theme.axis }} />
              <YAxis domain={[0, chart.ceiling]} ticks={chart.ticks} tickFormatter={compactNaira} width={54}
                tickLine={false} axisLine={false} tickMargin={8} allowDecimals={false}
                tick={{ fontSize: 11, fill: theme.axis }} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: theme.cursor }} wrapperStyle={{ outline: 'none' }} />
              <Bar dataKey="income" name="Income" fill={theme.income} stroke={theme.income} radius={[6, 6, 2, 2]} maxBarSize={compact ? 18 : 24} barGap={4} minPointSize={3} />
              <Bar dataKey="expenses" name="Expenses" fill={theme.expense} stroke={theme.expense} radius={[6, 6, 2, 2]} maxBarSize={compact ? 18 : 24} barGap={4} minPointSize={3} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyState icon="report" title="No confirmed activity yet"
          description="Income and expenses will appear here once transactions are confirmed. Planned amounts are never charted." />
      )}
      <div className="chart-footer">
        <p className="card-note">Total in {money(chart.totalIncome)} · Total out {money(chart.totalExpenses)}</p>
        <Button variant="tertiary" icon="transactions" aria-expanded={showTable} aria-controls={tableId}
          onClick={() => setShowTable(!showTable)}>{showTable ? 'Hide table' : 'Table view'}</Button>
      </div>
      <div id={tableId} className={showTable ? 'chart-table-wrap' : 'sr-only'}>
        <table className="chart-table">
          <caption className="sr-only">Weekly income and expenses for {label}</caption>
          <thead><tr><th scope="col">Week</th><th scope="col">Income</th><th scope="col">Expenses</th></tr></thead>
          <tbody>{chart.buckets.map((bucket) => (
            <tr key={bucket.start}>
              <th scope="row">{bucket.fullLabel}</th>
              <td>{money(bucket.income)}</td>
              <td>{money(bucket.expenses)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </Card>
  )
}