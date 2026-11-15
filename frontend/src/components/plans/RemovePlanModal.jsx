import Modal from '../Modal'
import Icon from '../Icon'
import Button from '../ui/Button'
import { money } from '../../finance/dashboard'

export default function RemovePlanModal({ plan, onClose, onConfirm }) {
  return (
    <Modal
      title="Delete plan"
      description="This removes the planned entry only. Confirmed transactions are never changed."
      onClose={onClose}
    >
      <div className="plan-delete-summary">
        <span className={`plan-delete-icon tone-${plan.tone}`}><Icon name={plan.icon} size={19} /></span>
        <span className="plan-delete-copy">
          <strong>{plan.name}</strong>
          <small>{plan.type === 'income' ? 'Expected income' : 'Planned expense'} · {money(plan.amount, true)}</small>
          <small>Expected {plan.dateLabel} · {plan.categoryName}</small>
        </span>
      </div>

      <p className="plan-delete-warning">
        <Icon name="alert" size={16} />
        This cannot be undone in the current demo session. No money has moved for this plan.
      </p>

      <div className="modal-actions">
        <Button variant="secondary" onClick={onClose}>Keep plan</Button>
        <Button variant="destructive" onClick={onConfirm}>Delete plan</Button>
      </div>
    </Modal>
  )
}