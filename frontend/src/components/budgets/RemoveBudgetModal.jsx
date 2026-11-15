import Modal from '../Modal'
import Icon from '../Icon'
import Button from '../ui/Button'
import { money } from '../../finance/dashboard'

export default function RemoveBudgetModal({ budget, onClose, onConfirm }) {
  return (
    <Modal
      title="Remove budget"
      description="This removes the monthly allocation only. Confirmed transactions are not changed."
      onClose={onClose}
    >
      <div className="budget-remove-summary">
        <span className={`budget-remove-icon tone-${budget.tone}`}><Icon name={budget.icon} size={19} /></span>
        <span className="budget-remove-copy">
          <strong>{budget.name}</strong>
          <small>{money(budget.allocation, true)} allocated · {money(budget.spent, true)} spent</small>
        </span>
      </div>

      <p className="budget-remove-warning">
        <Icon name="alert" size={16} />
        {budget.spent > 0
          ? `${money(budget.spent, true)} of confirmed spending will no longer have a category allocation.`
          : 'No confirmed spending is recorded for this category this month.'}
      </p>

      <div className="modal-actions">
        <Button variant="secondary" onClick={onClose}>Keep budget</Button>
        <Button variant="destructive" onClick={onConfirm}>Remove allocation</Button>
      </div>
    </Modal>
  )
}