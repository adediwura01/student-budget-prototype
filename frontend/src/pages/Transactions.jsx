import { useMemo, useState } from 'react'
import PageHeader from '../components/PageHeader'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import TransactionSummary from '../components/transactions/TransactionSummary'
import TransactionFilters from '../components/transactions/TransactionFilters'
import TransactionList from '../components/transactions/TransactionList'
import AddTransactionModal from '../components/transactions/AddTransactionModal'
import { DeleteTransactionModal, TransactionEditModal } from '../components/transactions/TransactionModal'
import { money } from '../finance/dashboard'
import {
  activeFilterCount,
  allCategories,
  categoryIndex,
  createTransactionRecord,
  describeTransaction,
  filterTransactions,
  formatTransactionDate,
  hasActiveFilters,
  sortTransactions,
  summariseTransactions,
} from '../finance/transactions'
import '../transactions.css'

const defaultFilters = { search: '', type: 'all', category: 'all', from: '', to: '', sort: 'newest' }

export default function Transactions({ workspace, onAdd, onUpdate, onDelete, onNotify }) {
  const [filters, setFilters] = useState(defaultFilters)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const categories = useMemo(() => allCategories(workspace), [workspace])
  const index = useMemo(() => categoryIndex(categories), [categories])
  const rows = useMemo(
    () => workspace.transactions
      .filter((row) => row.confirmed && !row.deleted && row.date <= workspace.asOf)
      .map((row) => describeTransaction(row, index)),
    [workspace.transactions, workspace.asOf, index],
  )
  const visible = useMemo(() => sortTransactions(filterTransactions(rows, filters), filters.sort), [rows, filters])
  const summary = useMemo(() => summariseTransactions(visible), [visible])

  const filtered = hasActiveFilters(filters)
  const dateError = filters.from && filters.to && filters.from > filters.to ? 'Start date must be on or before end date.' : ''
  const active = activeFilterCount(filters)

  function update(key, value) {
    setFilters((previous) => ({ ...previous, [key]: value }))
  }

  function addTransaction(value) {
    const record = createTransactionRecord(value)
    const matchesView = filterTransactions([describeTransaction(record, index)], filters).length > 0
    onAdd(record)
    if (!matchesView) setFilters(defaultFilters)
    setAdding(false)
    onNotify(
      'Transaction added',
      `${value.name} · ${value.type === 'income' ? 'Income' : 'Expense'} ${money(value.amount, true)} on ${formatTransactionDate(value.date)}. Demo only — nothing was saved to a server.`,
    )
  }

  function editTransaction(value) {
    const record = {
      ...editing,
      name: value.name,
      type: value.type,
      category: value.category,
      amount: value.amount,
      date: value.date,
      note: value.note,
    }
    onUpdate(record)
    setEditing(null)
    onNotify(
      'Transaction updated',
      `${record.name} · ${record.type === 'income' ? 'Income' : 'Expense'} ${money(record.amount, true)} on ${formatTransactionDate(record.date)}. Budgets were recalculated.`,
    )
  }

  function confirmDelete() {
    const record = deleting
    onDelete(record.id)
    setDeleting(null)
    onNotify(
      'Transaction deleted',
      `${record.name} was removed from this demo session. Budgets and dashboard totals were recalculated.`,
    )
  }

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Transactions"
        description="Review confirmed income and expenses, search your history, and add a new demo entry."
      >
        <Button icon="plus" onClick={() => setAdding(true)}>Add transaction</Button>
      </PageHeader>

      <div className="tx-page">
        <TransactionSummary summary={summary} total={rows.length} filtered={filtered} />

        <Card className="tx-history-card" title="Transaction history" description="Confirmed demo activity, newest information first.">
          <TransactionFilters
            filters={filters}
            categories={categories}
            onChange={update}
            onClear={() => setFilters(defaultFilters)}
            dateError={dateError}
          />

          <div className="tx-results-bar">
            <p role="status">Showing <strong>{visible.length}</strong> of {rows.length} transactions{filtered ? ' with filters applied' : ''}.</p>
            {active > 0 && <span>{active} active {active === 1 ? 'filter' : 'filters'}</span>}
          </div>

          <TransactionList
            rows={visible}
            totalCount={rows.length}
            onClearFilters={() => setFilters(defaultFilters)}
            onAdd={() => setAdding(true)}
            onEdit={setEditing}
            onDelete={setDeleting}
          />
        </Card>
      </div>

      {adding && (
        <AddTransactionModal
          categories={categories}
          asOf={workspace.asOf}
          onClose={() => setAdding(false)}
          onSubmit={addTransaction}
        />
      )}
      {editing && (
        <TransactionEditModal
          transaction={editing}
          categories={categories}
          asOf={workspace.asOf}
          onClose={() => setEditing(null)}
          onSubmit={editTransaction}
        />
      )}
      {deleting && (
        <DeleteTransactionModal
          transaction={deleting}
          onClose={() => setDeleting(null)}
          onConfirm={confirmDelete}
        />
      )}
    </>
  )
}