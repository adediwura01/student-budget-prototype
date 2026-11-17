import { dateNumber } from '../finance/dashboard.js'
import { selectPlans } from '../finance/plans.js'
import { formatTransactionDate } from '../finance/transactions.js'

export const notificationOptions = [
  { id: 'budgetThreshold', title: 'Budget threshold alerts', description: 'Show existing alerts for monthly category budgets that are getting close to their allocation.' },
  { id: 'overspending', title: 'Overspending alerts', description: 'Show existing alerts when a monthly category budget exceeds its allocation.' },
  { id: 'upcomingExpenses', title: 'Upcoming planned expenses', description: 'Show pending expense plans due today or within seven days of the FinSet demo date.' },
  { id: 'planningReminders', title: 'Financial planning reminders', description: 'Show overdue plans and expected income due today or within seven days of the demo date.' },
]

export function createSettingsPreferences(weekStart = 1) {
  if (![1, 7].includes(weekStart)) throw new RangeError('Choose Monday or Sunday.')
  return { weekStart, notifications: { budgetThreshold: true, overspending: true, upcomingExpenses: false, planningReminders: false } }
}

export function updateSettingsPreference(preferences, key, value) {
  if (key === 'weekStart') {
    if (![1, 7].includes(value)) throw new RangeError('Choose Monday or Sunday.')
    return { ...preferences, weekStart: value }
  }
  if (!notificationOptions.some((option) => option.id === key)) throw new RangeError('Unknown notification preference.')
  if (typeof value !== 'boolean') throw new TypeError('Notification preferences must be boolean.')
  return { ...preferences, notifications: { ...preferences.notifications, [key]: value } }
}

export function selectSettingsNotifications(workspace, dashboard, preferences) {
  const options = preferences.notifications
  const notifications = dashboard.notifications.filter((notification) => {
    const status = dashboard.budget.categories.find((category) => category.id === notification.id)?.status
    return status === 'over' ? options.overspending : status === 'warning' && options.budgetThreshold
  })
  if (!options.upcomingExpenses && !options.planningReminders) return notifications

  const reference = dateNumber(workspace.asOf)
  const upcomingEnd = reference + 7 * 86400000
  const plans = selectPlans(workspace, dashboard.month).pending
  for (const plan of plans) {
    const date = dateNumber(plan.date)
    const dateLabel = formatTransactionDate(plan.date)
    if (date < reference && options.planningReminders) {
      notifications.push({ id: `plan-reminder-${plan.id}`, icon: 'planning', title: 'Plan needs a follow-up',
        message: `${plan.name} was planned for ${dateLabel}. Review or reschedule it in Financial Planning; it is still pending.` })
    } else if (date >= reference && date <= upcomingEnd) {
      if (plan.type === 'expense' && options.upcomingExpenses) {
        notifications.push({ id: `planned-expense-${plan.id}`, icon: 'clock', title: 'Upcoming planned expense',
          message: `${plan.name} is planned for ${dateLabel}. This is a plan, not actual spending.` })
      } else if (plan.type === 'income' && options.planningReminders) {
        notifications.push({ id: `expected-income-${plan.id}`, icon: 'planning', title: 'Expected income reminder',
          message: `${plan.name} is expected on ${dateLabel}. It is not actual income until recorded.` })
      }
    }
  }
  return notifications
}
