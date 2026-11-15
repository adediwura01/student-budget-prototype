import { useState } from 'react'
import Modal from '../Modal'
import Icon from '../Icon'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import Input from '../ui/Input'
import { money, shortDate } from '../../finance/dashboard'
import { parseAmountKobo } from '../../finance/transactions'

export default function ConfirmPlanModal({ plan, asOf, onClose, onConfirm }) {
  const [amount, setAmount] = useState(((plan.actualAmount ?? plan.amount) / 100).toFixed(2))
  const [attempted, setAttempted] = useState(false)

  const parsed = parseAmountKobo(amount)
  const error = attempted && !parsed.ok ? parsed.error : ''
  const difference = parsed.ok ? parsed.kobo - plan.amount : null
  const typeLabel = plan.type === 'income' ? 'Expected income' : 'Planned expense'
  const verb = plan.type === 'income' ? 'received' : 'paid'

  function submit(event) {
    event.preventDefault()
    setAttempted(true)
    if (!parsed.ok) {
      document.getElementById('plan-actual-amount')?.focus()
      return
    }
    onConfirm(parsed.kobo)
  }

  return (
    <Modal
      title="Confirm plan"
      description="Record what actually happened. The actual amount can differ from the plan."
      onClose={onClose}
    >
      <form className="plan-form" onSubmit={submit} noValidate>
        <div className="plan-confirm-summary">
          <span className={`plan-confirm-icon tone-${plan.tone}`}><Icon name={plan.icon} size={19} /></span>
          <span className="plan-confirm-copy">
            <strong>{plan.name}</strong>
            <small>{typeLabel} · {plan.categoryName} · expected {shortDate(plan.date)}</small>
            <small>Planned {money(plan.amount, true)}</small>
          </span>
          <Badge tone={plan.type === 'income' ? 'success' : 'neutral'} dot>{plan.type === 'income' ? 'Income' : 'Expense'}</Badge>
        </div>

        <Input
          id="plan-actual-amount"
          label={`Actual amount ${verb} (NGN)`}
          value={amount}
          placeholder="0.00"
          inputMode="decimal"
          autoComplete="off"
          required
          autoFocus
          hint="Up to two decimal places. Enter what you actually received or paid."
          error={error}
          onChange={(event) => setAmount(event.target.value)}
        />

        <p className="plan-confirm-difference" role="status">
          <Icon name={difference === null ? 'info' : difference === 0 ? 'check' : 'alert'} size={15} />
          <span>
            {difference === null
              ? 'Enter an amount to compare it with the plan.'
              : difference === 0
                ? 'This matches the planned amount.'
                : `${money(Math.abs(difference), true)} ${difference > 0 ? 'more' : 'less'} than planned.`}
          </span>
        </p>

        <p className="plan-confirm-warning">
          <Icon name="alert" size={16} />
          Confirming creates a confirmed {plan.type === 'income' ? 'income' : 'expense'} transaction dated {shortDate(asOf)}. It will appear on the Dashboard, in Transactions and in Budgets.
        </p>

        <div className="modal-actions">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" icon="check">Confirm plan</Button>
        </div>
      </form>
    </Modal>
  )
}