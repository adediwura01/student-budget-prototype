import { useEffect, useMemo, useRef, useState } from 'react'
import AppLayout from './components/AppLayout'
import WorkspacePreferences from './components/WorkspacePreferences'
import Toast from './components/ui/Toast'
import useAppearance from './hooks/useAppearance'
import { createDashboardWorkspace } from './demo/dashboard'
import { addTransaction, deleteTransaction, updateTransaction, workspaceMonths } from './finance/workspace'
import { confirmPlan, removePlan, undoPlanConfirmation, upsertPlan } from './finance/plans'
import { selectDashboard, transactionCsv } from './finance/dashboard'
import { destinationFromHash } from './navigation'
import Dashboard from './pages/Dashboard'
import SectionPage from './pages/SectionPage'
import Transactions from './pages/Transactions'
import Budgets from './pages/Budgets'
import FinancialPlanning from './pages/FinancialPlanning'
import './App.css'

function App() {
  const workspace = useMemo(() => createDashboardWorkspace(), [])
  const [destination, setDestination] = useState(() => destinationFromHash(location.hash))
  const [workspaceName, setWorkspaceName] = useState('My workspace')
  const [dialog, setDialog] = useState(null)
  const [notification, setNotification] = useState(null)
  const [month, setMonth] = useState(() => workspace.asOf.slice(0, 7))
  const toastId = useRef(0)
  const { appearance, setAppearance } = useAppearance()
  const [transactions, setTransactions] = useState(workspace.transactions)
  const [budgets, setBudgets] = useState(workspace.monthlyBudgets)
  const [plans, setPlans] = useState(workspace.plans)
  const activeWorkspace = useMemo(
    () => ({ ...workspace, transactions, monthlyBudgets: budgets, plans }),
    [workspace, transactions, budgets, plans],
  )
  const months = useMemo(() => workspaceMonths(activeWorkspace), [activeWorkspace])
  const dashboard = useMemo(() => selectDashboard(activeWorkspace, month), [activeWorkspace, month])

  useEffect(() => {
    const navigate = () => {
      if (location.hash.startsWith('#/') || !location.hash) setDestination(destinationFromHash(location.hash))
    }
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])

  function notify(title, message, tone = 'success') {
    setNotification({ id: ++toastId.current, title, message, tone })
  }

  function exportCsv() {
    const blob = new Blob([`\uFEFF${transactionCsv(dashboard.transactions)}`], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `finset-${dashboard.month}-transactions.csv`
    document.body.append(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    notify('Export ready', `${dashboard.transactions.length} confirmed transactions from ${dashboard.monthLabel} were downloaded as CSV.`)
  }

  function addTransactionRecord(record) {
    setTransactions((rows) => addTransaction(rows, record))
  }

  function updateTransactionRecord(record) {
    setTransactions((rows) => updateTransaction(rows, { ...record, confirmed: true, deleted: false }))
  }

  function deleteTransactionRecord(id) {
    setTransactions((rows) => deleteTransaction(rows, id))
  }

  function savePlanRecord(record) {
    setPlans((rows) => upsertPlan(rows, record))
  }

  function deletePlanRecord(id) {
    setPlans((rows) => removePlan(rows, id))
  }

  function confirmPlanRecord(planId, amount) {
    const result = confirmPlan({ plans, transactions, planId, amount, asOf: workspace.asOf })
    setPlans(result.plans)
    setTransactions(result.transactions)
    return result
  }

  function undoPlanRecord(planId) {
    const result = undoPlanConfirmation({ plans, transactions, planId })
    setPlans(result.plans)
    setTransactions(result.transactions)
    return result
  }

  return <>
    <AppLayout destination={destination} workspaceName={workspaceName} appearance={appearance}
      notifications={dashboard.notifications} onAppearanceChange={setAppearance}
      onPreferences={() => setDialog('preferences')} onNotify={notify}>
      {destination.id === 'dashboard'
        ? <Dashboard dashboard={dashboard} month={month} months={months} onMonthChange={setMonth} onExport={exportCsv} />
        : destination.id === 'transactions'
          ? <Transactions
              workspace={activeWorkspace}
              onAdd={addTransactionRecord}
              onUpdate={updateTransactionRecord}
              onDelete={deleteTransactionRecord}
              onNotify={notify}
            />
          : destination.id === 'budgets'
            ? <Budgets
                workspace={activeWorkspace}
                month={month}
                months={months}
                onMonthChange={setMonth}
                onBudgetsChange={setBudgets}
                onNotify={notify}
              />
            : destination.id === 'financial-planning'
              ? <FinancialPlanning
                  workspace={activeWorkspace}
                  month={month}
                  months={months}
                  onMonthChange={setMonth}
                  onPlansChange={savePlanRecord}
                  onPlanRemove={deletePlanRecord}
                  onPlanConfirm={confirmPlanRecord}
                  onPlanUndo={undoPlanRecord}
                  onNotify={notify}
                />
              : <SectionPage destination={destination} />}
    </AppLayout>
    {dialog === 'preferences' && <WorkspacePreferences name={workspaceName} appearance={appearance}
      onAppearanceChange={setAppearance} onClose={() => setDialog(null)}
      onSave={(name) => { setWorkspaceName(name); notify('Workspace label updated', 'Your label is applied to this preview session. No account information was changed.') }} />}
    {notification && <Toast key={notification.id} title={notification.title} message={notification.message} tone={notification.tone} onClose={() => setNotification(null)} />}
  </>
}

export default App
