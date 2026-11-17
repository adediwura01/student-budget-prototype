import test from 'node:test'
import assert from 'node:assert/strict'
import { createDashboardWorkspace } from '../src/demo/dashboard.js'
import { actualTransactions, selectDashboard, transactionCsv } from '../src/finance/dashboard.js'
import { selectBudgets, upsertBudget } from '../src/finance/budgets.js'
import { confirmPlan, undoPlanConfirmation } from '../src/finance/plans.js'
import { filterTransactions, summariseTransactions } from '../src/finance/transactions.js'
import { deleteTransaction, updateTransaction } from '../src/finance/workspace.js'
import { reportRangeOptions, resolveReportRange, selectReports } from '../src/finance/reports.js'

const workspace = createDashboardWorkspace()
const range = (preset = 'this-month', custom = {}, asOf = workspace.asOf) => resolveReportRange(asOf, preset, custom)
const report = (data = workspace, selection = range()) => selectReports(data, selection)
const sum = (rows, key) => rows.reduce((total, row) => total + row[key], 0)

test('presets use the demo clock and expose inclusive, clearly labelled dates', () => {
  assert.equal(reportRangeOptions.length, 4)
  assert.deepEqual([range().from, range().to, range().days], ['2026-11-01', '2026-11-13', 13])
  assert.deepEqual([range('last-month').from, range('last-month').to, range('last-month').days], ['2026-10-01', '2026-10-31', 31])
  assert.deepEqual([range('last-3-months').from, range('last-3-months').to], ['2026-09-01', '2026-11-13'])
  assert.equal(range().label, '1 Nov 2026 - 13 Nov 2026')
  assert.equal(range('custom', { from: '2026-11-13', to: '2026-11-13' }).label, '13 Nov 2026')
})

test('calendar presets handle year rollovers and leap-year month ends', () => {
  assert.deepEqual([range('last-month', {}, '2027-01-05').from, range('last-month', {}, '2027-01-05').to], ['2026-12-01', '2026-12-31'])
  assert.equal(range('last-3-months', {}, '2027-01-05').from, '2026-11-01')
  assert.equal(range('last-month', {}, '2028-03-05').to, '2028-02-29')
  assert.equal(range('last-month', {}, '2027-03-05').to, '2027-02-28')
})

test('custom ranges reject missing, invalid, reversed and future dates', () => {
  for (const custom of [
    { from: '', to: '2026-11-13' },
    { from: '2026-11-01', to: '' },
    { from: '2026-02-30', to: '2026-11-13' },
    { from: '01/11/2026', to: '2026-11-13' },
    { from: '2026-11-13', to: '2026-11-12' },
    { from: '2026-11-01', to: '2026-11-14' },
  ]) assert.throws(() => range('custom', custom), RangeError)
  assert.throws(() => range('unknown'), RangeError)
})

test('November net cash flow is period income minus period expenses, not cumulative balance', () => {
  const data = report()
  assert.deepEqual(data.summary, { income: 10550000, expenses: 5030000, net: 5520000, count: 17 })
  assert.notEqual(data.summary.net, selectDashboard(workspace, '2026-11').money.balance)
  assert.equal(data.transactions.length, 17)
  assert.ok(data.transactions.every((row) => row.confirmed === true && !row.deleted))
})

test('last month and the last three months have exact, reconciling totals', () => {
  assert.deepEqual(report(workspace, range('last-month')).summary, { income: 9200000, expenses: 6000000, net: 3200000, count: 8 })
  assert.deepEqual(report(workspace, range('last-3-months')).summary, { income: 27250000, expenses: 16430000, net: 10820000, count: 32 })
})

test('custom range transaction totals include both endpoints and exclude other dates', () => {
  const data = report(workspace, range('custom', { from: '2026-11-12', to: '2026-11-13' }))
  assert.deepEqual(data.summary, { income: 3000000, expenses: 730000, net: 2270000, count: 5 })
  assert.ok(data.transactions.every((row) => row.date >= '2026-11-12' && row.date <= '2026-11-13'))
})

test('report money reconciles with Dashboard and Transactions for every demo month', () => {
  for (const month of ['2026-09', '2026-10', '2026-11']) {
    const dashboard = selectDashboard(workspace, month)
    const selection = range('custom', { from: `${month}-01`, to: dashboard.asOf })
    const data = report(workspace, selection)
    const actual = actualTransactions(workspace.transactions, workspace.asOf)
    const transactions = filterTransactions(actual, { search: '', type: 'all', category: 'all', from: selection.from, to: selection.to })
    assert.equal(data.summary.income, dashboard.money.income)
    assert.equal(data.summary.expenses, dashboard.money.expenses)
    assert.deepEqual(data.summary, summariseTransactions(transactions))
    assert.deepEqual(data.budgets[0].categories, selectBudgets(workspace, month).categories)
  }
})

test('plans, unconfirmed, deleted, future and non-financial records never enter actual reports', () => {
  const copy = createDashboardWorkspace()
  const baseline = report(copy)
  copy.plans.push({ id: 'expected-only', name: 'Expected only', type: 'income', amount: 999000000, date: '2026-11-12', status: 'pending' })
  const row = { id: 'excluded', name: 'Excluded', type: 'expense', category: 'food', amount: 9990000, date: '2026-11-10' }
  copy.transactions.push(
    { ...row, confirmed: false },
    { ...row, confirmed: 'true' },
    { ...row, confirmed: true, deleted: true },
    { ...row, confirmed: true, date: '2026-11-14' },
    { ...row, confirmed: true, type: 'transfer' },
    { ...row, confirmed: true, type: 'adjustment' },
  )
  assert.deepEqual(report(copy), baseline)
})

test('daily and weekly tracking limits never increase the monthly allocation', () => {
  const copy = createDashboardWorkspace()
  copy.trackingLimits = [{ period: 'daily', amount: 999000000 }, { period: 'weekly', amount: 999000000 }]
  assert.equal(report(copy).budgets[0].allocated, 6000000)
})

test('all chart buckets reconcile exactly and stop at the reporting cutoff', () => {
  for (const preset of ['this-month', 'last-month', 'last-3-months']) {
    const data = report(workspace, range(preset))
    for (const buckets of [data.flow, data.trends]) {
      assert.equal(sum(buckets, 'income'), data.summary.income)
      assert.equal(sum(buckets, 'expenses'), data.summary.expenses)
      assert.equal(sum(buckets, 'net'), data.summary.net)
      assert.equal(buckets[0].start, data.range.from)
      assert.equal(buckets.at(-1).end, data.range.to)
      assert.ok(buckets.every((bucket) => Number.isSafeInteger(bucket.income) && Number.isSafeInteger(bucket.expenses) && bucket.end <= data.range.to))
    }
  }
})

test('weekly charts respect the existing Monday or Sunday preference', () => {
  const monday = report()
  const sunday = report({ ...workspace, profile: { ...workspace.profile, weekStart: 7 } })
  assert.equal(monday.flow[0].end, '2026-11-01')
  assert.equal(monday.flow[0].partial, true)
  assert.equal(sunday.flow[0].end, '2026-11-07')
  assert.equal(sunday.flow[0].partial, false)
  assert.equal(sum(monday.flow, 'expenses'), sum(sunday.flow, 'expenses'))
  assert.throws(() => report({ ...workspace, profile: { ...workspace.profile, weekStart: 2 } }), RangeError)
})

test('expense category amounts and visual percentages reconcile with total expenses', () => {
  const data = report()
  assert.equal(sum(data.categories, 'amount'), data.summary.expenses)
  assert.deepEqual(data.categories.map((category) => [category.id, category.amount]), [
    ['housing', 2500000], ['food', 1305000], ['education', 430000], ['lifestyle', 400000], ['transport', 395000],
  ])
  assert.ok(Math.abs(sum(data.categories, 'percent') - 100) < 1e-10)
})

test('many categories are grouped into at most six chart segments without hiding ledger amounts', () => {
  const copy = createDashboardWorkspace()
  for (let index = 0; index < 9; index += 1) {
    const id = `additional-${index}`
    copy.categories.push({ id, name: `Additional ${index}`, tone: 'purple', icon: 'expense' })
    copy.transactions.push({ id, category: id, name: 'Additional expense', type: 'expense', amount: index + 1, date: copy.asOf, confirmed: true })
  }
  const data = report(copy)
  assert.equal(data.categories.length, 14)
  assert.equal(data.chartCategories.length, 6)
  assert.equal(data.chartCategories.at(-1).grouped, true)
  assert.equal(data.chartCategories.at(-1).amount, 45)
  assert.equal(sum(data.chartCategories, 'amount'), data.summary.expenses)
  assert.equal(sum(data.categories, 'amount'), data.summary.expenses)
})

test('unknown categories remain visible and count as spending without an allocation', () => {
  const copy = createDashboardWorkspace()
  copy.transactions.push({ id: 'unknown', category: 'removed-category', name: 'Unknown category', type: 'expense', amount: 101, date: copy.asOf, confirmed: true })
  const data = report(copy)
  assert.equal(data.summary.expenses, 5030101)
  assert.equal(data.categories.find((category) => category.id === 'uncategorised').amount, 101)
  assert.equal(data.budgets[0].unbudgeted.find((category) => category.id === 'uncategorised').spent, 101)
  assert.equal(data.transactions.find((row) => row.id === 'unknown').categoryName, 'Uncategorised')
})

test('empty ranges have real zero values, empty breakdowns and zero-filled periods', () => {
  const data = report(workspace, range('custom', { from: '2026-08-01', to: '2026-08-31' }))
  assert.deepEqual(data.summary, { income: 0, expenses: 0, net: 0, count: 0 })
  assert.deepEqual(data.categories, [])
  assert.deepEqual(data.transactions, [])
  assert.equal(data.budgets[0].allocated, 0)
  assert.equal(data.budgets[0].spent, 0)
  assert.ok(data.flow.every((bucket) => bucket.income === 0 && bucket.expenses === 0))
  assert.ok(data.trends.every((bucket) => bucket.expenses === 0))
})

test('income-only periods have no spending category or imaginary trend figures', () => {
  const data = report(workspace, range('custom', { from: '2026-11-01', to: '2026-11-01' }))
  assert.equal(data.summary.income, 4500000)
  assert.equal(data.summary.expenses, 0)
  assert.deepEqual(data.categories, [])
  assert.equal(data.trends.length, 1)
  assert.equal(data.trends[0].expenses, 0)
  assert.equal(data.comparison, null)
})

test('multiple-month reports keep each monthly allocation separate', () => {
  const data = report(workspace, range('last-3-months'))
  assert.deepEqual(data.budgets.map((budget) => [budget.month, budget.allocated, budget.spent]), [
    ['2026-11', 6000000, 5030000], ['2026-10', 6000000, 6000000], ['2026-09', 6000000, 5400000],
  ])
  assert.equal(data.flowInterval, 'monthly')
  assert.equal(data.flow.at(-1).partial, true)
})

test('partial custom ranges do not reset monthly budget spending or include later expenses', () => {
  const selection = range('custom', { from: '2026-11-10', to: '2026-11-11' })
  const data = report(workspace, selection)
  assert.deepEqual(data.summary, { income: 1250000, expenses: 180000, net: 1070000, count: 3 })
  assert.equal(data.budgets[0].from, '2026-11-01')
  assert.equal(data.budgets[0].asOf, '2026-11-11')
  assert.equal(data.budgets[0].allocated, 6000000)
  assert.equal(data.budgets[0].spent, 4300000)
  assert.equal(data.budgets[0].remaining, 1700000)
  assert.deepEqual(data.budgets[0].categories, selectBudgets({ ...workspace, asOf: selection.to }, '2026-11').categories)
})

test('zero allocations and unbudgeted categories stay safe and explicit', () => {
  const copy = createDashboardWorkspace()
  copy.monthlyBudgets.push({ id: '2026-11-health', month: '2026-11', category: 'health', allocation: 0, archived: false })
  copy.transactions.push({ id: 'health', category: 'health', name: 'Health expense', type: 'expense', amount: 100, date: copy.asOf, confirmed: true })
  const health = report(copy).budgets[0].categories.find((category) => category.id === 'health')
  assert.equal(health.percent, 0)
  assert.equal(health.remaining, -100)
  assert.equal(health.status, 'none')
  const noBudgets = report({ ...copy, monthlyBudgets: copy.monthlyBudgets.map((budget) => ({ ...budget, archived: true })) })
  assert.equal(noBudgets.budgets[0].allocated, 0)
  assert.equal(noBudgets.budgets[0].remaining, -5030100)
  assert.equal(sum(noBudgets.budgets[0].unbudgeted, 'spent'), noBudgets.summary.expenses)
})

test('trend changes do not compare an unfinished month with a complete month', () => {
  const data = report(workspace, range('custom', { from: '2026-08-01', to: '2026-11-13' }))
  assert.equal(data.trendInterval, 'monthly')
  assert.equal(data.trends.at(-1).partial, true)
  assert.equal(data.comparison.current.start, '2026-10-01')
  assert.equal(data.comparison.previous.start, '2026-09-01')
  assert.equal(data.comparison.difference, 600000)
  assert.equal(data.comparison.percent, 600000 / 5400000 * 100)
})

test('one-kobo changes remain exact and zero prior spending does not produce an infinite percentage', () => {
  const copy = createDashboardWorkspace()
  copy.transactions = [
    { id: 'one', name: 'One kobo', type: 'expense', category: 'food', amount: 1, date: '2026-11-13', confirmed: true },
    { id: 'income', name: 'Income', type: 'income', category: 'allowance', amount: 101, date: '2026-11-13', confirmed: true },
  ]
  const data = report(copy)
  assert.deepEqual(data.summary, { income: 101, expenses: 1, net: 100, count: 2 })
  assert.equal(data.comparison.difference, 1)
  assert.equal(data.comparison.percent, null)
})

test('editing, moving, deleting and budget changes propagate from the shared workspace', () => {
  const target = workspace.transactions.find((row) => row.id === 'nov03b')
  const edited = report({ ...workspace, transactions: updateTransaction(workspace.transactions, { ...target, amount: 450001, category: 'transport' }) })
  assert.equal(edited.summary.expenses, 5030001)
  assert.equal(edited.categories.find((category) => category.id === 'transport').amount, 845001)
  const moved = report({ ...workspace, transactions: updateTransaction(workspace.transactions, { ...target, date: '2026-10-28' }) })
  assert.equal(moved.summary.expenses, 4580000)
  const deleted = report({ ...workspace, transactions: deleteTransaction(workspace.transactions, target.id) })
  assert.equal(deleted.summary.expenses, 4580000)
  const budgetChanged = report({ ...workspace, monthlyBudgets: upsertBudget(workspace.monthlyBudgets, { ...workspace.monthlyBudgets.find((budget) => budget.id === '2026-11-food'), allocation: 2000000 }) })
  assert.equal(budgetChanged.budgets[0].allocated, 6800000)
  assert.equal(budgetChanged.budgets[0].categories.find((category) => category.id === 'food').remaining, 695000)
})

test('a confirmed plan enters Reports exactly once using the actual amount and reverses on undo', () => {
  const confirmed = confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-allowance', amount: 1750001, asOf: workspace.asOf })
  const next = { ...workspace, ...confirmed }
  assert.equal(report(next).summary.income, 12300001)
  assert.equal(report(next).summary.expenses, 5030000)
  const undone = undoPlanConfirmation({ plans: confirmed.plans, transactions: confirmed.transactions, planId: 'plan-allowance' })
  assert.deepEqual(report({ ...workspace, ...undone }).summary, report().summary)
})

test('invalid monetary values and unsafe aggregate overflow are rejected', () => {
  for (const amount of [0, -1, 0.5, NaN, Infinity, '100', Number.MAX_SAFE_INTEGER + 1]) {
    const copy = createDashboardWorkspace()
    copy.transactions.push({ id: 'invalid', name: 'Invalid', type: 'expense', category: 'food', amount, date: copy.asOf, confirmed: true })
    assert.throws(() => report(copy), TypeError)
  }
  const copy = createDashboardWorkspace()
  copy.transactions.push({ id: 'overflow', name: 'Overflow', type: 'income', category: 'allowance', amount: Number.MAX_SAFE_INTEGER, date: copy.asOf, confirmed: true })
  assert.throws(() => report(copy), TypeError)
})

test('CSV reuses the actual transaction export pattern with readable categories and safe descriptions', () => {
  const data = report(workspace, range('custom', { from: '2026-11-12', to: '2026-11-13' }))
  const csv = transactionCsv(data.transactions)
  assert.equal(csv.split('\r\n').length, 6)
  assert.ok(csv.includes('Amount (NGN)'))
  assert.ok(csv.includes('Scholarship'))
  assert.ok(!csv.includes('Family allowance'))
  assert.ok(!csv.includes('2026-11-10'))
  const unsafe = transactionCsv([{ ...data.transactions[0], name: '=SUM(A1:A2)', categoryName: 'Quoted "category"' }])
  assert.ok(unsafe.includes("'=SUM(A1:A2)"))
  assert.ok(unsafe.includes('Quoted ""category""'))
})

test('report selection does not mutate the workspace or stored transactions', () => {
  const copy = createDashboardWorkspace()
  const before = structuredClone(copy)
  report(copy, range('last-3-months'))
  assert.deepEqual(copy, before)
})
