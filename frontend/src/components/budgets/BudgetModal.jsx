import { useState } from 'react'
import Modal from '../Modal'
import Icon from '../Icon'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import EmptyState from '../ui/EmptyState'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Textarea from '../ui/Textarea'
import { monthName } from '../../finance/dashboard'
import {
  createBudgetDraft,
  formatAllocationInput,
  validateBudget,
} from '../../finance/budgets'

const fieldOrder = ['category', 'amount', 'note']

export default function BudgetModal({ mode, budget, month, categories, budgets, available, onClose, onSave }) {
  const editing = mode === 'edit' && budget
  const [draft, setDraft] = useState(() => editing
    ? { category: budget.category, amount: formatAllocationInput(budget.allocation), note: budget.note ?? '' }
    : createBudgetDraft(categories, budgets, month))
  const [attempted, setAttempted] = useState(false)

  const availableCategories = available ?? []
  const editingCategory = editing ? categories.find((item) => item.id === budget.category) : null
  const unavailableCategories = categories.filter((category) => !availableCategories.some((item) => item.id === category.id))
  const result = validateBudget(draft, { categories, month, budgets, editingId: editing?.budgetId ?? null })
  const errors = attempted ? result.errors : {}

  function update(key, value) {
    setDraft((previous) => ({ ...previous, [key]: value }))
  }

  function submit(event) {
    event.preventDefault()
    setAttempted(true)
    if (!result.valid) {
      const first = fieldOrder.find((field) => result.errors[field])
      if (first) document.getElementById(`budget-${first}`)?.focus()
      return
    }
    onSave(result.value)
  }

  if (!editing && availableCategories.length === 0) {
    return (
      <Modal
        title="New budget"
        description={`${monthName(month)} allocation. Every category already has an allocation for this month.`}
        onClose={onClose}
      >
        <EmptyState
          icon="budget"
          title="All categories allocated"
          description={`Edit an existing allocation or remove one before creating another for ${monthName(month)}.`}
        >
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </EmptyState>
      </Modal>
    )
  }

  return (
    <Modal
      title={editing ? 'Edit budget' : 'New budget'}
      description={`${monthName(month)} allocation. Only confirmed expenses count toward spending.`}
      onClose={onClose}
    >
      <form className="budget-form" onSubmit={submit} noValidate>
        {attempted && !result.valid && (
          <p className="budget-form-alert" role="alert">
            <Icon name="alert" size={16} />
            Check the highlighted fields and try again.
          </p>
        )}

        <div className="budget-month-context">
          <span className="budget-month-copy">
            <span className="budget-month-icon"><Icon name="calendar3" size={17} /></span>
            <span>
              <small>Allocation month</small>
              <strong>{monthName(month)}</strong>
            </span>
          </span>
          <Badge tone="brand">Monthly</Badge>
        </div>

        {editing ? (
          <div className="ui-field">
            <span className="ui-field-label">Category</span>
            <span className={`budget-static-value tone-${editingCategory?.tone ?? 'purple'}`}>
              <span className="budget-static-icon"><Icon name={editingCategory?.icon ?? 'budget'} size={17} /></span>
              {editingCategory?.name ?? 'Category'}
            </span>
            <p className="ui-field-hint">Category cannot be changed after creation.</p>
          </div>
        ) : (
          <Select
            id="budget-category"
            label="Category"
            value={draft.category}
            required
            autoFocus
            error={errors.category}
            onChange={(event) => update('category', event.target.value)}
          >
            <option value="">Choose a category</option>
            {availableCategories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </Select>
        )}

        {!editing && (
          <p className="budget-category-note" role="note">
            <Icon name="info" size={15} />
            <span>
              Only expense categories without an allocation for {monthName(month)} are available.
              {availableCategories.length > 0
                ? ` Available now: ${availableCategories.map((category) => category.name).join(', ')}.`
                : ' Every expense category already has an allocation for this month.'}
              {unavailableCategories.length > 0 && ` Already allocated: ${unavailableCategories.map((category) => category.name).join(', ')}.`}
            </span>
          </p>
        )}

        <Input
          id="budget-amount"
          label="Monthly allocation (NGN)"
          value={draft.amount}
          placeholder="0.00"
          inputMode="decimal"
          autoComplete="off"
          required
          autoFocus={Boolean(editing)}
          hint="Up to two decimal places. This is the monthly amount."
          error={errors.amount}
          onChange={(event) => update('amount', event.target.value)}
        />

        <Textarea
          id="budget-note"
          label="Note (optional)"
          value={draft.note}
          placeholder="Add context for this allocation"
          maxLength={160}
          hint="Up to 160 characters. Notes are only used in this demo."
          error={errors.note}
          onChange={(event) => update('note', event.target.value)}
        />

        <div className="modal-actions budget-form-actions">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" icon="check">{editing ? 'Save changes' : 'Create budget'}</Button>
        </div>
      </form>
    </Modal>
  )
}