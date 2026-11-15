import { useMemo, useState } from 'react'
import PageHeader from '../components/PageHeader'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import MonthPicker from '../components/dashboard/MonthPicker'
import PlanOverview from '../components/plans/PlanOverview'
import PlanFilters from '../components/plans/PlanFilters'
import PlanList from '../components/plans/PlanList'
import PlanModal from '../components/plans/PlanModal'
import ConfirmPlanModal from '../components/plans/ConfirmPlanModal'
import RemovePlanModal from '../components/plans/RemovePlanModal'
import { money } from '../finance/dashboard'
import { formatTransactionDate } from '../finance/transactions'
import {
  activePlanFilterCount,
  createPlanRecord,
  filterPlans,
  hasActivePlanFilters,
  planFiltersEmpty,
  selectPlans,
  sortPlans,
} from '../finance/plans'
import '../plans.css'

export default function FinancialPlanning({ workspace, month, months, onMonthChange, onPlansChange, onPlanRemove, onPlanConfirm, onPlanUndo, onNotify }) {
  const plan = useMemo(() => selectPlans(workspace, month), [workspace, month])
  const [filters, setFilters] = useState(planFiltersEmpty)
  const [editor, setEditor] = useState(null)
  const [confirming, setConfirming] = useState(null)
  const [removing, setRemoving] = useState(null)

  const visible = useMemo(() => sortPlans(filterPlans(plan.items, filters), filters.sort), [plan.items, filters])
  const filtered = hasActivePlanFilters(filters)
  const active = activePlanFilterCount(filters)

  function update(key, value) {
    setFilters((previous) => ({ ...previous, [key]: value }))
  }

  function save(value) {
    const editing = editor?.mode === 'edit'
    const source = editing ? workspace.plans.find((row) => row.id === editor.plan.id) : null
    const record = source ? { ...source, ...value } : createPlanRecord(value)
    onPlansChange(record)
    setEditor(null)
    onNotify(
      editing ? 'Plan updated' : 'Plan created',
      `${value.name} · ${value.type === 'income' ? 'Expected income' : 'Planned expense'} ${money(value.amount, true)} expected ${formatTransactionDate(value.date)}. Nothing has been confirmed yet.`,
    )
  }

  function confirm(selected, amount) {
    try {
      const result = onPlanConfirm(selected.id, amount)
      setConfirming(null)
      const type = selected.type === 'income' ? 'received' : 'paid'
      onNotify(
        'Plan confirmed',
        `${selected.name} · ${money(amount, true)} ${type} recorded as an actual transaction dated ${formatTransactionDate(result.transaction.date)}. Budgets and Dashboard were updated.`,
      )
    } catch (error) {
      onNotify('Plan not confirmed', error.message, 'danger')
    }
  }

  function undo(selected) {
    try {
      onPlanUndo(selected.id)
      onNotify(
        'Confirmation undone',
        `${selected.name} is pending again. The linked transaction was reversed, so budgets and Dashboard were recalculated.`,
      )
    } catch (error) {
      onNotify('Undo unavailable', error.message, 'danger')
    }
  }

  function remove(selected) {
    onPlanRemove(selected.id)
    setRemoving(null)
    onNotify('Plan deleted', `${selected.name} was removed from this demo session. No money had moved for this plan.`)
  }

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Financial Planning"
        description="Plan expected income and upcoming expenses. Only confirming a plan moves real money."
      >
        <MonthPicker months={months ?? plan.months} value={month} onChange={onMonthChange} />
        <Button icon="plus" onClick={() => setEditor({ mode: 'create' })}>New plan</Button>
      </PageHeader>

      <div className="plans-page">
        <PlanOverview plan={plan} />

        <Card
          className="plan-list-card"
          title="Plans"
          description={`${plan.monthLabel} expected income and planned expenses.`}
          actions={<Badge tone="neutral">{plan.items.length} {plan.items.length === 1 ? 'plan' : 'plans'}</Badge>}
        >
          <PlanFilters
            filters={filters}
            categories={plan.categories}
            onChange={update}
            onClear={() => setFilters(planFiltersEmpty)}
          />

          <div className="plan-results-bar">
            <p role="status">Showing <strong>{visible.length}</strong> of {plan.items.length} plans{filtered ? ' with filters applied' : ''}.</p>
            {active > 0 && <span>{active} active {active === 1 ? 'filter' : 'filters'}</span>}
          </div>

          <PlanList
            rows={visible}
            totalCount={plan.items.length}
            monthLabel={plan.monthLabel}
            transactions={workspace.transactions}
            onClearFilters={() => setFilters(planFiltersEmpty)}
            onCreate={() => setEditor({ mode: 'create' })}
            onEdit={(selected) => setEditor({ mode: 'edit', plan: selected })}
            onConfirm={setConfirming}
            onUndo={undo}
            onDelete={setRemoving}
          />
        </Card>
      </div>

      {editor && (
        <PlanModal
          key={`${editor.mode}-${editor.plan?.id ?? 'new'}-${month}`}
          mode={editor.mode}
          plan={editor.plan}
          categories={plan.categories}
          asOf={workspace.asOf}
          onClose={() => setEditor(null)}
          onSubmit={save}
        />
      )}

      {confirming && (
        <ConfirmPlanModal
          plan={confirming}
          asOf={workspace.asOf}
          onClose={() => setConfirming(null)}
          onConfirm={(amount) => confirm(confirming, amount)}
        />
      )}

      {removing && (
        <RemovePlanModal
          plan={removing}
          onClose={() => setRemoving(null)}
          onConfirm={() => remove(removing)}
        />
      )}
    </>
  )
}