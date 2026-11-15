import PageHeader from '../components/PageHeader'
import Button from '../components/ui/Button'
import MonthPicker from '../components/dashboard/MonthPicker'
import SummaryCards from '../components/dashboard/SummaryCards'
import BudgetCard from '../components/dashboard/BudgetCard'
import CashFlowChart from '../components/dashboard/CashFlowChart'
import CategoryProgress from '../components/dashboard/CategoryProgress'
import UpcomingPlans from '../components/dashboard/UpcomingPlans'
import WeekSummary from '../components/dashboard/WeekSummary'
import RecentTransactions from '../components/dashboard/RecentTransactions'
import '../dashboard.css'

export default function Dashboard({ dashboard, month, months, onMonthChange, onExport }) {
  const firstName = dashboard.profile.name.split(' ')[0]

  return <>
    <PageHeader
      eyebrow="Dashboard"
      title={`Welcome back, ${firstName}.`}
      description={`Your money for ${dashboard.monthLabel}, confirmed up to ${dashboard.asOfLabel}.`}
    >
      <MonthPicker months={months ?? dashboard.months} value={month} onChange={onMonthChange} />
      <Button variant="secondary" icon="download" onClick={onExport}>Export CSV</Button>
    </PageHeader>
    <div className="dash-grid">
      <SummaryCards dashboard={dashboard} />
      <div className="dash-row">
        <CashFlowChart chart={dashboard.chart} />
        <BudgetCard dashboard={dashboard} />
      </div>
      <div className="dash-row">
        <CategoryProgress dashboard={dashboard} />
        <UpcomingPlans dashboard={dashboard} />
      </div>
      <WeekSummary dashboard={dashboard} weekStart={dashboard.week.weekStart} />
      <RecentTransactions dashboard={dashboard} />
    </div>
  </>
}