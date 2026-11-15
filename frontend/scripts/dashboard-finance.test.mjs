import test from 'node:test'
import assert from 'node:assert/strict'
import { createDashboardWorkspace } from '../src/demo/dashboard.js'
import { selectDashboard, actualTransactions, dateNumber, weekBounds, budgetState, money } from '../src/finance/dashboard.js'
import { availableBudgetCategories, removeBudget, selectBudgets, upsertBudget } from '../src/finance/budgets.js'
import { updateTransaction } from '../src/finance/workspace.js'

test('confirmed cumulative balance and November totals are exact', () => {
  const data = selectDashboard(createDashboardWorkspace(), '2026-11')
  assert.deepEqual(data.money, { balance: 10820000, income: 10550000, expenses: 5030000 })
  assert.equal(data.budget.allocated, 6000000)
  assert.equal(data.budget.remaining, 970000)
  assert.equal(data.budget.spent, 5030000)
})

test('expected income and planned expenses never change actual money', () => {
  const workspace = createDashboardWorkspace()
  const before = selectDashboard(workspace, '2026-11')
  workspace.plans.push({ id: 'large-income-plan', name: 'Expected only', type: 'income', amount: 100000000, date: '2026-11-20', status: 'pending' })
  workspace.plans.push({ id: 'large-expense-plan', name: 'Planned only', type: 'expense', amount: 100000000, date: '2026-11-20', status: 'pending' })
  const after = selectDashboard(workspace, '2026-11')
  assert.deepEqual(after.money, before.money)
  assert.deepEqual(after.budget, before.budget)
  assert.deepEqual(after.chart, before.chart)
  assert.deepEqual(after.week, before.week)
  assert.equal(before.plans.expectedIncome, 4000000)
  assert.equal(before.plans.plannedExpenses, 1350000)
})

test('daily and weekly tracking limits are not monthly allocations', () => {
  const workspace = createDashboardWorkspace()
  workspace.trackingLimits = [{ amount: 900000000, period: 'daily' }, { amount: 900000000, period: 'weekly' }]
  assert.equal(selectDashboard(workspace, '2026-11').budget.allocated, 6000000)
})

test('configured Monday and Sunday weeks produce different, correct reports', () => {
  const workspace = createDashboardWorkspace()
  const monday = selectDashboard(workspace, '2026-11', 1)
  const sunday = selectDashboard(workspace, '2026-11', 7)
  assert.equal(monday.week.start, '2026-11-09')
  assert.equal(monday.week.income, 4250000)
  assert.equal(monday.week.expenses, 1230000)
  assert.equal(monday.week.balance, 3020000)
  assert.equal(monday.week.largest.amount, 675000)
  assert.equal(sunday.week.start, '2026-11-08')
  assert.equal(sunday.week.expenses, 1410000)
  assert.equal(sunday.week.balance, 2840000)
  assert.equal(sunday.week.largest.amount, 855000)
  assert.equal(monday.chart.buckets[0].end, '2026-11-01')
  assert.equal(sunday.chart.buckets[0].end, '2026-11-07')
})

test('unconfirmed, deleted and future actual records are excluded', () => {
  const workspace = createDashboardWorkspace()
  const baseline = selectDashboard(workspace, '2026-11')
  const row = { id: 'excluded', name: 'Not actual', type: 'income', amount: 9990000, category: 'allowance' }
  workspace.transactions.push({ ...row, date: '2026-11-10', confirmed: false }, { ...row, date: '2026-11-10', confirmed: true, deleted: true }, { ...row, date: '2026-11-20', confirmed: true })
  assert.deepEqual(selectDashboard(workspace, '2026-11').money, baseline.money)
})

test('historical month balances include earlier confirmed months, not later activity', () => {
  const workspace = createDashboardWorkspace()
  assert.equal(selectDashboard(workspace, '2026-09').money.balance, 2100000)
  assert.equal(selectDashboard(workspace, '2026-10').money.balance, 5300000)
  assert.equal(selectDashboard(workspace, '2026-10').asOf, '2026-10-31')
})

test('budget thresholds distinguish warning, exact exhaustion and over-budget', () => {
  assert.equal(budgetState(79, 100).status, 'on-track')
  assert.equal(budgetState(80, 100).status, 'warning')
  assert.equal(budgetState(100, 100).status, 'exhausted')
  assert.equal(budgetState(101, 100).status, 'over')
  assert.equal(budgetState(101, 100).progress, 100)
  assert.equal(budgetState(0, 0).status, 'none')
})

test('invalid dates, money and week preferences are rejected rather than coerced', () => {
  assert.throws(() => dateNumber('2026-02-31'))
  assert.throws(() => weekBounds('2026-11-13', 2))
  for (const amount of ['100', 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => actualTransactions([{ type: 'income', confirmed: true, amount, date: '2026-11-01' }], '2026-11-13'))
  }
  assert.ok(money(123400).includes('1,234'))
  assert.ok(!money(123400).includes('$'))
})

test('chart buckets add up to the confirmed month totals', () => {
  for (const month of ['2026-09', '2026-10', '2026-11']) {
    const data = selectDashboard(createDashboardWorkspace(), month)
    const income = data.chart.buckets.reduce((total, bucket) => total + bucket.income, 0)
    const expenses = data.chart.buckets.reduce((total, bucket) => total + bucket.expenses, 0)
    assert.equal(income, data.money.income)
    assert.equal(expenses, data.money.expenses)
    assert.equal(data.chart.totalIncome, data.money.income)
    assert.equal(data.chart.totalExpenses, data.money.expenses)
    assert.equal(data.chart.hasData, true)
  }
})

test('y axis uses an even scale that contains every bucket', () => {
  const data = selectDashboard(createDashboardWorkspace(), '2026-11')
  const maximum = Math.max(...data.chart.buckets.flatMap((bucket) => [bucket.income, bucket.expenses]))
  const step = data.chart.ticks[1]
  assert.equal(data.chart.ticks[0], 0)
  assert.equal(data.chart.ticks.at(-1), data.chart.ceiling)
  assert.ok(data.chart.ceiling >= maximum)
  assert.ok(data.chart.ticks.length >= 3 && data.chart.ticks.length <= 6)
  for (let index = 1; index < data.chart.ticks.length; index += 1) {
    assert.equal(data.chart.ticks[index] - data.chart.ticks[index - 1], step)
  }
})

test('week labels read as day ranges and keep month boundaries', () => {
  const monday = selectDashboard(createDashboardWorkspace(), '2026-11', 1)
  const sunday = selectDashboard(createDashboardWorkspace(), '2026-11', 7)
  assert.deepEqual(monday.chart.buckets.map((bucket) => bucket.label), ['1', '2–8', '9–15', '16–22', '23–29', '30'])
  assert.deepEqual(sunday.chart.buckets.map((bucket) => bucket.label), ['1–7', '8–14', '15–21', '22–28', '29–30'])
  assert.equal(monday.chart.buckets[0].fullLabel, '1 Nov')
  assert.equal(monday.chart.buckets[1].fullLabel, '2–8 Nov')
})

test('shared budget changes update dashboard allocation selectors for every budget operation', () => {
  const workspace = createDashboardWorkspace()
  const health = { id: '2026-11-health', month: '2026-11', category: 'health', allocation: 200000, archived: false }
  const created = upsertBudget(workspace.monthlyBudgets, health)
  const createdWorkspace = { ...workspace, monthlyBudgets: created }
  assert.equal(selectBudgets(createdWorkspace, '2026-11').allocated, 6200000)
  assert.equal(selectDashboard(createdWorkspace, '2026-11').budget.allocated, 6200000)

  const edited = upsertBudget(created, { ...health, allocation: 250000 })
  const editedWorkspace = { ...workspace, monthlyBudgets: edited }
  assert.equal(selectBudgets(editedWorkspace, '2026-11').allocated, 6250000)
  assert.equal(selectDashboard(editedWorkspace, '2026-11').budget.allocated, 6250000)

  const removed = removeBudget(edited, health.id)
  const removedWorkspace = { ...workspace, monthlyBudgets: removed }
  assert.equal(selectBudgets(removedWorkspace, '2026-11').allocated, 6000000)
  assert.equal(selectDashboard(removedWorkspace, '2026-11').budget.allocated, 6000000)
  assert.deepEqual(availableBudgetCategories(workspace.categories, removed, '2026-11').map((category) => category.id), ['health'])
})

test('month selection is a shared session value used by both dashboard and budget selectors', () => {
  const workspace = createDashboardWorkspace()
  const months = ['2026-11', '2026-10', '2026-09']
  for (const month of months) {
    const dashboard = selectDashboard(workspace, month)
    const budgets = selectBudgets(workspace, month)
    assert.equal(dashboard.month, month)
    assert.equal(budgets.month, month)
    assert.equal(dashboard.monthLabel, budgets.monthLabel)
  }
})

test('editing transaction amount, category and date recalculates dashboard and budgets for the correct month', () => {
  const workspace = createDashboardWorkspace()
  const food = workspace.transactions.find((row) => row.id === 'nov03b')
  const amountChanged = { ...workspace, transactions: updateTransaction(workspace.transactions, { ...food, amount: 500000 }) }
  assert.equal(selectDashboard(amountChanged, '2026-11').budget.spent, 5080000)
  assert.equal(selectBudgets(amountChanged, '2026-11').categories.find((row) => row.id === 'food').spent, 1355000)

  const categoryChanged = { ...workspace, transactions: updateTransaction(workspace.transactions, { ...food, category: 'transport' }) }
  const categoryDashboard = selectDashboard(categoryChanged, '2026-11').budget.categories
  assert.equal(categoryDashboard.find((row) => row.id === 'food').spent, 855000)
  assert.equal(categoryDashboard.find((row) => row.id === 'transport').spent, 845000)
  assert.equal(selectBudgets(categoryChanged, '2026-11').spent, 5030000)

  const dateChanged = { ...workspace, transactions: updateTransaction(workspace.transactions, { ...food, date: '2026-10-28' }) }
  assert.equal(selectDashboard(dateChanged, '2026-11').budget.spent, 4580000)
  assert.equal(selectDashboard(dateChanged, '2026-10').budget.spent, 6450000)
  assert.equal(selectBudgets(dateChanged, '2026-10').categories.find((row) => row.id === 'food').spent, 2050000)
})

test('transaction deletion is excluded from budget spending without deleting the budget allocation', () => {
  const workspace = createDashboardWorkspace()
  const deleted = { ...workspace, transactions: workspace.transactions.map((row) => row.id === 'nov02' ? { ...row, deleted: true } : row) }
  const dashboard = selectDashboard(deleted, '2026-11')
  const budgets = selectBudgets(deleted, '2026-11')
  assert.equal(dashboard.budget.spent, 2530000)
  assert.equal(budgets.spent, 2530000)
  assert.equal(budgets.remaining, 3470000)
  assert.equal(dashboard.budget.categories.find((row) => row.id === 'housing').spent, 0)
  assert.equal(budgets.categories.find((row) => row.id === 'housing').spent, 0)
  assert.equal(budgets.allocated, 6000000)
})

test('income edits and planned expenses do not alter expense budget spending', () => {
  const workspace = createDashboardWorkspace()
  const income = workspace.transactions.find((row) => row.id === 'nov01')
  const edited = { ...workspace, transactions: updateTransaction(workspace.transactions, { ...income, amount: 9999999 }) }
  const data = selectDashboard(edited, '2026-11')
  assert.equal(data.money.income, 16049999)
  assert.equal(data.budget.spent, 5030000)
  assert.equal(selectBudgets(edited, '2026-11').spent, 5030000)
})

test('a month without confirmed activity reports an empty chart', () => {
  const workspace = createDashboardWorkspace()
  workspace.transactions = workspace.transactions.filter((row) => !row.date.startsWith('2026-11-'))
  const data = selectDashboard(workspace, '2026-11')
  assert.equal(data.chart.hasData, false)
  assert.equal(data.chart.totalIncome, 0)
  assert.equal(data.chart.totalExpenses, 0)
  assert.equal(data.chart.buckets.length, 6)
  assert.ok(data.chart.buckets.every((bucket) => bucket.income === 0 && bucket.expenses === 0))
})
