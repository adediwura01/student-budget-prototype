// Pure frontend selectors. Plans and tracking limits never enter actual totals.
const dayMs = 86400000

export function dateNumber(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new TypeError('Expected an ISO calendar date')
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) throw new RangeError('Invalid calendar date')
  return date.getTime()
}

export function isoDate(value) { return new Date(value).toISOString().slice(0, 10) }

export function checkedKobo(value, positive = false) {
  if (!Number.isSafeInteger(value) || positive && value < 1) throw new TypeError('Money must be safe integer kobo')
  return value
}

function sum(rows, key) {
  return rows.reduce((total, row) => checkedKobo(total + checkedKobo(row[key], true)), 0)
}

export function money(kobo, decimals = false) {
  checkedKobo(kobo)
  return new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', minimumFractionDigits: decimals ? 2 : 0, maximumFractionDigits: decimals ? 2 : 0 }).format(kobo / 100)
}

export function shortDate(date) {
  return new Intl.DateTimeFormat('en-NG', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(dateNumber(date))
}

export function monthName(month) {
  return new Intl.DateTimeFormat('en-NG', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(dateNumber(`${month}-01`))
}

export function monthBounds(month) {
  const start = dateNumber(`${month}-01`)
  const date = new Date(start)
  const end = Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 1)
  return { start, end }
}

export function weekBounds(date, weekStart = 1) {
  if (![1, 7].includes(weekStart)) throw new RangeError('Week starts on Monday or Sunday')
  const anchor = dateNumber(date)
  const weekday = new Date(anchor).getUTCDay()
  const start = anchor - ((weekday - (weekStart === 7 ? 0 : 1) + 7) % 7) * dayMs
  return { start, end: start + 7 * dayMs }
}

export function actualTransactions(rows, asOf) {
  const cutoff = dateNumber(asOf)
  return rows.filter((row) => {
    if (row.confirmed !== true || row.deleted) return false
    if (!['income', 'expense'].includes(row.type)) throw new TypeError('Invalid transaction type')
    checkedKobo(row.amount, true)
    return dateNumber(row.date) <= cutoff
  })
}

function totals(rows) {
  const income = sum(rows.filter((row) => row.type === 'income'), 'amount')
  const expenses = sum(rows.filter((row) => row.type === 'expense'), 'amount')
  return { income, expenses, balance: checkedKobo(income - expenses) }
}

export function budgetState(spent, allocated) {
  checkedKobo(spent)
  checkedKobo(allocated)
  if (!allocated) return { percent: 0, progress: 0, status: 'none', label: 'No allocation' }
  const percent = spent / allocated * 100
  return { percent, progress: Math.min(100, Math.max(0, percent)),
    status: spent > allocated ? 'over' : spent === allocated ? 'exhausted' : percent >= 80 ? 'warning' : 'on-track',
    label: spent > allocated ? 'Over budget' : spent === allocated ? 'Fully used' : percent >= 80 ? 'Getting close' : 'On track' }
}

function niceScale(maximum) {
  if (!Number.isSafeInteger(maximum) || maximum <= 0) return { ceiling: 1000000, ticks: [0, 250000, 500000, 750000, 1000000] }
  const rough = maximum / 4
  const power = Math.max(1, 10 ** Math.floor(Math.log10(rough)))
  const step = [1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10].map((entry) => Math.round(entry * power)).find((entry) => entry >= rough)
  const ceiling = Math.ceil(maximum / step) * step
  const ticks = []
  for (let value = 0; value <= ceiling; value += step) ticks.push(value)
  return { ceiling, ticks }
}

function dayOfMonth(value) { return new Date(value).getUTCDate() }

function cashFlow(rows, month, weekStart) {
  const { start, end } = monthBounds(month)
  const buckets = []
  let cursor = start
  while (cursor < end) {
    const week = weekBounds(isoDate(cursor), weekStart)
    const finish = Math.min(week.end, end)
    const values = totals(rows.filter((row) => dateNumber(row.date) >= cursor && dateNumber(row.date) < finish))
    const first = dayOfMonth(isoDate(cursor))
    const last = dayOfMonth(isoDate(finish - dayMs))
    const label = first === last ? String(first) : `${first}–${last}`
    buckets.push({ start: isoDate(cursor), end: isoDate(finish - dayMs), label, fullLabel: `${label} ${monthName(month).slice(0, 3)}`, ...values })
    cursor = finish
  }
  const scale = niceScale(Math.max(0, ...buckets.flatMap((bucket) => [bucket.income, bucket.expenses])))
  const values = totals(rows)
  return {
    month, weekStart, buckets, ticks: scale.ticks, ceiling: scale.ceiling,
    hasData: rows.length > 0, totalIncome: values.income, totalExpenses: values.expenses,
  }
}

export function selectDashboard(workspace, month, weekStart = workspace.profile.weekStart) {
  const { start, end } = monthBounds(month)
  const reference = dateNumber(workspace.asOf)
  const cutoff = Math.min(reference, end - dayMs)
  const asOf = isoDate(cutoff)
  const actual = actualTransactions(workspace.transactions, asOf)
  const monthly = actual.filter((row) => dateNumber(row.date) >= start && dateNumber(row.date) < end)
  const monthlyTotals = totals(monthly)
  const balance = totals(actual).balance
  const budgets = workspace.monthlyBudgets.filter((row) => row.month === month && !row.archived)
  const allocated = sum(budgets, 'allocation')
  const categories = budgets.map((row) => {
    const category = workspace.categories.find((item) => item.id === row.category)
    if (!category) throw new TypeError('Unknown budget category')
    const spent = sum(monthly.filter((item) => item.type === 'expense' && item.category === row.category), 'amount')
    return { ...category, allocated: row.allocation, spent, remaining: row.allocation - spent, ...budgetState(spent, row.allocation) }
  })
  const pending = workspace.plans.filter((plan) => plan.status === 'pending' && dateNumber(plan.date) >= cutoff && plan.date.startsWith(`${month}-`)).map((plan) => {
    if (!['income', 'expense'].includes(plan.type)) throw new TypeError('Invalid plan type')
    checkedKobo(plan.amount, true)
    return { ...plan, categoryName: workspace.categories.find((item) => item.id === plan.category)?.name ?? 'Income', dateLabel: shortDate(plan.date) }
  }).sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id))
  const week = weekBounds(asOf, weekStart)
  const weekly = actual.filter((row) => dateNumber(row.date) >= week.start && dateNumber(row.date) < week.end)
  const weeklyTotals = totals(weekly)
  const largest = workspace.categories.map((category) => ({ ...category, amount: sum(weekly.filter((row) => row.type === 'expense' && row.category === category.id), 'amount') })).sort((a, b) => b.amount - a.amount)[0]
  const transactions = [...monthly].sort((a, b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id)).map((row) => ({ ...row,
    categoryName: workspace.categories.find((category) => category.id === row.category)?.name ?? 'Income',
    icon: row.type === 'income' ? 'income' : workspace.categories.find((category) => category.id === row.category)?.icon ?? 'expense', dateLabel: shortDate(row.date) }))
  const notificationRows = categories.filter((category) => ['over', 'warning'].includes(category.status)).map((category) => ({ id: category.id, title: category.status === 'over' ? `${category.name} is over budget` : `${category.name} is getting close`,
    message: category.status === 'over' ? `${money(-category.remaining)} above its monthly allocation.` : `${money(category.remaining)} remaining in its monthly allocation.` }))
  return {
    month, monthLabel: monthName(month), asOf, asOfLabel: shortDate(asOf), profile: workspace.profile,
    months: [...new Set(workspace.monthlyBudgets.map((row) => row.month))].filter((value) => value <= workspace.asOf.slice(0, 7)).sort().reverse(),
    money: { balance, income: monthlyTotals.income, expenses: monthlyTotals.expenses },
    budget: { allocated, spent: monthlyTotals.expenses, remaining: checkedKobo(allocated - monthlyTotals.expenses), ...budgetState(monthlyTotals.expenses, allocated), categories },
    chart: cashFlow(monthly, month, weekStart),
    plans: { items: pending, expectedIncome: sum(pending.filter((plan) => plan.type === 'income'), 'amount'), plannedExpenses: sum(pending.filter((plan) => plan.type === 'expense'), 'amount') },
    week: { ...weeklyTotals, start: isoDate(week.start), end: isoDate(week.end - dayMs), weekStart, label: `${shortDate(isoDate(week.start))} - ${shortDate(isoDate(week.end - dayMs))}`, largest: largest?.amount ? largest : null },
    recent: transactions.slice(0, 5), transactions, notifications: notificationRows,
  }
}

export function transactionCsv(rows) {
  const cell = (value) => {
    const text = String(value)
    const safe = /^[=+\-@\t\r\n]/.test(text) ? `'${text}` : text
    return `"${safe.replaceAll('"', '""')}"`
  }
  const data = rows.map((row) => [row.date, row.name, row.type, row.categoryName,
    (row.type === 'expense' ? -row.amount : row.amount) / 100])
  return [['Date', 'Description', 'Type', 'Category', 'Amount (NGN)'], ...data].map((row) => row.map(cell).join(',')).join('\r\n')
}
