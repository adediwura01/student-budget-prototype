export function formatMoney(cents, showCents = true) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: showCents ? 2 : 0,
    maximumFractionDigits: showCents ? 2 : 0,
  }).format(cents / 100)
}

export function monthKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

export function monthLabel(month, short = false) {
  const [year, number] = month.split('-').map(Number)
  return new Date(year, number - 1, 1).toLocaleDateString('en-US', { month: short ? 'short' : 'long', year: 'numeric' })
}

export function formatDate(date) {
  const [year, month, day] = date.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function previousMonth(month) {
  const [year, number] = month.split('-').map(Number)
  return monthKey(new Date(year, number - 2, 1))
}

export function getMonthTransactions(transactions, month) {
  return transactions.filter((transaction) => transaction.date.startsWith(`${month}-`))
}

export function getTotals(transactions) {
  let income = 0
  let expense = 0
  for (const transaction of transactions) {
    if (transaction.type === 'income') income += transaction.amount
    else expense += transaction.amount
  }
  return { income, expense, balance: income - expense }
}

export function getChange(current, previous) {
  return previous === 0 ? null : ((current - previous) / Math.abs(previous)) * 100
}

export function getFlowData(transactions, month, interval = 'weekly') {
  const [year, number] = month.split('-').map(Number)
  const days = new Date(year, number, 0).getDate()
  const step = interval === 'weekly' ? 7 : 1
  const data = Array.from({ length: Math.ceil(days / step) }, (_, index) => {
    const start = index * step + 1
    const end = Math.min(start + step - 1, days)
    const label = step === 1 ? String(start).padStart(2, '0') : `${String(start).padStart(2, '0')} - ${String(end).padStart(2, '0')}`
    return { label, income: 0, expense: 0 }
  })
  for (const transaction of getMonthTransactions(transactions, month)) {
    const index = Math.floor((Number(transaction.date.slice(8)) - 1) / step)
    if (data[index]) data[index][transaction.type] += transaction.amount
  }
  return data
}

export function transactionsCsv(transactions, categories) {
  const quote = (value) => `"${String(value).replaceAll('"', '""')}"`
  const rows = transactions.map((transaction) => {
    // Prevent descriptions from becoming spreadsheet formulas when a CSV is opened.
    const name = /^[=+\-@\t\r\n]/.test(transaction.name) ? `'${transaction.name}` : transaction.name
    return [transaction.date, name, transaction.type, categories.find((category) => category.id === transaction.category)?.name ?? transaction.category,
      `${transaction.type === 'expense' ? '-' : ''}${(transaction.amount / 100).toFixed(2)}`]
  })
  return [['Date', 'Description', 'Type', 'Category', 'Amount (USD)'], ...rows].map((row) => row.map(quote).join(',')).join('\r\n')
}
