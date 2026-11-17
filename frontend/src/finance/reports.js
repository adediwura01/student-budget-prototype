// Reports use the actual ledger; expectations and tracking limits are never money.
import { actualTransactions, checkedKobo, dateNumber, isoDate, monthBounds, monthName, shortDate, weekBounds } from './dashboard.js'
import { availableMonths, selectBudgets } from './budgets.js'
import { allCategories, categoryIndex, describeTransaction, formatTransactionDate, summariseTransactions, transactionTypes } from './transactions.js'

const dayMs = 86400000

export const reportRangeOptions = [
  { id: 'this-month', label: 'This Month', description: 'The current month, up to the demo date' },
  { id: 'last-month', label: 'Last Month', description: 'The previous complete calendar month' },
  { id: 'last-3-months', label: 'Last 3 Months', description: 'The current month and previous two months' },
  { id: 'custom', label: 'Custom Range', description: 'Choose an inclusive start and end date' },
]

export function resolveReportRange(asOf, preset = 'this-month', custom = {}) {
  const reference = dateNumber(asOf)
  const current = new Date(monthBounds(asOf.slice(0, 7)).start)
  const year = current.getUTCFullYear()
  const month = current.getUTCMonth()
  let from
  let to

  if (preset === 'this-month') {
    from = isoDate(current)
    to = asOf
  } else if (preset === 'last-month') {
    from = isoDate(Date.UTC(year, month - 1, 1))
    to = isoDate(current.getTime() - dayMs)
  } else if (preset === 'last-3-months') {
    from = isoDate(Date.UTC(year, month - 2, 1))
    to = asOf
  } else if (preset === 'custom') {
    from = custom.from
    to = custom.to
  } else {
    throw new RangeError('Unknown reporting period')
  }

  if (!from || !to) throw new RangeError('Choose a start and end date.')
  let start
  let end
  try {
    start = dateNumber(from)
    end = dateNumber(to)
  } catch {
    throw new RangeError('Choose valid calendar dates.')
  }
  if (start > end) throw new RangeError('Start date must be on or before end date.')
  if (end > reference) throw new RangeError(`Choose dates on or before the demo date, ${formatTransactionDate(asOf)}.`)

  return {
    preset, from, to, days: (end - start) / dayMs + 1,
    label: from === to ? formatTransactionDate(from) : `${formatTransactionDate(from)} - ${formatTransactionDate(to)}`,
  }
}

function calendarPeriod(date, interval, weekStart) {
  const start = dateNumber(date)
  if (interval === 'daily') return { start, end: start + dayMs }
  if (interval === 'weekly') return weekBounds(date, weekStart)
  if (interval === 'monthly') return monthBounds(date.slice(0, 7))
  const year = new Date(start).getUTCFullYear()
  return { start: Date.UTC(year, 0, 1), end: Date.UTC(year + 1, 0, 1) }
}

function reportBuckets(rows, range, interval, weekStart) {
  const finish = dateNumber(range.to) + dayMs
  const buckets = []
  let cursor = dateNumber(range.from)

  while (cursor < finish) {
    const period = calendarPeriod(isoDate(cursor), interval, weekStart)
    const end = Math.min(period.end, finish)
    const from = isoDate(cursor)
    const to = isoDate(end - dayMs)
    const values = summariseTransactions(rows.filter((row) => row.date >= from && row.date <= to))
    const label = interval === 'yearly' ? from.slice(0, 4)
      : interval === 'monthly' ? new Intl.DateTimeFormat('en-NG', { month: 'short', year: '2-digit', timeZone: 'UTC' }).format(cursor)
        : shortDate(from)
    const fullLabel = interval === 'monthly' ? monthName(from.slice(0, 7))
      : interval === 'yearly' ? from.slice(0, 4)
        : from === to ? formatTransactionDate(from) : `${formatTransactionDate(from)} - ${formatTransactionDate(to)}`
    buckets.push({ start: from, end: to, label, fullLabel, partial: cursor !== period.start || end !== period.end, ...values })
    cursor = end
  }

  return buckets
}

function spendingCategories(rows, index, total) {
  const grouped = new Map()
  for (const row of rows) {
    if (row.type !== 'expense') continue
    const category = index.get(row.category)
    const id = category?.id ?? 'uncategorised'
    const current = grouped.get(id) ?? {
      id, name: category?.name ?? 'Uncategorised', icon: category?.icon ?? 'expense', tone: category?.tone ?? 'purple', amount: 0,
    }
    grouped.set(id, { ...current, amount: checkedKobo(current.amount + row.amount) })
  }
  return [...grouped.values()]
    .map((category) => ({ ...category, percent: total ? category.amount / total * 100 : 0 }))
    .sort((a, b) => b.amount - a.amount || a.name.localeCompare(b.name))
}

export function selectReports(workspace, selection) {
  const range = resolveReportRange(workspace.asOf, selection.preset, selection)
  // The ledger currently defines only income and expense. Never reinterpret transfers.
  const actual = actualTransactions(workspace.transactions.filter((row) => transactionTypes.includes(row.type)), range.to)
  const rows = actual.filter((row) => row.date >= range.from && row.date <= range.to)
  const summary = summariseTransactions(rows)
  const index = categoryIndex(allCategories(workspace))
  const categories = spendingCategories(rows, index, summary.expenses)
  const chartCategories = categories.length <= 6 ? categories : [
    ...categories.slice(0, 5),
    {
      id: 'report-other', name: 'Other categories', tone: 'neutral', icon: 'expense', grouped: true,
      amount: categories.slice(5).reduce((total, category) => checkedKobo(total + category.amount), 0),
      percent: categories.slice(5).reduce((total, category) => total + category.percent, 0),
    },
  ]

  const firstMonth = range.from.slice(0, 7)
  const lastMonth = range.to.slice(0, 7)
  const monthCount = (Number(lastMonth.slice(0, 4)) - Number(firstMonth.slice(0, 4))) * 12 + Number(lastMonth.slice(5)) - Number(firstMonth.slice(5)) + 1
  const flowInterval = range.days <= 31 ? 'weekly' : monthCount <= 24 ? 'monthly' : 'yearly'
  const trendInterval = range.days <= 31 ? 'daily' : range.days <= 93 ? 'weekly' : monthCount <= 24 ? 'monthly' : 'yearly'
  const flow = reportBuckets(rows, range, flowInterval, workspace.profile.weekStart)
  const trends = reportBuckets(rows, range, trendInterval, workspace.profile.weekStart)
  const complete = trends.filter((bucket) => !bucket.partial)
  const latest = complete.at(-1)
  const previous = complete.at(-2)
  const difference = latest && previous ? checkedKobo(latest.expenses - previous.expenses) : null
  const comparison = difference === null ? null : {
    current: latest, previous, difference,
    percent: previous.expenses ? difference / previous.expenses * 100 : null,
  }

  const budgetMonths = [...new Set([lastMonth, ...availableMonths(workspace).filter((month) => month >= firstMonth && month <= lastMonth)])].sort().reverse()
  // A custom start does not reset a monthly allocation. Use month-to-date spending
  // through the report's end date, and expose that coverage separately in the UI.
  const budgetWorkspace = { ...workspace, asOf: range.to, transactions: actual }
  const knownCategories = new Set(workspace.categories.map((category) => category.id))
  const budgets = budgetMonths.map((month) => {
    const budget = selectBudgets(budgetWorkspace, month)
    const unknown = actual.filter((row) => row.type === 'expense' && row.date.startsWith(`${month}-`) && !knownCategories.has(row.category))
    if (unknown.length) budget.unbudgeted = [...budget.unbudgeted, { id: 'uncategorised', name: 'Uncategorised', spent: summariseTransactions(unknown).expenses }]
    return { ...budget, from: `${month}-01` }
  })

  return {
    range, summary, categories, chartCategories, flow, flowInterval, trends, trendInterval, comparison, budgets,
    highestSpending: trends.reduce((highest, bucket) => !highest || bucket.expenses > highest.expenses ? bucket : highest, null),
    transactions: [...rows].sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id)).map((row) => describeTransaction(row, index)),
  }
}
