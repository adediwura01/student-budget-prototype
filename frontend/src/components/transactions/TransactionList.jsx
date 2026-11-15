import Icon from '../Icon'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import EmptyState from '../ui/EmptyState'
import { money } from '../../finance/dashboard'

export default function TransactionList({ rows, totalCount, onClearFilters, onAdd, onEdit, onDelete }) {
  if (totalCount === 0) {
    return (
      <EmptyState
        icon="transactions"
        title="No transactions yet"
        description="Add the first confirmed income or expense to start this demo history."
      >
        <Button icon="plus" onClick={onAdd}>Add transaction</Button>
      </EmptyState>
    )
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        icon="search"
        title="No matching transactions"
        description="No transactions match the current search and filters. Try a wider date range or a different category."
      >
        <Button variant="secondary" icon="refresh" onClick={onClearFilters}>Clear filters</Button>
      </EmptyState>
    )
  }

  return (
    <>
      <div className="tx-table-head" aria-hidden="true">
        <span>Description</span>
        <span>Category</span>
        <span>Date</span>
        <span>Type</span>
        <span>Amount</span>
        <span className="tx-align-end">Actions</span>
      </div>
      <ul className="tx-rows" aria-label="Transaction history">
        {rows.map((row) => (
          <li key={row.id} className="tx-history-row">
            <span className="tx-history-main">
              <span className={`tx-history-icon tone-${row.tone}`}><Icon name={row.icon} size={17} /></span>
              <span className="tx-history-copy">
                <strong>{row.name}</strong>
                {row.note && <small>{row.note}</small>}
              </span>
            </span>
            <span className="tx-category">{row.categoryName}</span>
            <span className="tx-date">{row.dateLabel}</span>
            <span className="tx-type-cell"><Badge tone={row.type === 'income' ? 'success' : 'neutral'} dot>{row.typeLabel}</Badge></span>
            <span className={`tx-history-amount ${row.type === 'income' ? 'tx-income' : 'tx-expense'}`}>
              {row.type === 'income' ? '+' : '−'}{money(row.amount, true)}
            </span>
            <span className="tx-actions">
              <Button variant="tertiary" onClick={() => onEdit(row)} aria-label={`Edit ${row.name}`}>Edit</Button>
              <Button variant="tertiary" className="tx-delete-action" onClick={() => onDelete(row)} aria-label={`Delete ${row.name}`}>Delete</Button>
            </span>
          </li>
        ))}
      </ul>
    </>
  )
}