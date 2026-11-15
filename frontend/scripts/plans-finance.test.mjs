import test from 'node:test'
import assert from 'node:assert/strict'
import { createDashboardWorkspace } from '../src/demo/dashboard.js'
import { selectDashboard } from '../src/finance/dashboard.js'
import { selectBudgets } from '../src/finance/budgets.js'
import { allCategories } from '../src/finance/transactions.js'
import { deleteTransaction } from '../src/finance/workspace.js'
import { workspaceMonths } from '../src/finance/workspace.js'
import {
  activePlanFilterCount,
  confirmPlan,
  createPlanDraft,
  createPlanRecord,
  describePlan,
  filterPlans,
  findPlanTransaction,
  hasActivePlanFilters,
  planDraftFrom,
  planFiltersEmpty,
  planSortLabel,
  planTransactionId,
  removePlan,
  selectPlans,
  sortPlans,
  undoPlanConfirmation,
  upsertPlan,
  validatePlan,
} from '../src/finance/plans.js'

const workspace = createDashboardWorkspace()
const categories = allCategories(workspace)
const empty = planFiltersEmpty()
const november = selectPlans(workspace, '2026-11')

function withPlans(plans, transactions = workspace.transactions) {
  return { ...workspace, plans, transactions }
}

test('plan overview totals are exact and labelled as planned amounts', () => {
  assert.equal(november.month, '2026-11')
  assert.equal(november.monthLabel, 'November 2026')
  assert.equal(november.items.length, 5)
  assert.equal(november.pending.length, 5)
  assert.equal(november.confirmed.length, 0)
  assert.equal(november.expectedIncome, 4000000)
  assert.equal(november.plannedExpenses, 1350000)
  assert.equal(november.projected, 2650000)
  assert.equal(november.upcomingCount, 5)
  assert.equal(november.needsAttentionCount, 0)
  assert.equal(november.confirmedCount, 0)
  assert.equal(november.items[0].typeLabel, 'Expected income')
  assert.equal(november.items.find((row) => row.type === 'expense').typeLabel, 'Planned expense')
  assert.equal(november.items.find((row) => row.id === 'plan-books').categoryName, 'Education')
  assert.equal(november.items.find((row) => row.id === 'plan-books').icon, 'book')
  assert.equal(november.items.find((row) => row.id === 'plan-books').dateLabel, '16 Nov')
})

test('plans never change actual balances or budget spending', () => {
  const before = selectDashboard(workspace, '2026-11')
  const beforeBudgets = selectBudgets(workspace, '2026-11')
  const copy = createDashboardWorkspace()
  copy.plans.push(
    { id: 'big-income', name: 'Windfall', type: 'income', amount: 900000000, date: '2026-11-20', category: 'allowance', status: 'pending', note: '' },
    { id: 'big-expense', name: 'Rent top-up', type: 'expense', amount: 900000000, date: '2026-11-20', category: 'housing', status: 'pending', note: '' },
  )
  const after = selectDashboard(copy, '2026-11')
  assert.deepEqual(after.money, before.money)
  assert.deepEqual(after.budget, before.budget)
  assert.equal(after.plans.plannedExpenses, 901350000)
  assert.deepEqual(selectBudgets(copy, '2026-11'), beforeBudgets)
})

test('month selection scopes plans and the month list stays newest first', () => {
  assert.equal(selectPlans(workspace, '2026-10').items.length, 0)
  assert.equal(selectPlans(workspace, '2026-10').expectedIncome, 0)
  assert.equal(selectPlans(workspace, '2026-12').items.length, 0)

  const copy = createDashboardWorkspace()
  copy.plans.push({ id: 'plan-dec', name: 'December sublet', type: 'expense', amount: 250000, date: '2026-12-01', category: 'housing', status: 'pending', note: '' })
  assert.equal(selectPlans(copy, '2026-12').items.length, 1)
  assert.equal(selectPlans(copy, '2026-12').plannedExpenses, 250000)
  assert.equal(selectPlans(copy, '2026-11').items.length, 5)
  assert.deepEqual(workspaceMonths(copy).slice(0, 2), ['2026-12', '2026-11'])
  assert.deepEqual(workspaceMonths(workspace).slice(0, 3), ['2026-11', '2026-10', '2026-09'])
})

test('overdue pending plans are counted separately from upcoming plans', () => {
  const copy = createDashboardWorkspace()
  copy.plans.push({ id: 'plan-overdue', name: 'Late shuttle pass', type: 'expense', amount: 200000, date: '2026-11-10', category: 'transport', status: 'pending', note: '' })
  const data = selectPlans(copy, '2026-11')
  assert.equal(data.items.length, 6)
  assert.equal(data.upcomingCount, 5)
  assert.equal(data.needsAttentionCount, 1)
  assert.deepEqual(data.attention.map((row) => row.id), ['plan-overdue'])
  assert.equal(data.attention[0].needsAttention, true)
  assert.equal(data.plannedExpenses, 1550000)
})

test('search, type, status and category filters combine', () => {
  const items = november.items
  assert.equal(items.length, 5)
  assert.equal(filterPlans(items, { ...empty, search: 'ELECTRICITY' }).length, 1)
  assert.deepEqual(filterPlans(items, { ...empty, search: 'zzzz' }), [])
  const income = filterPlans(items, { ...empty, type: 'income' })
  assert.equal(income.length, 2)
  assert.ok(income.every((row) => row.type === 'income'))
  assert.equal(filterPlans(items, { ...empty, category: 'education' }).length, 1)
  assert.equal(filterPlans(items, { ...empty, status: 'confirmed' }).length, 0)
  assert.equal(filterPlans(items, { ...empty, status: 'pending' }).length, 5)
  assert.equal(filterPlans(items, { ...empty, type: 'expense', category: 'transport' }).length, 1)
  assert.equal(hasActivePlanFilters(empty), false)
  assert.equal(activePlanFilterCount(empty), 0)
  const active = { ...empty, search: ' rent ', type: 'expense', status: 'pending' }
  assert.equal(hasActivePlanFilters(active), true)
  assert.equal(activePlanFilterCount(active), 3)
})

test('date and amount sorting is stable and numeric', () => {
  const items = november.items
  assert.equal(sortPlans(items, 'date')[0].id, 'plan-allowance')
  assert.equal(sortPlans(items, 'date-desc')[0].id, 'plan-transport')
  assert.equal(sortPlans(items, 'amount-high')[0].id, 'plan-design')
  assert.equal(sortPlans(items, 'amount-low')[0].id, 'plan-power')
  assert.equal(sortPlans(items, 'amount-high')[0].amount, 2200000)
  assert.equal(planSortLabel('amount-high'), 'Amount (highest)')
  assert.throws(() => sortPlans(items, 'sideways'), RangeError)
})

test('plan validation enforces required fields, category fit, amounts and dates', () => {
  const valid = validatePlan(
    { type: 'expense', description: '  Late shuttle pass  ', amount: '2,500.50', category: 'transport', date: '2026-11-25', note: '  Weekly  ' },
    { categories },
  )
  assert.equal(valid.valid, true)
  assert.deepEqual(valid.value, { name: 'Late shuttle pass', type: 'expense', category: 'transport', amount: 250050, date: '2026-11-25', note: 'Weekly' })

  const emptyDraft = validatePlan(createPlanDraft('expense', categories, '2026-11-13'), { categories })
  assert.equal(emptyDraft.valid, false)
  assert.ok(emptyDraft.errors.description)
  assert.ok(emptyDraft.errors.amount)

  const mismatched = validatePlan(
    { type: 'income', description: 'Mismatch', amount: '1', category: 'housing', date: '2026-11-20', note: '' },
    { categories },
  )
  assert.ok(mismatched.errors.category)

  const badAmount = validatePlan(
    { type: 'expense', description: 'Bad amount', amount: '1.234', category: 'food', date: '2026-11-20', note: '' },
    { categories },
  )
  assert.ok(badAmount.errors.amount)

  const badDate = validatePlan(
    { type: 'expense', description: 'Bad date', amount: '1', category: 'food', date: '2026-02-31', note: '' },
    { categories },
  )
  assert.ok(badDate.errors.date)

  const missingDate = validatePlan(
    { type: 'expense', description: 'No date', amount: '1', category: 'food', date: '', note: '' },
    { categories },
  )
  assert.ok(missingDate.errors.date)

  const longNote = validatePlan(
    { type: 'expense', description: 'Note', amount: '1', category: 'food', date: '2026-11-20', note: 'x'.repeat(161) },
    { categories },
  )
  assert.ok(longNote.errors.note)
})

test('future-dated plans are allowed, past-dated plans are allowed, drafts keep the demo date', () => {
  const future = validatePlan(
    { type: 'expense', description: 'Next year', amount: '10', category: 'food', date: '2027-03-01', note: '' },
    { categories },
  )
  assert.equal(future.valid, true)
  assert.equal(future.value.date, '2027-03-01')

  const past = validatePlan(
    { type: 'income', description: 'Last month', amount: '10', category: 'allowance', date: '2026-09-05', note: '' },
    { categories },
  )
  assert.equal(past.valid, true)

  assert.deepEqual(createPlanDraft('income', categories, '2026-11-13'), { type: 'income', description: '', amount: '', category: 'allowance', date: '2026-11-13', note: '' })
  assert.equal(createPlanDraft('expense', categories, '2026-11-13').category, 'housing')
  assert.deepEqual(planDraftFrom({ name: 'Books', type: 'expense', amount: 123456, category: 'education', date: '2026-11-16', note: 'Two books' }), { type: 'expense', description: 'Books', amount: '1234.56', category: 'education', date: '2026-11-16', note: 'Two books' })
})

test('plans are created, edited and removed without touching confirmed records', () => {
  const created = createPlanRecord({ name: 'New plan', type: 'expense', category: 'food', amount: 500000, date: '2026-11-24', note: '' })
  assert.equal(created.status, 'pending')
  assert.equal(created.actualAmount, null)
  const withNew = upsertPlan(workspace.plans, created)
  assert.equal(withNew.length, 6)
  assert.equal(selectPlans(withPlans(withNew), '2026-11').plannedExpenses, 1850000)
  assert.equal(selectPlans(withPlans(withNew), '2026-11').items.length, 6)

  const edited = upsertPlan(withNew, { ...workspace.plans[0], amount: 1900000, date: '2026-11-17' })
  assert.equal(edited.length, 6)
  assert.equal(edited.find((row) => row.id === 'plan-allowance').amount, 1900000)
  const editedData = selectPlans(withPlans(edited), '2026-11')
  assert.equal(editedData.expectedIncome, 4100000)
  assert.equal(editedData.items.find((row) => row.id === 'plan-allowance').dateLabel, '17 Nov')

  const removed = removePlan(workspace.plans, 'plan-power')
  assert.equal(removed.length, 4)
  assert.equal(selectPlans(withPlans(removed), '2026-11').plannedExpenses, 1050000)
  assert.equal(selectPlans(withPlans(removed), '2026-11').items.length, 4)
  assert.throws(() => removePlan(workspace.plans, 'missing'), RangeError)
})

test('confirming with a different actual amount records the real amount', () => {
  const result = confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-books', amount: 400000, asOf: workspace.asOf })

  assert.equal(result.plans.length, 5)
  const plan = result.plans.find((row) => row.id === 'plan-books')
  assert.equal(plan.status, 'confirmed')
  assert.equal(plan.actualAmount, 400000)
  assert.equal(plan.transactionId, 'actual-plan-books')
  assert.equal(plan.confirmedDate, workspace.asOf)

  assert.equal(result.transactions.length, 33)
  const transaction = result.transactions.find((row) => row.id === 'actual-plan-books')
  assert.equal(transaction.planId, 'plan-books')
  assert.equal(transaction.name, 'Course materials')
  assert.equal(transaction.type, 'expense')
  assert.equal(transaction.category, 'education')
  assert.equal(transaction.amount, 400000)
  assert.equal(transaction.date, workspace.asOf)
  assert.equal(transaction.confirmed, true)
  assert.equal(transaction.deleted, false)
  assert.equal(planTransactionId('plan-books'), 'actual-plan-books')

  const data = selectPlans(withPlans(result.plans, result.transactions), '2026-11')
  assert.equal(data.plannedExpenses, 900000)
  assert.equal(data.confirmedCount, 1)
  assert.equal(data.confirmedExpenses, 400000)
  assert.equal(data.expectedIncome, 4000000)
  assert.equal(data.items.find((row) => row.id === 'plan-books').statusLabel, 'Confirmed')
  assert.equal(findPlanTransaction(result.transactions, plan).id, 'actual-plan-books')
})

test('confirmed transactions propagate to the dashboard, transactions and budgets', () => {
  const result = confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-books', amount: 400000, asOf: workspace.asOf })
  const next = withPlans(result.plans, result.transactions)

  const dashboard = selectDashboard(next, '2026-11')
  assert.equal(dashboard.money.expenses, 5430000)
  assert.equal(dashboard.budget.spent, 5430000)
  assert.equal(dashboard.budget.remaining, 570000)
  assert.equal(dashboard.budget.categories.find((row) => row.id === 'education').spent, 830000)
  assert.equal(dashboard.budget.categories.find((row) => row.id === 'education').remaining, -230000)

  const budgets = selectBudgets(next, '2026-11')
  assert.equal(budgets.spent, 5430000)
  assert.equal(budgets.categories.find((row) => row.id === 'education').status, 'over')

  const dashboardList = dashboard.transactions.filter((row) => row.id === 'actual-plan-books')
  assert.equal(dashboardList.length, 1)
  assert.equal(dashboard.plans.items.length, 4)
})

test('expected income confirmation raises actual income but never budget spending', () => {
  const result = confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-allowance', amount: 1750000, asOf: workspace.asOf })
  const next = withPlans(result.plans, result.transactions)

  const dashboard = selectDashboard(next, '2026-11')
  assert.equal(dashboard.money.income, 12300000)
  assert.equal(dashboard.money.balance, 12570000)
  assert.equal(dashboard.money.expenses, 5030000)
  assert.equal(dashboard.budget.spent, 5030000)
  assert.equal(selectBudgets(next, '2026-11').spent, 5030000)

  const data = selectPlans(next, '2026-11')
  assert.equal(data.expectedIncome, 2200000)
  assert.equal(data.plannedExpenses, 1350000)
  assert.equal(data.confirmedIncome, 1750000)
  assert.equal(data.confirmedExpenses, 0)
})

test('a plan cannot be confirmed twice', () => {
  const result = confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-power', amount: 300000, asOf: workspace.asOf })
  assert.throws(
    () => confirmPlan({ plans: result.plans, transactions: result.transactions, planId: 'plan-power', amount: 300000, asOf: workspace.asOf }),
    RangeError,
  )
  assert.throws(
    () => confirmPlan({ plans: workspace.plans, transactions: [...workspace.transactions, { id: 'actual-plan-power', planId: 'plan-power', type: 'expense', category: 'housing', amount: 1, date: '2026-11-13', confirmed: true, deleted: false }], planId: 'plan-power', amount: 300000, asOf: workspace.asOf }),
    RangeError,
  )
  assert.throws(() => confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'missing', amount: 1, asOf: workspace.asOf }), RangeError)
  assert.throws(() => confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-power', amount: 0, asOf: workspace.asOf }), TypeError)
})

test('undo confirmation reverses the transaction and recalculates summaries', () => {
  const confirmed = confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-books', amount: 400000, asOf: workspace.asOf })
  const undone = undoPlanConfirmation({ plans: confirmed.plans, transactions: confirmed.transactions, planId: 'plan-books' })

  const plan = undone.plans.find((row) => row.id === 'plan-books')
  assert.equal(plan.status, 'pending')
  assert.equal(plan.actualAmount, null)
  assert.equal(plan.transactionId, null)
  assert.equal(plan.confirmedDate, null)
  assert.equal(undone.transactions.find((row) => row.id === 'actual-plan-books').deleted, true)
  assert.equal(undone.transactions.filter((row) => !row.deleted).length, 32)

  const dashboard = selectDashboard(withPlans(undone.plans, undone.transactions), '2026-11')
  assert.equal(dashboard.money.expenses, 5030000)
  assert.equal(dashboard.budget.spent, 5030000)
  assert.equal(selectBudgets(withPlans(undone.plans, undone.transactions), '2026-11').categories.find((row) => row.id === 'education').spent, 430000)
  assert.equal(selectPlans(withPlans(undone.plans, undone.transactions), '2026-11').plannedExpenses, 1350000)
  assert.equal(selectPlans(withPlans(undone.plans, undone.transactions), '2026-11').confirmedCount, 0)

  assert.throws(
    () => undoPlanConfirmation({ plans: undone.plans, transactions: undone.transactions, planId: 'plan-books' }),
    RangeError,
  )
  assert.throws(() => undoPlanConfirmation({ plans: workspace.plans, transactions: workspace.transactions, planId: 'missing' }), RangeError)
})

test('undo is blocked when the linked transaction can no longer be identified', () => {
  const confirmed = confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-books', amount: 400000, asOf: workspace.asOf })
  const removed = deleteTransaction(confirmed.transactions, 'actual-plan-books')

  assert.equal(findPlanTransaction(removed, confirmed.plans.find((row) => row.id === 'plan-books')), null)
  assert.throws(() => undoPlanConfirmation({ plans: confirmed.plans, transactions: removed, planId: 'plan-books' }), RangeError)

  const planWithoutLink = confirmed.plans.map((row) => (row.id === 'plan-books' ? { ...row, transactionId: null } : row))
  assert.throws(() => undoPlanConfirmation({ plans: planWithoutLink, transactions: confirmed.transactions, planId: 'plan-books' }), RangeError)

  const mismatched = confirmed.transactions.map((row) => (row.id === 'actual-plan-books' ? { ...row, planId: 'other-plan' } : row))
  assert.throws(() => undoPlanConfirmation({ plans: confirmed.plans, transactions: mismatched, planId: 'plan-books' }), RangeError)
})

test('re-confirming after undo reuses the same transaction instead of duplicating it', () => {
  const confirmed = confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-books', amount: 400000, asOf: workspace.asOf })
  const undone = undoPlanConfirmation({ plans: confirmed.plans, transactions: confirmed.transactions, planId: 'plan-books' })
  const again = confirmPlan({ plans: undone.plans, transactions: undone.transactions, planId: 'plan-books', amount: 450000, asOf: workspace.asOf })

  assert.equal(again.transactions.filter((row) => row.planId === 'plan-books').length, 1)
  assert.equal(again.transactions.filter((row) => row.id === 'actual-plan-books').length, 1)
  assert.equal(again.transactions.filter((row) => !row.deleted).length, 33)
  assert.equal(again.transactions.find((row) => row.id === 'actual-plan-books').amount, 450000)
  assert.equal(again.transactions.find((row) => row.id === 'actual-plan-books').deleted, false)
})

test('confirmed plans cannot be edited or deleted until the confirmation is undone', () => {
  const confirmed = confirmPlan({ plans: workspace.plans, transactions: workspace.transactions, planId: 'plan-power', amount: 300000, asOf: workspace.asOf })
  const target = confirmed.plans.find((row) => row.id === 'plan-power')
  assert.throws(() => upsertPlan(confirmed.plans, { ...target, amount: 1 }), RangeError)
  assert.throws(() => removePlan(confirmed.plans, 'plan-power'), RangeError)

  const undone = undoPlanConfirmation({ plans: confirmed.plans, transactions: confirmed.transactions, planId: 'plan-power' })
  const edited = upsertPlan(undone.plans, { ...undone.plans.find((row) => row.id === 'plan-power'), amount: 350000 })
  assert.equal(edited.find((row) => row.id === 'plan-power').amount, 350000)
  assert.equal(removePlan(edited, 'plan-power').length, 4)
})

test('describing a plan rejects invalid types, amounts and dates', () => {
  const base = { id: 'x', name: 'Plan', amount: 1000, date: '2026-11-20', category: 'food' }
  assert.equal(describePlan({ ...base, type: 'expense' }, categories).status, 'pending')
  assert.equal(describePlan({ ...base, type: 'expense' }, categories, '2026-11-25').needsAttention, true)
  assert.equal(describePlan({ ...base, type: 'expense', status: 'confirmed' }, categories).statusLabel, 'Confirmed')
  assert.throws(() => describePlan({ ...base, type: 'other' }, categories), TypeError)
  assert.throws(() => describePlan({ ...base, type: 'expense', amount: 0 }, categories), TypeError)
  assert.throws(() => describePlan({ ...base, type: 'expense', date: '2026-02-31' }, categories), RangeError)
})