import { useMemo, useState } from 'react'
import PageHeader from '../components/PageHeader'
import Button from '../components/ui/Button'
import MonthPicker from '../components/dashboard/MonthPicker'
import BudgetOverview from '../components/budgets/BudgetOverview'
import BudgetCategories from '../components/budgets/BudgetCategories'
import BudgetInsights from '../components/budgets/BudgetInsights'
import BudgetModal from '../components/budgets/BudgetModal'
import RemoveBudgetModal from '../components/budgets/RemoveBudgetModal'
import { money, monthName } from '../finance/dashboard'
import { availableBudgetCategories, availableMonths, removeBudget, selectBudgets, upsertBudget } from '../finance/budgets'
import '../budgets.css'

export default function Budgets({ workspace, month, months, onMonthChange, onBudgetsChange, onNotify }) {
  const availableMonthList = useMemo(() => availableMonths(workspace), [workspace])
  const monthOptions = months ?? availableMonthList
  const [editor, setEditor] = useState(null)
  const [removing, setRemoving] = useState(null)

  const budget = useMemo(() => selectBudgets(workspace, month), [workspace, month])
  const available = useMemo(
    () => availableBudgetCategories(workspace.categories, workspace.monthlyBudgets, month),
    [workspace.categories, workspace.monthlyBudgets, month],
  )

  function save(record) {
    const name = workspace.categories.find((category) => category.id === record.category)?.name ?? 'Category'
    const editing = editor?.mode === 'edit'
    onBudgetsChange(upsertBudget(workspace.monthlyBudgets, record))
    setEditor(null)
    onNotify(
      editing ? 'Budget updated' : 'Budget created',
      `${name} · ${monthName(record.month)} allocation set to ${money(record.allocation, true)}. Demo only — nothing was saved to a server.`,
    )
  }

  function confirmRemove() {
    const name = removing.name
    onBudgetsChange(removeBudget(workspace.monthlyBudgets, removing.budgetId))
    setRemoving(null)
    onNotify('Budget removed', `${name} allocation for ${monthName(month)} was removed. Confirmed transactions were not changed.`)
  }

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Budgets"
        description="Plan monthly allocations and follow confirmed spending by category."
      >
        <MonthPicker months={monthOptions} value={month} onChange={onMonthChange} />
        <Button icon="plus" onClick={() => setEditor({ mode: 'create' })}>New budget</Button>
      </PageHeader>

      <div className="budgets-page">
        <div className="budget-overview-row">
          <BudgetOverview budget={budget} />
          <BudgetInsights budget={budget} />
        </div>

        <BudgetCategories
          budget={budget}
          onCreate={() => setEditor({ mode: 'create' })}
          onEdit={(category) => setEditor({ mode: 'edit', budget: category })}
          onRemove={setRemoving}
        />
      </div>

      {editor && (
        <BudgetModal
          key={`${editor.mode}-${editor.budget?.budgetId ?? 'new'}-${month}`}
          mode={editor.mode}
          budget={editor.budget}
          month={month}
          categories={workspace.categories}
          budgets={workspace.monthlyBudgets}
          available={available}
          onClose={() => setEditor(null)}
          onSave={save}
        />
      )}

      {removing && (
        <RemoveBudgetModal
          budget={removing}
          onClose={() => setRemoving(null)}
          onConfirm={confirmRemove}
        />
      )}
    </>
  )
}