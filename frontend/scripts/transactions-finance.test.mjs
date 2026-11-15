import test from 'node:test'
import assert from 'node:assert/strict'
import { createDashboardWorkspace } from '../src/demo/dashboard.js'
import {
  activeFilterCount,
  allCategories,
  categoriesForType,
  categoryIndex,
  createTransactionDraft,
  createTransactionRecord,
  describeTransaction,
  filterTransactions,
  formatTransactionDate,
  hasActiveFilters,
  parseAmountKobo,
  sortTransactions,
  summariseTransactions,
  validateTransaction,
} from '../src/finance/transactions.js'
import { addTransaction, deleteTransaction, updateTransaction } from '../src/finance/workspace.js'

const workspace = createDashboardWorkspace()
const categories = allCategories(workspace)
const index = categoryIndex(categories)
const rows = workspace.transactions.map((row) => describeTransaction(row, index))
const baseFilters = { search: '', type: 'all', category: 'all', from: '', to: '', sort: 'newest' }

test('demo workspace exposes expense and income categories without changing budget categories', () => {
  assert.equal(workspace.categories.length, 6)
  assert.equal(workspace.incomeCategories.length, 3)
  assert.equal(categories.length, 9)
  assert.equal(categoriesForType(categories, 'expense').length, 6)
  assert.equal(categoriesForType(categories, 'income').length, 3)
})

test('every demo transaction is described with a readable category, icon and date', () => {
  assert.equal(rows.length, 32)
  assert.equal(rows.find((row) => row.id === 'nov12a').categoryName, 'Scholarship')
  assert.equal(rows.find((row) => row.id === 'nov12a').icon, 'book')
  assert.equal(rows.find((row) => row.id === 'nov13a').categoryName, 'Food & groceries')
  assert.equal(rows.find((row) => row.id === 'nov13a').icon, 'food')
  assert.equal(rows.find((row) => row.id === 'nov13a').typeLabel, 'Expense')
  assert.equal(rows.find((row) => row.id === 'nov13a').dateLabel, '13 Nov 2026')
  assert.equal(formatTransactionDate('2026-11-13'), '13 Nov 2026')
})

test('search is case-insensitive and matches descriptions only', () => {
  const matches = filterTransactions(rows, { ...baseFilters, search: 'GROCERIES' })
  assert.ok(matches.length > 0)
  assert.ok(matches.every((row) => row.name.toLocaleLowerCase('en-NG').includes('groceries')))
  assert.deepEqual(filterTransactions(rows, { ...baseFilters, search: 'zzzz' }), [])
})

test('type, category and inclusive date filters combine correctly', () => {
  const income = filterTransactions(rows, { ...baseFilters, type: 'income' })
  assert.ok(income.length > 0)
  assert.ok(income.every((row) => row.type === 'income'))

  const food = filterTransactions(rows, { ...baseFilters, category: 'food' })
  assert.ok(food.length > 0)
  assert.ok(food.every((row) => row.category === 'food'))

  const range = filterTransactions(rows, { ...baseFilters, from: '2026-11-12', to: '2026-11-13' })
  assert.ok(range.length > 0)
  assert.ok(range.every((row) => row.date >= '2026-11-12' && row.date <= '2026-11-13'))

  const combined = filterTransactions(rows, { ...baseFilters, type: 'expense', category: 'food', from: '2026-11-01' })
  assert.ok(combined.length > 0)
  assert.ok(combined.every((row) => row.type === 'expense' && row.category === 'food' && row.date >= '2026-11-01'))
})

test('all four sort orders are stable and amount sorting is numeric', () => {
  assert.equal(sortTransactions(rows, 'newest')[0].id, 'nov13c')
  assert.equal(sortTransactions(rows, 'oldest')[0].id, 'sep01')
  assert.equal(sortTransactions(rows, 'highest')[0].amount, 4500000)
  assert.equal(sortTransactions(rows, 'highest')[0].id, 'nov01')
  assert.equal(sortTransactions(rows, 'lowest')[0].amount, 80000)
  assert.equal(sortTransactions(rows, 'lowest')[0].id, 'nov11')
  assert.throws(() => sortTransactions(rows, 'sideways'), RangeError)
})

test('summaries are exact integer-kobo totals', () => {
  const summary = summariseTransactions(rows)
  const expectedIncome = workspace.transactions.filter((row) => row.type === 'income').reduce((total, row) => total + row.amount, 0)
  const expectedExpenses = workspace.transactions.filter((row) => row.type === 'expense').reduce((total, row) => total + row.amount, 0)
  assert.deepEqual(summary, { income: expectedIncome, expenses: expectedExpenses, net: expectedIncome - expectedExpenses, count: 32 })
  assert.equal(summariseTransactions([]).net, 0)
})

test('filter helpers report active filters', () => {
  assert.equal(hasActiveFilters(baseFilters), false)
  assert.equal(activeFilterCount(baseFilters), 0)
  const active = { ...baseFilters, search: ' rent ', type: 'expense', from: '2026-11-01' }
  assert.equal(hasActiveFilters(active), true)
  assert.equal(activeFilterCount(active), 3)
})

test('amount parsing accepts two decimal places and rejects everything else', () => {
  assert.equal(parseAmountKobo('1250.50').kobo, 125050)
  assert.equal(parseAmountKobo('1,250.5').kobo, 125050)
  assert.equal(parseAmountKobo('₦ 1,250.50 ').kobo, 125050)
  assert.equal(parseAmountKobo('1').kobo, 100)
  for (const value of ['', '0', '0.00', '12.345', '-5', 'abc', '1.2.3']) {
    assert.equal(parseAmountKobo(value).ok, false, value)
  }
})

test('drafts default to the demo date and the first matching category', () => {
  const expense = createTransactionDraft('expense', categories, '2026-11-13')
  assert.deepEqual(expense, { type: 'expense', description: '', amount: '', category: 'housing', date: '2026-11-13', note: '' })
  const income = createTransactionDraft('income', categories, '2026-11-13')
  assert.equal(income.category, 'allowance')
})

test('validation rejects missing, oversized, future and mismatched values', () => {
  const valid = validateTransaction(
    { type: 'expense', description: '  Test entry  ', amount: '10.00', category: 'housing', date: '2026-11-13', note: '' },
    { categories, asOf: '2026-11-13' },
  )
  assert.equal(valid.valid, true)
  assert.deepEqual(valid.value, { name: 'Test entry', type: 'expense', category: 'housing', amount: 1000, date: '2026-11-13', note: '' })

  const missing = validateTransaction(createTransactionDraft('expense', categories, '2026-11-13'), { categories, asOf: '2026-11-13' })
  assert.equal(missing.valid, false)
  assert.ok(missing.errors.description)
  assert.ok(missing.errors.amount)

  const oversized = validateTransaction(
    { type: 'expense', description: 'x'.repeat(81), amount: '1', category: 'housing', date: '2026-11-13', note: '' },
    { categories, asOf: '2026-11-13' },
  )
  assert.ok(oversized.errors.description)

  const future = validateTransaction(
    { type: 'expense', description: 'Future', amount: '1', category: 'housing', date: '2026-11-14', note: '' },
    { categories, asOf: '2026-11-13' },
  )
  assert.ok(future.errors.date)

  const mismatched = validateTransaction(
    { type: 'income', description: 'Mismatch', amount: '1', category: 'housing', date: '2026-11-13', note: '' },
    { categories, asOf: '2026-11-13' },
  )
  assert.ok(mismatched.errors.category)

  const longNote = validateTransaction(
    { type: 'expense', description: 'Note', amount: '1', category: 'housing', date: '2026-11-13', note: 'x'.repeat(161) },
    { categories, asOf: '2026-11-13' },
  )
  assert.ok(longNote.errors.note)
})

test('new records are confirmed demo rows with unique ids', () => {
  const first = createTransactionRecord({ name: 'One', type: 'expense', category: 'food', amount: 1000, date: '2026-11-13', note: '' })
  const second = createTransactionRecord({ name: 'Two', type: 'income', category: 'allowance', amount: 2000, date: '2026-11-13', note: '' })
  assert.notEqual(first.id, second.id)
  assert.equal(first.confirmed, true)
  assert.equal(first.deleted, false)
})

test('transaction workspace helpers add, update and archive records without mutating the original rows', () => {
  const original = createDashboardWorkspace()
  const added = addTransaction(original.transactions, createTransactionRecord({ name: 'Extra', type: 'expense', category: 'food', amount: 1000, date: '2026-11-13', note: '' }))
  const target = added.find((row) => row.name === 'Extra')
  const updated = updateTransaction(added, { ...target, amount: 2500, category: 'transport' })
  const deleted = deleteTransaction(updated, target.id)
  assert.equal(original.transactions.length, 32)
  assert.equal(added.length, 33)
  assert.equal(updated.find((row) => row.id === target.id).amount, 2500)
  assert.equal(updated.find((row) => row.id === target.id).category, 'transport')
  assert.equal(deleted.find((row) => row.id === target.id).deleted, true)
  assert.equal(deleted.filter((row) => !row.deleted).length, updated.filter((row) => !row.deleted).length - 1)
  assert.throws(() => updateTransaction(original.transactions, { ...target, id: 'missing' }), RangeError)
  assert.throws(() => deleteTransaction(original.transactions, 'missing'), RangeError)
  assert.throws(() => updateTransaction(original.transactions, { ...target, type: 'other' }), TypeError)
})