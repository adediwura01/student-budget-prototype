// Pure helpers for the transactions screen. Demo-only; nothing is persisted.
import { checkedKobo, dateNumber } from './dashboard.js'

export const transactionTypes = ['income', 'expense']
export const transactionSorts = ['newest', 'oldest', 'highest', 'lowest']

export function allCategories(workspace) {
  return [...workspace.categories, ...(workspace.incomeCategories ?? [])]
}

function categoryType(category) {
  return category.type ?? 'expense'
}

export function categoriesForType(categories, type) {
  return categories.filter((category) => categoryType(category) === type)
}

export function categoryIndex(categories) {
  return new Map(categories.map((category) => [category.id, category]))
}

const dateFormat = new Intl.DateTimeFormat('en-NG', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })

export function formatTransactionDate(date) {
  return dateFormat.format(dateNumber(date))
}

export function describeTransaction(row, index) {
  const category = index.get(row.category)
  const typeLabel = row.type === 'income' ? 'Income' : 'Expense'
  return {
    ...row,
    typeLabel,
    categoryName: category?.name ?? (row.type === 'income' ? 'Income' : 'Uncategorised'),
    icon: category?.icon ?? (row.type === 'income' ? 'income' : 'expense'),
    tone: category?.tone ?? (row.type === 'income' ? 'green' : 'purple'),
    dateLabel: formatTransactionDate(row.date),
  }
}

export function summariseTransactions(rows) {
  const income = rows.filter((row) => row.type === 'income').reduce((total, row) => checkedKobo(total + checkedKobo(row.amount, true)), 0)
  const expenses = rows.filter((row) => row.type === 'expense').reduce((total, row) => checkedKobo(total + checkedKobo(row.amount, true)), 0)
  return { income, expenses, net: checkedKobo(income - expenses), count: rows.length }
}

function bound(value) {
  if (!value) return null
  try { return dateNumber(value) } catch { return null }
}

export function filterTransactions(rows, filters) {
  const search = filters.search.trim().toLocaleLowerCase('en-NG')
  const from = bound(filters.from)
  const to = bound(filters.to)

  return rows.filter((row) => {
    if (search && !row.name.toLocaleLowerCase('en-NG').includes(search)) return false
    if (filters.type !== 'all' && row.type !== filters.type) return false
    if (filters.category !== 'all' && row.category !== filters.category) return false
    const date = dateNumber(row.date)
    if (from !== null && date < from) return false
    if (to !== null && date > to) return false
    return true
  })
}

export function sortTransactions(rows, sort) {
  const sorted = [...rows]
  const newest = (a, b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id)
  const oldest = (a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id)

  if (sort === 'oldest') sorted.sort(oldest)
  else if (sort === 'highest') sorted.sort((a, b) => b.amount - a.amount || newest(a, b))
  else if (sort === 'lowest') sorted.sort((a, b) => a.amount - b.amount || newest(a, b))
  else if (sort === 'newest') sorted.sort(newest)
  else throw new RangeError('Unknown transaction sort')

  return sorted
}

export function hasActiveFilters(filters) {
  return Boolean(filters.search.trim() || filters.type !== 'all' || filters.category !== 'all' || filters.from || filters.to)
}

export function activeFilterCount(filters) {
  return [filters.search.trim(), filters.type !== 'all', filters.category !== 'all', filters.from, filters.to].filter(Boolean).length
}

export function parseAmountKobo(raw) {
  const text = String(raw ?? '').trim().replace(/[,\s₦]/g, '')
  if (!text) return { ok: false, error: 'Enter an amount.' }
  if (!/^\d+(\.\d{1,2})?$/.test(text)) return { ok: false, error: 'Enter an amount with up to two decimal places.' }
  const [whole, fraction = ''] = text.split('.')
  const kobo = Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
  if (!Number.isSafeInteger(kobo)) return { ok: false, error: 'Enter a smaller amount.' }
  if (kobo <= 0) return { ok: false, error: 'Enter an amount greater than zero.' }
  return { ok: true, kobo }
}

export function createTransactionDraft(type, categories, asOf) {
  const allowed = categoriesForType(categories, type)
  return { type, description: '', amount: '', category: allowed[0]?.id ?? '', date: asOf, note: '' }
}

export function validateTransaction(draft, { categories, asOf }) {
  const errors = {}
  const type = transactionTypes.includes(draft.type) ? draft.type : null
  const description = draft.description.trim()

  if (!type) errors.type = 'Choose income or expense.'
  if (!description) errors.description = 'Enter a description.'
  else if (description.length > 80) errors.description = 'Keep the description to 80 characters or fewer.'

  const allowed = type ? categoriesForType(categories, type) : []
  if (!draft.category) errors.category = 'Choose a category.'
  else if (!allowed.some((category) => category.id === draft.category)) errors.category = `Choose a ${type ?? 'valid'} category.`

  const amount = parseAmountKobo(draft.amount)
  if (!amount.ok) errors.amount = amount.error

  if (!draft.date) errors.date = 'Choose a date.'
  else if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.date)) errors.date = 'Enter a valid date.'
  else {
    try {
      if (dateNumber(draft.date) > dateNumber(asOf)) errors.date = 'Choose today or an earlier demo date.'
    } catch {
      errors.date = 'Enter a valid date.'
    }
  }

  const note = draft.note.trim()
  if (note.length > 160) errors.note = 'Keep the note to 160 characters or fewer.'

  const valid = Object.keys(errors).length === 0
  return {
    errors,
    valid,
    value: valid ? { name: description, type, category: draft.category, amount: amount.kobo, date: draft.date, note } : null,
  }
}

let sequence = 0

export function createTransactionRecord(value) {
  sequence += 1
  return { id: `demo-${Date.now().toString(36)}-${sequence}`, ...value, confirmed: true, deleted: false }
}