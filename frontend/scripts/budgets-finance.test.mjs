import test from 'node:test'
import assert from 'node:assert/strict'
import { createDashboardWorkspace } from '../src/demo/dashboard.js'
import {
  availableBudgetCategories,
  availableMonths,
  budgetId,
  createBudgetDraft,
  formatAllocationInput,
  removeBudget,
  selectBudgets,
  upsertBudget,
  validateBudget,
} from '../src/finance/budgets.js'

const workspace = createDashboardWorkspace()
const categories = workspace.categories
const november = selectBudgets(workspace, '2026-11')

test('demo categories include one unbudgeted expense category for allocation management', () => {
  assert.equal(categories.length, 6)
  assert.equal(workspace.monthlyBudgets.filter((row) => row.month === '2026-11').length, 5)
  assert.equal(november.categories.length, 5)
  assert.equal(november.unbudgeted.length, 0)
})

test('November allocation, confirmed spending, remaining and status are exact', () => {
  assert.equal(november.month, '2026-11')
  assert.equal(november.monthLabel, 'November 2026')
  assert.equal(november.allocated, 6000000)
  assert.equal(november.spent, 5030000)
  assert.equal(november.remaining, 970000)
  assert.equal(november.status, 'warning')
  assert.equal(november.label, 'Getting close')
  assert.equal(november.percent, 5030000 / 6000000 * 100)
  assert.equal(november.progress, november.percent)
})

test('category allocations, spending, remaining and thresholds are exact', () => {
  const byId = Object.fromEntries(november.categories.map((category) => [category.id, category]))
  assert.deepEqual(
    Object.fromEntries(Object.entries(byId).map(([id, category]) => [id, [category.allocation, category.spent, category.remaining, category.status]])),
    {
      housing: [3000000, 2500000, 500000, 'warning'],
      food: [1200000, 1305000, -105000, 'over'],
      transport: [500000, 395000, 105000, 'on-track'],
      education: [600000, 430000, 170000, 'on-track'],
      lifestyle: [700000, 400000, 300000, 'on-track'],
    },
  )
  assert.equal(byId.housing.percent, 2500000 / 3000000 * 100)
  assert.equal(byId.food.percent, 1305000 / 1200000 * 100)
  assert.equal(byId.transport.status, 'on-track')
})

test('category spending adds up to actual spending without double counting', () => {
  const categoryTotal = november.categories.reduce((total, category) => total + category.spent, 0)
  assert.equal(categoryTotal, november.spent)
  assert.equal(november.allocated, november.categories.reduce((total, category) => total + category.allocation, 0))
})

test('planned, expected, unconfirmed, deleted and future expenses never count', () => {
  const copy = createDashboardWorkspace()
  copy.plans.push({ id: 'plan-big', name: 'Planned only', type: 'expense', amount: 100000000, date: '2026-11-20', category: 'housing', status: 'pending' })
  copy.transactions.push(
    { id: 'unconfirmed', name: 'Not confirmed', type: 'expense', category: 'food', amount: 500000, date: '2026-11-10', confirmed: false },
    { id: 'deleted', name: 'Deleted', type: 'expense', category: 'food', amount: 500000, date: '2026-11-10', confirmed: true, deleted: true },
    { id: 'future', name: 'Future', type: 'expense', category: 'food', amount: 500000, date: '2026-11-20', confirmed: true },
  )
  assert.deepEqual(selectBudgets(copy, '2026-11'), november)
})

test('unbudgeted confirmed spending counts toward overall remaining but not a category', () => {
  const copy = createDashboardWorkspace()
  copy.transactions.push({ id: 'health-visit', name: 'Clinic visit', type: 'expense', category: 'health', amount: 50000, date: '2026-11-10', confirmed: true })
  const data = selectBudgets(copy, '2026-11')
  assert.equal(data.spent, 5080000)
  assert.equal(data.remaining, 920000)
  assert.equal(data.categories.length, 5)
  assert.deepEqual(data.unbudgeted.map((category) => [category.id, category.spent]), [['health', 50000]])
})

test('zero-allocation categories are safe and report no allocation', () => {
  const copy = createDashboardWorkspace()
  copy.monthlyBudgets.push({ id: '2026-11-health', month: '2026-11', category: 'health', allocation: 0, archived: false })
  const data = selectBudgets(copy, '2026-11')
  const health = data.categories.find((category) => category.id === 'health')
  assert.equal(health.allocation, 0)
  assert.equal(health.spent, 0)
  assert.equal(health.remaining, 0)
  assert.equal(health.percent, 0)
  assert.equal(health.progress, 0)
  assert.equal(health.status, 'none')
  assert.equal(health.label, 'No allocation')
  assert.equal(data.allocated, 6000000)
})

test('month switching changes totals and category spending', () => {
  const september = selectBudgets(workspace, '2026-09')
  const october = selectBudgets(workspace, '2026-10')
  assert.equal(september.spent, 5400000)
  assert.equal(september.remaining, 600000)
  assert.equal(september.status, 'warning')
  assert.equal(october.spent, 6000000)
  assert.equal(october.remaining, 0)
  assert.equal(october.status, 'exhausted')
  assert.equal(october.label, 'Fully used')
  assert.equal(october.categories.find((category) => category.id === 'food').status, 'over')
})

test('available months are stable and newest first', () => {
  assert.deepEqual(availableMonths(workspace), ['2026-11', '2026-10', '2026-09'])
  const copy = createDashboardWorkspace()
  copy.monthlyBudgets = copy.monthlyBudgets.map((row) => ({ ...row, archived: true }))
  assert.deepEqual(availableMonths(copy), ['2026-11', '2026-10', '2026-09'])
})

test('available categories exclude active allocations for the selected month', () => {
  assert.deepEqual(availableBudgetCategories(categories, workspace.monthlyBudgets, '2026-11').map((category) => category.id), ['health'])
  assert.deepEqual(availableBudgetCategories(categories, workspace.monthlyBudgets, '2026-10').map((category) => category.id), ['health'])
  assert.deepEqual(createBudgetDraft(categories, workspace.monthlyBudgets, '2026-11'), { category: 'health', amount: '', note: '' })
})

test('validation accepts a new allocation and rejects duplicates and invalid amounts', () => {
  const draft = { category: 'health', amount: '2000.00', note: '  Clinic fund  ' }
  const result = validateBudget(draft, { categories, month: '2026-11', budgets: workspace.monthlyBudgets })
  assert.equal(result.valid, true)
  assert.deepEqual(result.value, { id: '2026-11-health', month: '2026-11', category: 'health', allocation: 200000, note: 'Clinic fund', archived: false })

  const duplicate = validateBudget({ ...draft, category: 'food' }, { categories, month: '2026-11', budgets: workspace.monthlyBudgets })
  assert.equal(duplicate.valid, false)
  assert.ok(duplicate.errors.category.includes('already has an allocation'))

  for (const amount of ['', '0', '-1', '1.234', 'abc']) {
    const invalid = validateBudget({ ...draft, amount }, { categories, month: '2026-11', budgets: workspace.monthlyBudgets })
    assert.equal(invalid.valid, false, amount)
    assert.ok(invalid.errors.amount, amount)
  }

  const missingCategory = validateBudget({ ...draft, category: '' }, { categories, month: '2026-11', budgets: workspace.monthlyBudgets })
  assert.ok(missingCategory.errors.category)

  const longNote = validateBudget({ ...draft, note: 'x'.repeat(161) }, { categories, month: '2026-11', budgets: workspace.monthlyBudgets })
  assert.ok(longNote.errors.note)

  assert.equal(formatAllocationInput(3000000), '30000.00')
  assert.equal(budgetId('2026-11', 'health'), '2026-11-health')
})

test('creating, editing, archiving and recreating allocations updates totals correctly', () => {
  const created = upsertBudget(workspace.monthlyBudgets, { id: '2026-11-health', month: '2026-11', category: 'health', allocation: 200000, note: '', archived: false })
  assert.equal(created.length, 16)
  let data = selectBudgets({ ...workspace, monthlyBudgets: created }, '2026-11')
  assert.equal(data.allocated, 6200000)
  assert.equal(data.remaining, 1170000)
  assert.equal(data.categories.find((category) => category.id === 'health').status, 'on-track')

  const edited = upsertBudget(created, { id: '2026-11-health', month: '2026-11', category: 'health', allocation: 250000, note: 'Updated', archived: false })
  assert.equal(edited.length, 16)
  data = selectBudgets({ ...workspace, monthlyBudgets: edited }, '2026-11')
  assert.equal(data.allocated, 6250000)
  assert.equal(data.remaining, 1220000)
  assert.equal(data.categories.find((category) => category.id === 'health').allocation, 250000)

  const archived = removeBudget(edited, '2026-11-health')
  assert.equal(archived.find((row) => row.id === '2026-11-health').archived, true)
  data = selectBudgets({ ...workspace, monthlyBudgets: archived }, '2026-11')
  assert.equal(data.categories.length, 5)
  assert.equal(data.allocated, 6000000)
  assert.deepEqual(availableMonths({ ...workspace, monthlyBudgets: archived }), ['2026-11', '2026-10', '2026-09'])

  const recreated = upsertBudget(archived, { id: '2026-11-health', month: '2026-11', category: 'health', allocation: 300000, note: '', archived: false })
  assert.equal(recreated.filter((row) => row.month === '2026-11' && row.category === 'health').length, 1)
  data = selectBudgets({ ...workspace, monthlyBudgets: recreated }, '2026-11')
  assert.equal(data.categories.length, 6)
  assert.equal(data.allocated, 6300000)
})

test('upsert refuses an active duplicate category and month', () => {
  const created = upsertBudget(workspace.monthlyBudgets, { id: '2026-11-health', month: '2026-11', category: 'health', allocation: 200000, note: '', archived: false })
  assert.throws(
    () => upsertBudget(created, { id: 'different-id', month: '2026-11', category: 'health', allocation: 100000, note: '', archived: false }),
    RangeError,
  )
})

test('removing all allocations leaves overall remaining negative without breaking calculations', () => {
  const empty = workspace.monthlyBudgets.map((row) => ({ ...row, archived: true }))
  const data = selectBudgets({ ...workspace, monthlyBudgets: empty }, '2026-11')
  assert.equal(data.allocated, 0)
  assert.equal(data.spent, 5030000)
  assert.equal(data.remaining, -5030000)
  assert.equal(data.status, 'none')
  assert.equal(data.categories.length, 0)
  assert.equal(data.unbudgeted.length, 5)
})