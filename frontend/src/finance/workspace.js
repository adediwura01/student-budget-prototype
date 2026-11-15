const allowedTypes = new Set(['income', 'expense'])

function assertType(type) {
  if (!allowedTypes.has(type)) throw new TypeError('Unknown transaction type')
}

// Every month with data, newest first. Future months appear when a plan is dated ahead.
export function workspaceMonths(workspace) {
  const months = new Set([workspace.asOf.slice(0, 7)])
  ;(workspace.transactions ?? []).forEach((row) => months.add(row.date.slice(0, 7)))
  ;(workspace.monthlyBudgets ?? []).forEach((row) => months.add(row.month))
  ;(workspace.plans ?? []).forEach((row) => months.add(row.date.slice(0, 7)))
  return [...months].sort().reverse()
}

export function addTransaction(rows, record) {
  return [...rows, record]
}

export function updateTransaction(rows, record) {
  if (!record?.id) throw new TypeError('Transaction id is required')
  assertType(record.type)
  let found = false
  const next = rows.map((row) => {
    if (row.id !== record.id) return row
    found = true
    return { ...row, ...record }
  })
  if (!found) throw new RangeError('Unknown transaction')
  return next
}

export function deleteTransaction(rows, id) {
  let found = false
  const next = rows.map((row) => {
    if (row.id !== id) return row
    found = true
    return { ...row, deleted: true }
  })
  if (!found) throw new RangeError('Unknown transaction')
  return next
}