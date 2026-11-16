import { useMemo, useState } from 'react'
import PageHeader from '../components/PageHeader'
import Icon from '../components/Icon'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Dropdown from '../components/ui/Dropdown'
import Input from '../components/ui/Input'
import { IncomeExpenses, SpendingTrends } from '../components/reports/ReportCharts'
import SpendingCategories from '../components/reports/SpendingCategories'
import BudgetPerformance from '../components/reports/BudgetPerformance'
import { money } from '../finance/dashboard'
import { formatTransactionDate } from '../finance/transactions'
import { reportRangeOptions, resolveReportRange, selectReports } from '../finance/reports'
import '../reports.css'

const summaryCells = [
  { key: 'income', label: 'Total Income', icon: 'income', tone: 'success', note: 'Confirmed money received' },
  { key: 'expenses', label: 'Total Expenses', icon: 'expense', tone: 'danger', note: 'Confirmed money spent' },
  { key: 'net', label: 'Net Cash Flow', icon: 'wallet', tone: 'brand', note: 'Actual income minus actual expenses' },
]

export default function Reports({ workspace, onExport, onExportPdf }) {
  const [range, setRange] = useState(() => resolveReportRange(workspace.asOf))
  const [preset, setPreset] = useState('this-month')
  const [draft, setDraft] = useState({ from: range.from, to: range.to })
  const [error, setError] = useState('')
  const [exportingPdf, setExportingPdf] = useState(false)
  const report = useMemo(() => selectReports(workspace, range), [workspace, range])

  function choosePeriod(id) {
    setPreset(id)
    setError('')
    if (id === 'custom') {
      setDraft({ from: range.from, to: range.to })
    } else {
      setRange(resolveReportRange(workspace.asOf, id))
    }
  }

  function applyRange(event) {
    event.preventDefault()
    try {
      setRange(resolveReportRange(workspace.asOf, 'custom', draft))
      setError('')
    } catch (invalid) {
      setError(invalid.message)
    }
  }

  async function exportPdf() {
    if (exportingPdf) return
    setExportingPdf(true)
    try {
      await onExportPdf(report)
    } finally {
      setExportingPdf(false)
    }
  }

  return (
    <>
      <PageHeader eyebrow="Workspace" title="Reports" description="Understand your financial activity, spending patterns, and monthly budgets.">
        <div className="report-header-controls">
          <Dropdown className="report-range-picker" label="Reporting period" icon="calendar3" triggerContent={reportRangeOptions.find((option) => option.id === preset).label}
            items={reportRangeOptions.map((option) => ({ ...option, checked: option.id === preset, onSelect: () => choosePeriod(option.id) }))} />
          <Button variant="secondary" icon="download" disabled={report.summary.count === 0} onClick={() => onExport(report)} title="Export confirmed transactions in the applied date range">Export CSV</Button>
          <Button variant="secondary" icon="report" loading={exportingPdf} onClick={exportPdf} title="Export a financial statement for the applied date range, including empty periods">{exportingPdf ? 'Preparing PDF...' : 'Export PDF'}</Button>
        </div>
      </PageHeader>

      <div className="reports-page">
        {preset === 'custom' && (
          <Card className="report-range-card" aria-label="Custom reporting dates">
            <form className="report-range-form" noValidate onSubmit={applyRange}>
              <Input label="Start date" type="date" value={draft.from} max={workspace.asOf} required onChange={(event) => setDraft({ ...draft, from: event.target.value })} aria-describedby={error ? 'report-range-error' : 'report-range-hint'} aria-invalid={error ? true : undefined} />
              <Input label="End date" type="date" value={draft.to} max={workspace.asOf} required onChange={(event) => setDraft({ ...draft, to: event.target.value })} aria-describedby={error ? 'report-range-error' : 'report-range-hint'} aria-invalid={error ? true : undefined} />
              <Button type="submit">Apply range</Button>
            </form>
            <p id="report-range-hint" className="report-range-hint">Both dates are included. Apply your dates to update the report; invalid dates do not replace the current report.</p>
            {error && <p id="report-range-error" className="report-range-error" role="alert">{error}</p>}
          </Card>
        )}

        <div className="report-context"><p role="status"><strong>{report.range.label}</strong><span>{report.summary.count} confirmed {report.summary.count === 1 ? 'transaction' : 'transactions'}</span></p><p>NGN demo data as of {formatTransactionDate(workspace.asOf)}</p></div>

        <div className="report-overview" role="group" aria-label="Financial overview">
          {summaryCells.map((cell) => {
            const value = report.summary[cell.key]
            return <Card key={cell.key} className={`report-summary-card report-summary-card--${cell.tone}`} aria-label={cell.label}>
              <h2 className="report-summary-label"><span className="report-summary-icon"><Icon name={cell.icon} size={17} /></span>{cell.label}</h2>
              <strong className={`report-summary-value ${value < 0 ? 'is-negative' : ''}`}>{cell.key === 'net' && value > 0 ? '+' : ''}{money(value, true)}</strong>
              <p className="report-summary-note">{cell.key === 'net' && value < 0 ? 'Expenses exceed income in this range' : cell.note}</p>
            </Card>
          })}
        </div>

        <div className="report-chart-row"><IncomeExpenses report={report} /><SpendingCategories key={`${range.from}-${range.to}`} report={report} /></div>
        <SpendingTrends report={report} />
        <BudgetPerformance key={`${range.from}-${range.to}`} report={report} />
        <p className="report-footnote">Reports use confirmed transactions only. Expected income and planned expenses are excluded. CSV and PDF exports contain all actual transactions in the applied range.</p>
      </div>
    </>
  )
}
