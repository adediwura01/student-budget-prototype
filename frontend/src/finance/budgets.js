// Pure budget selectors and allocation editing. Actual expenses only; plans never count.
import { budgetState, checkedKobo, dateNumber, isoDate, monthBounds, monthName } from './dashboard.js'
import { parseAmountKobo } from './transactions.js'

const dayMs = 86400000

function sum(rows, key) {
  return rows.reduce((total, row) => {
    const value = checkedKobo(row[key])
    return checkedKobo(total + value)
  }, 0)
}

export function availableMonths(workspace) {
  const latest = workspace.asOf.slice(0, 7)
  const months = new Set(workspace.monthlyBudgets.map((row) => row.month))
  workspace.transactions.forEach((row) => months.add(row.date.slice(0, 7)))
  months.add(latest)
  return [...months].filter((month) => month <= latest).sort().reverse()
}

export function selectBudgets(workspace, month) {
  const { start, end } = monthBounds(month)
  const cutoff = Math.min(dateNumber(workspace.asOf), end - dayMs)
  const asOf = isoDate(cutoff)
  const actual = workspace.transactions.filter((row) => {
    if (row.confirmed !== true || row.deleted) return false
    const date = dateNumber(row.date)
    return date >= start && date < end && date <= cutoff
  })
  const expenses = actual.filter((row) => row.type === 'expense')
  const spent = sum(expenses, 'amount')
  const rows = workspace.monthlyBudgets.filter((row) => row.month === month && !row.archived)
  const allocated = sum(rows, 'allocation')

  const categories = rows.map((row) => {
    const category = workspace.categories.find((item) => item.id === row.category)
    if (!category) throw new TypeError('Unknown budget category')
    const categorySpent = sum(expenses.filter((item) => item.category === row.category), 'amount')
    return {
      ...category,
      budgetId: row.id,
      allocation: row.allocation,
      spent: categorySpent,
      remaining: checkedKobo(row.allocation - categorySpent),
      note: row.note ?? '',
      ...budgetState(categorySpent, row.allocation),
    }
  })

  const budgeted = new Set(rows.map((row) => row.category))
  const unbudgeted = workspace.categories
    .filter((category) => !budgeted.has(category.id))
    .map((category) => ({ ...category, spent: sum(expenses.filter((row) => row.category === category.id), 'amount') }))
    .filter((category) => category.spent > 0)

  const remaining = checkedKobo(allocated - spent)

  return {
    month,
    monthLabel: monthName(month),
    asOf,
    allocated,
    spent,
    remaining,
    categories,
    unbudgeted,
    months: availableMonths(workspace),
    ...budgetState(spent, allocated),
  }
}

export function budgetId(month, category) {
  return `${month}-${category}`
}

export function availableBudgetCategories(categories, budgets, month) {
  return categories.filter((category) => !budgets.some((row) => !row.archived && row.month === month && row.category === category.id))
}

export function createBudgetDraft(categories, budgets, month) {
  const available = availableBudgetCategories(categories, budgets, month)
  return { category: available[0]?.id ?? '', amount: '', note: '' }
}

export function formatAllocationInput(kobo) {
  checkedKobo(kobo)
  return (kobo / 100).toFixed(2)
}

export function validateBudget(draft, { categories, month, budgets, editingId = null }) {
  const errors = {}
  const category = categories.find((item) => item.id === draft.category)
  if (!month) errors.month = 'Choose a month.'
  if (!category) errors.category = 'Choose a category.'
  else if (budgets.some((row) => !row.archived && row.month === month && row.category === category.id && row.id !== editingId)) {
    errors.category = 'This category already has an allocation for the selected month.'
  }

  const amount = parseAmountKobo(draft.amount)
  if (!amount.ok) errors.amount = amount.error

  const note = (draft.note ?? '').trim()
  if (note.length > 160) errors.note = 'Keep the note to 160 characters or fewer.'

  const valid = Object.keys(errors).length === 0
  return {
    errors,
    valid,
    value: valid
      ? { id: editingId ?? budgetId(month, category.id), month, category: category.id, allocation: amount.kobo, note, archived: false }
      : null,
  }
}

export function upsertBudget(rows, record) {
  if (rows.some((row) => !row.archived && row.month === record.month && row.category === record.category && row.id !== record.id)) {
    throw new RangeError('A budget already exists for this category and month')
  }
  return [...rows.filter((row) => !(row.month === record.month && row.category === record.category)), record]
}

export function removeBudget(rows, id) {
  return rows.map((row) => (row.id === id ? { ...row, archived: true } : row))
}