import Icon from '../Icon'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import EmptyState from '../ui/EmptyState'
import { money } from '../../finance/dashboard'
import { findPlanTransaction } from '../../finance/plans'

export default function PlanList({ rows, totalCount, monthLabel, transactions, onClearFilters, onCreate, onEdit, onConfirm, onUndo, onDelete }) {
  if (totalCount === 0) {
    return (
      <EmptyState
        icon="planning"
        title={`No plans for ${monthLabel}`}
        description="Plan expected income and upcoming expenses. Nothing is counted until you confirm it."
      >
        <Button icon="plus" onClick={onCreate}>New plan</Button>
      </EmptyState>
    )
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        icon="search"
        title="No matching plans"
        description="No plans match the current search and filters. Try a different type, status or category."
      >
        <Button variant="secondary" icon="refresh" onClick={onClearFilters}>Clear filters</Button>
      </EmptyState>
    )
  }

  return (
    <>
      <div className="plan-table-head" aria-hidden="true">
        <span>Plan</span>
        <span>Category</span>
        <span>Expected date</span>
        <span>Status</span>
        <span className="plan-align-end">Amount</span>
        <span className="sr-only">Actions</span>
      </div>
      <ul className="plan-rows" aria-label="Financial plans">
        {rows.map((plan) => {
          const linked = findPlanTransaction(transactions, plan)
          const undoable = plan.status === 'confirmed' && Boolean(linked)
          const actual = plan.actualAmount ?? plan.amount
          const differs = plan.status === 'confirmed' && actual !== plan.amount

          return (
            <li key={plan.id} className={`plan-list-row tone-${plan.tone}`}>
              <span className="plan-list-main">
                <span className="plan-list-icon"><Icon name={plan.icon} size={17} /></span>
                <span className="plan-list-copy">
                  <strong>{plan.name}</strong>
                  <small className="plan-list-meta">
                    <Badge tone={plan.type === 'income' ? 'success' : 'neutral'} dot>{plan.typeLabel}</Badge>
                    {plan.note && <span>{plan.note}</span>}
                  </small>
                </span>
              </span>

              <span className="plan-category">{plan.categoryName}</span>

              <span className="plan-expected-date">
                <span className="plan-expected-label">Expected</span>
                {plan.dateLabel}
              </span>

              <span className="plan-status-cell">
                {plan.status === 'confirmed'
                  ? <Badge tone="success" dot>Confirmed</Badge>
                  : plan.needsAttention
                    ? <Badge tone="warning" dot>Due now</Badge>
                    : <Badge tone="neutral">Pending</Badge>}
                {differs && <small>Actual {plan.type === 'income' ? 'received' : 'paid'} {money(actual, true)}</small>}
                {plan.status === 'confirmed' && !linked && <small>Undo unavailable</small>}
              </span>

              <span className={`plan-list-amount ${plan.type === 'income' ? 'is-income' : 'is-expense'}`}>
                {plan.type === 'income' ? '+' : '−'}{money(plan.amount, true)}
              </span>

              <span className="plan-actions">
                {plan.status === 'pending' ? (
                  <>
                    <Button variant="tertiary" onClick={() => onConfirm(plan)} aria-label={`Confirm ${plan.name} plan`}>Confirm</Button>
                    <Button variant="tertiary" onClick={() => onEdit(plan)} aria-label={`Edit ${plan.name} plan`}>Edit</Button>
                    <Button variant="tertiary" className="plan-delete-action" onClick={() => onDelete(plan)} aria-label={`Delete ${plan.name} plan`}>Delete</Button>
                  </>
                ) : (
                  <Button
                    variant="tertiary"
                    onClick={() => onUndo(plan)}
                    disabled={!undoable}
                    title={undoable ? 'Reverse the confirmed transaction' : 'The linked transaction can no longer be identified'}
                    aria-label={`Undo confirmation for ${plan.name}`}
                  >
                    Undo
                  </Button>
                )}
              </span>
            </li>
          )
        })}
      </ul>
    </>
  )
}