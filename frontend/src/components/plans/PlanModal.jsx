import { useState } from 'react'
import Modal from '../Modal'
import Icon from '../Icon'
import Button from '../ui/Button'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Textarea from '../ui/Textarea'
import { categoriesForType } from '../../finance/transactions'
import { createPlanDraft, planDraftFrom, validatePlan } from '../../finance/plans'

const fieldOrder = ['type', 'description', 'amount', 'category', 'date', 'note']

export default function PlanModal({ mode = 'create', plan, categories, asOf, onClose, onSubmit }) {
  const editing = mode === 'edit' && plan
  const [draft, setDraft] = useState(() => (editing ? planDraftFrom(plan) : createPlanDraft('expense', categories, asOf)))
  const [attempted, setAttempted] = useState(false)

  const result = validatePlan(draft, { categories })
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
      if (first) document.getElementById(`plan-${first}`)?.focus()
      return
    }
    onSubmit(result.value)
  }

  return (
    <Modal
      title={editing ? 'Edit plan' : 'New plan'}
      description={editing
        ? 'Update this planned entry. Confirming it later creates the actual transaction.'
        : 'Plan expected income or an upcoming expense. Plans stay separate from confirmed money.'}
      onClose={onClose}
    >
      <form className="plan-form" onSubmit={submit} noValidate>
        {attempted && !result.valid && (
          <p className="plan-form-alert" role="alert">
            <Icon name="alert" size={16} />
            Check the highlighted fields and try again.
          </p>
        )}

        <div className="plan-form-grid">
          <fieldset className="plan-form-span plan-type-field">
            <legend className="ui-field-label">Plan type<span className="ui-field-required" aria-hidden="true">*</span></legend>
            <div className="plan-type-choices">
              {['income', 'expense'].map((type) => (
                <label key={type} className={`plan-type-choice ${draft.type === type ? 'is-selected' : ''}`}>
                  <input
                    type="radio"
                    name="plan-type"
                    id={type === 'expense' ? 'plan-type' : undefined}
                    value={type}
                    checked={draft.type === type}
                    onChange={() => changeType(type)}
                  />
                  <Icon name={type === 'income' ? 'income' : 'expense'} size={16} />
                  {type === 'income' ? 'Expected income' : 'Planned expense'}
                </label>
              ))}
            </div>
            {errors.type && <p className="ui-field-error" role="alert">{errors.type}</p>}
          </fieldset>

          <div className="plan-form-span">
            <Input
              id="plan-description"
              label="Description"
              value={draft.description}
              placeholder="e.g. Course materials"
              maxLength={80}
              required
              autoFocus
              error={errors.description}
              onChange={(event) => update('description', event.target.value)}
            />
          </div>

          <Input
            id="plan-amount"
            label="Expected amount (NGN)"
            className="plan-amount-field"
            value={draft.amount}
            placeholder="0.00"
            inputMode="decimal"
            autoComplete="off"
            required
            hint="Up to two decimal places. This is the planned amount."
            error={errors.amount}
            onChange={(event) => update('amount', event.target.value)}
          />

          <Select
            id="plan-category"
            label="Category"
            value={draft.category}
            required
            error={errors.category}
            onChange={(event) => update('category', event.target.value)}
          >
            <option value="">Choose a category</option>
            {allowed.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </Select>

          <div className="plan-form-span">
            <Input
              id="plan-date"
              label="Expected date"
              type="date"
              value={draft.date}
              required
              hint="Plans may be dated in the future. Nothing is counted until you confirm."
              error={errors.date}
              onChange={(event) => update('date', event.target.value)}
            />
          </div>

          <div className="plan-form-span">
            <Textarea
              id="plan-note"
              label="Note (optional)"
              value={draft.note}
              placeholder="Add context for this plan"
              maxLength={160}
              hint="Up to 160 characters. Notes are only used in this demo."
              error={errors.note}
              onChange={(event) => update('note', event.target.value)}
            />
          </div>
        </div>

        <div className="modal-actions plan-form-actions">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" icon="check">{editing ? 'Save changes' : 'Create plan'}</Button>
        </div>
      </form>
    </Modal>
  )
}