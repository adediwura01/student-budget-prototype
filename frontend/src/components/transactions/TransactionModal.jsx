import { useState } from 'react'
import Modal from '../Modal'
import Icon from '../Icon'
import Button from '../ui/Button'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Textarea from '../ui/Textarea'
import { categoriesForType, createTransactionDraft, formatTransactionDate, validateTransaction } from '../../finance/transactions'
import { money } from '../../finance/dashboard'

const fieldOrder = ['type', 'description', 'amount', 'category', 'date', 'note']

function draftFromTransaction(transaction) {
  return {
    type: transaction.type,
    description: transaction.name,
    amount: (transaction.amount / 100).toFixed(2),
    category: transaction.category,
    date: transaction.date,
    note: transaction.note ?? '',
  }
}

export default function TransactionModal({ transaction, categories, asOf, onClose, onSubmit, mode = 'create' }) {
  const editing = mode === 'edit' && transaction
  const [draft, setDraft] = useState(() => editing ? draftFromTransaction(transaction) : createTransactionDraft('expense', categories, asOf))
  const [attempted, setAttempted] = useState(false)

  const result = validateTransaction(draft, { categories, asOf })
  const errors = attempted ? result.errors : {}
  const allowed = categoriesForType(categories, draft.type)

  function update(key, value) {
    setDraft((previous) => ({ ...previous, [key]: value }))
  }

  function changeType(type) {
    setDraft((previous) => {
      const options = categoriesForType(categories, type)
      const keep = options.some((category) => category.id === previous.category)
      return { ...previous, type, category: keep ? previous.category : options[0]?.id ?? '' }
    })
  }

  function submit(event) {
    event.preventDefault()
    setAttempted(true)
    if (!result.valid) {
      const first = fieldOrder.find((field) => result.errors[field])
      if (first) document.getElementById(`tx-${first}`)?.focus()
      return
    }
    onSubmit(result.value)
  }

  return (
    <Modal
      title={editing ? 'Edit transaction' : 'Add transaction'}
      description={editing
        ? 'Update this confirmed demo entry. Changes recalculate budgets immediately.'
        : 'Record confirmed income or expense in this demo. Entries stay in this browser session only.'}
      onClose={onClose}
    >
      <form className="tx-form" onSubmit={submit} noValidate>
        {attempted && !result.valid && (
          <p className="tx-form-alert" role="alert">
            <Icon name="alert" size={16} />
            Check the highlighted fields and try again.
          </p>
        )}

        <div className="tx-form-grid">
          <fieldset className="tx-form-span tx-type-field">
            <legend className="ui-field-label">Type<span className="ui-field-required" aria-hidden="true">*</span></legend>
            <div className="tx-type-choices">
              {['expense', 'income'].map((type) => (
                <label key={type} className={`tx-type-choice ${draft.type === type ? 'is-selected' : ''}`}>
                  <input
                    type="radio"
                    name="tx-type"
                    id={type === 'expense' ? 'tx-type' : undefined}
                    value={type}
                    checked={draft.type === type}
                    onChange={() => changeType(type)}
                  />
                  <Icon name={type === 'income' ? 'income' : 'expense'} size={16} />
                  {type === 'income' ? 'Income' : 'Expense'}
                </label>
              ))}
            </div>
            {errors.type && <p className="ui-field-error" role="alert">{errors.type}</p>}
          </fieldset>

          <div className="tx-form-span">
            <Input
              id="tx-description"
              label="Description"
              value={draft.description}
              placeholder="e.g. Weekly groceries"
              maxLength={80}
              required
              autoFocus
              error={errors.description}
              onChange={(event) => update('description', event.target.value)}
            />
          </div>

          <Input
            id="tx-amount"
            label="Amount (NGN)"
            className="tx-amount-field"
            value={draft.amount}
            placeholder="0.00"
            inputMode="decimal"
            autoComplete="off"
            required
            hint="Nigerian naira. Up to two decimal places."
            error={errors.amount}
            onChange={(event) => update('amount', event.target.value)}
          />

          <Select
            id="tx-category"
            label="Category"
            value={draft.category}
            required
            error={errors.category}
            onChange={(event) => update('category', event.target.value)}
          >
            <option value="">Choose a category</option>
            {allowed.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </Select>

          <Input
            id="tx-date"
            label="Date"
            type="date"
            value={draft.date}
            max={asOf}
            required
            hint={`Demo clock: ${formatTransactionDate(asOf)}. Future dates are not counted.`}
            error={errors.date}
            onChange={(event) => update('date', event.target.value)}
          />

          <Textarea
            id="tx-note"
            label="Note (optional)"
            value={draft.note}
            placeholder="Add context for this transaction"
            maxLength={160}
            hint="Up to 160 characters. Notes are only used in this demo."
            error={errors.note}
            onChange={(event) => update('note', event.target.value)}
          />
        </div>

        <div className="modal-actions tx-form-actions">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" icon="check">{editing ? 'Save changes' : `Add ${draft.type === 'income' ? 'income' : 'expense'}`}</Button>
        </div>
      </form>
    </Modal>
  )
}

export function DeleteTransactionModal({ transaction, onClose, onConfirm }) {
  return (
    <Modal
      title="Delete transaction"
      description="This removes the confirmed demo entry and recalculates affected budgets."
      onClose={onClose}
    >
      <div className="tx-delete-summary">
        <span className={`tx-delete-icon tone-${transaction.tone}`}><Icon name={transaction.icon} size={19} /></span>
        <span className="tx-delete-copy">
          <strong>{transaction.name}</strong>
          <small>{formatTransactionDate(transaction.date)} · {transaction.type === 'income' ? 'Income' : 'Expense'} {transaction.categoryName}</small>
          <small>{transaction.type === 'income' ? '+' : '−'}{money(transaction.amount, true)}</small>
        </span>
      </div>
      <p className="tx-delete-warning">
        <Icon name="alert" size={16} />
        This cannot be undone in the current demo session.
      </p>
      <div className="modal-actions">
        <Button variant="secondary" onClick={onClose}>Keep transaction</Button>
        <Button variant="destructive" onClick={onConfirm}>Delete transaction</Button>
      </div>
    </Modal>
  )
}

export function TransactionEditModal({ transaction, categories, asOf, onClose, onSubmit }) {
  return (
    <TransactionModal
      mode="edit"
      transaction={transaction}
      categories={categories}
      asOf={asOf}
      onClose={onClose}
      onSubmit={onSubmit}
    />
  )
}