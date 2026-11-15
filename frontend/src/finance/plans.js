// Pure helpers for the financial planning screen. Plans never move real money:
// only confirming a plan creates an actual transaction.
import { checkedKobo, dateNumber, monthName, shortDate } from './dashboard.js'
import { allCategories, categoriesForType, categoryIndex, parseAmountKobo } from './transactions.js'
import { workspaceMonths } from './workspace.js'

export const planTypes = ['income', 'expense']
export const planStatuses = ['pending', 'confirmed']
export const planSorts = ['date', 'date-desc', 'amount-high', 'amount-low']

const sortLabels = {
  date: 'Expected date (soonest)',
  'date-desc': 'Expected date (latest)',
  'amount-high': 'Amount (highest)',
  'amount-low': 'Amount (lowest)',
}

export function planSortLabel(sort) {
  return sortLabels[sort] ?? sortLabels.date
}

function sum(rows, key) {
  return rows.reduce((total, row) => checkedKobo(total + checkedKobo(row[key], true)), 0)
}

function assertType(type) {
  if (!planTypes.includes(type)) throw new TypeError('Unknown plan type')
}

function assertDate(date) {
  dateNumber(date)
}

export function planTransactionId(planId) {
  return `actual-${planId}`
}

export function describePlan(plan, categories, asOf) {
  assertType(plan.type)
  checkedKobo(plan.amount, true)
  assertDate(plan.date)
  const index = categories instanceof Map ? categories : categoryIndex(categories)
  const category = index.get(plan.category)
  const status = planStatuses.includes(plan.status) ? plan.status : 'pending'
  const cutoff = asOf ? dateNumber(asOf) : null
  return {
    ...plan,
    note: plan.note ?? '',
    status,
    statusLabel: status === 'confirmed' ? 'Confirmed' : 'Pending',
    typeLabel: plan.type === 'income' ? 'Expected income' : 'Planned expense',
    categoryName: category?.name ?? (plan.type === 'income' ? 'Income' : 'Uncategorised'),
    icon: category?.icon ?? (plan.type === 'income' ? 'income' : 'expense'),
    tone: category?.tone ?? (plan.type === 'income' ? 'green' : 'purple'),
    dateLabel: shortDate(plan.date),
    needsAttention: status === 'pending' && cutoff !== null && dateNumber(plan.date) <= cutoff,
    actualAmount: plan.actualAmount ?? null,
  }
}

export function selectPlans(workspace, month) {
  const categories = allCategories(workspace)
  const index = categoryIndex(categories)
  const cutoff = dateNumber(workspace.asOf)

  const items = (workspace.plans ?? [])
    .filter((plan) => plan.date.startsWith(`${month}-`))
    .map((plan) => describePlan(plan, index, workspace.asOf))
    .sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id))

  const pending = items.filter((plan) => plan.status === 'pending')
  const confirmed = items.filter((plan) => plan.status === 'confirmed')
  const upcoming = pending.filter((plan) => dateNumber(plan.date) > cutoff)
  const attention = pending.filter((plan) => dateNumber(plan.date) <= cutoff)

  const expectedIncome = sum(pending.filter((plan) => plan.type === 'income'), 'amount')
  const plannedExpenses = sum(pending.filter((plan) => plan.type === 'expense'), 'amount')
  const confirmedValue = (plan) => checkedKobo(plan.actualAmount ?? plan.amount, true)
  const confirmedIncome = confirmed.filter((plan) => plan.type === 'income').reduce((total, plan) => checkedKobo(total + confirmedValue(plan)), 0)
  const confirmedExpenses = confirmed.filter((plan) => plan.type === 'expense').reduce((total, plan) => checkedKobo(total + confirmedValue(plan)), 0)

  return {
    month,
    monthLabel: monthName(month),
    asOf: workspace.asOf,
    asOfLabel: shortDate(workspace.asOf),
    categories,
    items,
    pending,
    confirmed,
    months: workspaceMonths(workspace),
    expectedIncome,
    plannedExpenses,
    projected: checkedKobo(expectedIncome - plannedExpenses),
    upcomingCount: upcoming.length,
    needsAttentionCount: attention.length,
    attention,
    confirmedCount: confirmed.length,
    confirmedIncome,
    confirmedExpenses,
  }
}

export function planFiltersEmpty() {
  return { search: '', type: 'all', status: 'all', category: 'all', sort: 'date' }
}

export function filterPlans(rows, filters) {
  const search = filters.search.trim().toLocaleLowerCase('en-NG')
  return rows.filter((row) => {
    if (search && !row.name.toLocaleLowerCase('en-NG').includes(search)) return false
    if (filters.type !== 'all' && row.type !== filters.type) return false
    if (filters.status !== 'all' && row.status !== filters.status) return false
    if (filters.category !== 'all' && row.category !== filters.category) return false
    return true
  })
}

export function sortPlans(rows, sort) {
  const sorted = [...rows]
  const byDate = (a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id)

  if (sort === 'date') sorted.sort(byDate)
  else if (sort === 'date-desc') sorted.sort((a, b) => byDate(b, a))
  else if (sort === 'amount-high') sorted.sort((a, b) => b.amount - a.amount || byDate(a, b))
  else if (sort === 'amount-low') sorted.sort((a, b) => a.amount - b.amount || byDate(a, b))
  else throw new RangeError('Unknown plan sort')

  return sorted
}

export function hasActivePlanFilters(filters) {
  return Boolean(filters.search.trim() || filters.type !== 'all' || filters.status !== 'all' || filters.category !== 'all')
}

export function activePlanFilterCount(filters) {
  return [filters.search.trim(), filters.type !== 'all', filters.status !== 'all', filters.category !== 'all'].filter(Boolean).length
}

export function createPlanDraft(type, categories, asOf) {
  const allowed = categoriesForType(categories, type)
  return { type, description: '', amount: '', category: allowed[0]?.id ?? '', date: asOf, note: '' }
}

export function planDraftFrom(plan) {
  return {
    type: plan.type,
    description: plan.name,
    amount: (plan.amount / 100).toFixed(2),
    category: plan.category,
    date: plan.date,
    note: plan.note ?? '',
  }
}

export function validatePlan(draft, { categories }) {
  const errors = {}
  const type = planTypes.includes(draft.type) ? draft.type : null
  const description = draft.description.trim()

  if (!type) errors.type = 'Choose expected income or planned expense.'
  if (!description) errors.description = 'Enter a description.'
  else if (description.length > 80) errors.description = 'Keep the description to 80 characters or fewer.'

  const allowed = type ? categoriesForType(categories, type) : []
  if (!draft.category) errors.category = 'Choose a category.'
  else if (!allowed.some((category) => category.id === draft.category)) errors.category = `Choose a ${type ?? 'valid'} category.`

  const amount = parseAmountKobo(draft.amount)
  if (!amount.ok) errors.amount = amount.error

  if (!draft.date) errors.date = 'Choose an expected date.'
  else if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.date)) errors.date = 'Enter a valid date.'
  else {
    try { assertDate(draft.date) } catch { errors.date = 'Enter a valid date.' }
  }

  const note = (draft.note ?? '').trim()
  if (note.length > 160) errors.note = 'Keep the note to 160 characters or fewer.'

  const valid = Object.keys(errors).length === 0
  return {
    errors,
    valid,
    value: valid ? { name: description, type, category: draft.category, amount: amount.kobo, date: draft.date, note } : null,
  }
}

let sequence = 0

export function createPlanRecord(value) {
  sequence += 1
  return { id: `plan-${Date.now().toString(36)}-${sequence}`, ...value, status: 'pending', actualAmount: null, transactionId: null }
}

export function upsertPlan(rows, record) {
  const existing = rows.find((row) => row.id === record.id)
  if (existing?.status === 'confirmed') throw new RangeError('Confirmed plans cannot be edited')
  if (existing) return rows.map((row) => (row.id === record.id ? { ...row, ...record } : row))
  return [...rows, record]
}

export function removePlan(rows, id) {
  const target = rows.find((row) => row.id === id)
  if (!target) throw new RangeError('Unknown plan')
  if (target.status === 'confirmed') throw new RangeError('Confirmed plans cannot be deleted')
  return rows.filter((row) => row.id !== id)
}

export function findPlanTransaction(transactions, plan) {
  if (!plan?.transactionId) return null
  const transaction = transactions.find((row) => row.id === plan.transactionId)
  if (!transaction || transaction.deleted) return null
  if (transaction.planId !== plan.id) return null
  return transaction
}

export function confirmPlan({ plans, transactions, planId, amount, asOf }) {
  const plan = plans.find((row) => row.id === planId)
  if (!plan) throw new RangeError('Unknown plan')
  if (plan.status === 'confirmed') throw new RangeError('This plan is already confirmed')
  assertType(plan.type)
  assertDate(plan.date)

  const value = checkedKobo(amount, true)
  const existing = transactions.find((row) => row.planId === planId)
  if (existing && !existing.deleted) throw new RangeError('A transaction already exists for this plan')

  const transaction = {
    id: existing?.id ?? planTransactionId(planId),
    planId,
    name: plan.name,
    type: plan.type,
    category: plan.category,
    amount: value,
    date: asOf,
    note: plan.note ?? '',
    confirmed: true,
    deleted: false,
  }

  return {
    plans: plans.map((row) => (row.id === planId
      ? { ...row, status: 'confirmed', actualAmount: value, transactionId: transaction.id, confirmedDate: asOf }
      : row)),
    transactions: existing
      ? transactions.map((row) => (row.id === existing.id ? transaction : row))
      : [...transactions, transaction],
    transaction,
  }
}

export function undoPlanConfirmation({ plans, transactions, planId }) {
  const plan = plans.find((row) => row.id === planId)
  if (!plan) throw new RangeError('Unknown plan')
  if (plan.status !== 'confirmed') throw new RangeError('Only confirmed plans can be undone')
  const transaction = findPlanTransaction(transactions, plan)
  if (!transaction) throw new RangeError('The linked transaction can no longer be identified')

  return {
    plans: plans.map((row) => (row.id === planId
      ? { ...row, status: 'pending', actualAmount: null, transactionId: null, confirmedDate: null }
      : row)),
    transactions: transactions.map((row) => (row.id === transaction.id ? { ...row, deleted: true } : row)),
    transaction,
  }
}