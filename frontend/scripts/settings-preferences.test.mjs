import test from 'node:test'
import assert from 'node:assert/strict'
import { createDashboardWorkspace } from '../src/demo/dashboard.js'
import { selectDashboard } from '../src/finance/dashboard.js'
import { selectBudgets } from '../src/finance/budgets.js'
import { selectPlans } from '../src/finance/plans.js'
import { resolveReportRange, selectReports } from '../src/finance/reports.js'
import { createSettingsPreferences, notificationOptions, selectSettingsNotifications, updateSettingsPreference } from '../src/utils/settingsPreferences.js'

const workspace = createDashboardWorkspace()
const dashboard = selectDashboard(workspace, '2026-11')

function choices(overrides = {}) {
  const defaults = createSettingsPreferences()
  return { ...defaults, notifications: { ...defaults.notifications, ...overrides } }
}

test('defaults retain existing budget alerts and make planning reminders opt-in', () => {
  assert.deepEqual(createSettingsPreferences(), {
    weekStart: 1,
    notifications: { budgetThreshold: true, overspending: true, upcomingExpenses: false, planningReminders: false },
  })
  assert.equal(notificationOptions.length, 4)
  assert.equal(createSettingsPreferences(7).weekStart, 7)
  const first = createSettingsPreferences()
  first.notifications.budgetThreshold = false
  assert.equal(createSettingsPreferences().notifications.budgetThreshold, true)
})

test('week preferences accept only the existing Monday and Sunday values', () => {
  const preferences = createSettingsPreferences()
  assert.equal(updateSettingsPreference(preferences, 'weekStart', 7).weekStart, 7)
  assert.equal(preferences.weekStart, 1)
  for (const value of [0, 2, 6, 8, '7', NaN, null]) {
    assert.throws(() => createSettingsPreferences(value), RangeError)
    assert.throws(() => updateSettingsPreference(preferences, 'weekStart', value), RangeError)
  }
})

test('every notification toggle updates only its own boolean without mutating defaults', () => {
  for (const option of notificationOptions) {
    const preferences = createSettingsPreferences()
    const previous = structuredClone(preferences)
    const next = updateSettingsPreference(preferences, option.id, !preferences.notifications[option.id])
    assert.equal(next.notifications[option.id], !previous.notifications[option.id])
    assert.deepEqual(preferences, previous)
    assert.equal(next.weekStart, preferences.weekStart)
    assert.equal(Object.keys(next.notifications).length, 4)
  }
  for (const key of ['unknown', '__proto__', 'currency', 'appearance']) {
    assert.throws(() => updateSettingsPreference(createSettingsPreferences(), key, true), RangeError)
  }
  for (const value of ['true', 1, null, undefined]) {
    assert.throws(() => updateSettingsPreference(createSettingsPreferences(), 'overspending', value), TypeError)
  }
})

test('default in-app notifications are exactly the existing dashboard notifications', () => {
  assert.deepEqual(selectSettingsNotifications(workspace, dashboard, createSettingsPreferences()), dashboard.notifications)
})

test('budget threshold and overspending switches filter existing statuses independently', () => {
  assert.deepEqual(selectSettingsNotifications(workspace, dashboard, choices({ overspending: false })).map((row) => row.id), ['housing'])
  assert.deepEqual(selectSettingsNotifications(workspace, dashboard, choices({ budgetThreshold: false })).map((row) => row.id), ['food'])
  assert.deepEqual(selectSettingsNotifications(workspace, dashboard, choices({ budgetThreshold: false, overspending: false })), [])
})

test('planned expense reminders use the existing selected-month pending plans and seven-day window', () => {
  const notifications = selectSettingsNotifications(workspace, dashboard, choices({ budgetThreshold: false, overspending: false, upcomingExpenses: true }))
  assert.deepEqual(notifications.map((row) => row.id), ['planned-expense-plan-books', 'planned-expense-plan-power'])
  assert.ok(notifications.every((row) => row.message.includes('not actual spending')))
  assert.ok(!notifications.some((row) => row.id.includes('transport')))
})

test('financial planning reminders show expected income, not actual income', () => {
  const notifications = selectSettingsNotifications(workspace, dashboard, choices({ budgetThreshold: false, overspending: false, planningReminders: true }))
  assert.deepEqual(notifications.map((row) => row.id), ['expected-income-plan-allowance', 'expected-income-plan-design'])
  assert.ok(notifications.every((row) => row.message.includes('not actual income')))
})

test('overdue pending plans are reminders without duplicate upcoming-expense alerts', () => {
  const data = createDashboardWorkspace()
  data.plans.push({ id: 'overdue', name: 'Overdue expense', type: 'expense', amount: 101, category: 'food', date: '2026-11-12', status: 'pending' })
  const notifications = selectSettingsNotifications(data, selectDashboard(data, '2026-11'), choices({ upcomingExpenses: true, planningReminders: true }))
  assert.equal(notifications.filter((row) => row.id.includes('overdue')).length, 1)
  assert.ok(notifications.find((row) => row.id === 'plan-reminder-overdue').message.includes('still pending'))
})

test('today and the seventh future day are included, but the eighth day is not', () => {
  const data = createDashboardWorkspace()
  data.plans = ['2026-11-13', '2026-11-20', '2026-11-21'].map((date, index) => ({ id: `day-${index}`, name: 'Planned expense', type: 'expense', amount: 101, category: 'food', date, status: 'pending' }))
  const notifications = selectSettingsNotifications(data, selectDashboard(data, '2026-11'), choices({ budgetThreshold: false, overspending: false, upcomingExpenses: true, planningReminders: true }))
  assert.deepEqual(notifications.map((row) => row.id), ['planned-expense-day-0', 'planned-expense-day-1'])
})

test('confirmed plans and other selected months do not generate pending-plan reminders', () => {
  const data = createDashboardWorkspace()
  data.plans = data.plans.map((plan) => ({ ...plan, status: 'confirmed', actualAmount: plan.amount }))
  const preferences = choices({ upcomingExpenses: true, planningReminders: true })
  assert.deepEqual(selectSettingsNotifications(data, selectDashboard(data, '2026-11'), preferences), selectDashboard(data, '2026-11').notifications)
  assert.deepEqual(selectSettingsNotifications(workspace, selectDashboard(workspace, '2026-10'), preferences), selectDashboard(workspace, '2026-10').notifications)
})

test('all preferences can be off, while turning everything on adds only four eligible plan alerts', () => {
  const enabled = Object.fromEntries(notificationOptions.map((option) => [option.id, true]))
  const disabled = Object.fromEntries(notificationOptions.map((option) => [option.id, false]))
  assert.equal(selectSettingsNotifications(workspace, dashboard, choices(enabled)).length, 6)
  assert.deepEqual(selectSettingsNotifications(workspace, dashboard, choices(disabled)), [])
})

test('week-start changes existing weekly views without changing monthly financial totals or the ledger', () => {
  const before = structuredClone(workspace)
  const sunday = { ...workspace, profile: { ...workspace.profile, weekStart: 7 } }
  const mondayDashboard = selectDashboard(workspace, '2026-11')
  const sundayDashboard = selectDashboard(sunday, '2026-11')
  assert.deepEqual(sundayDashboard.money, mondayDashboard.money)
  assert.deepEqual(sundayDashboard.budget, mondayDashboard.budget)
  assert.notDeepEqual(sundayDashboard.chart.buckets, mondayDashboard.chart.buckets)
  assert.deepEqual(selectBudgets(sunday, '2026-11').categories, selectBudgets(workspace, '2026-11').categories)
  const range = resolveReportRange(workspace.asOf)
  assert.deepEqual(selectReports(sunday, range).summary, selectReports(workspace, range).summary)
  assert.notDeepEqual(selectReports(sunday, range).flow, selectReports(workspace, range).flow)
  assert.deepEqual(selectPlans(sunday, '2026-11'), selectPlans(workspace, '2026-11'))
  assert.deepEqual(workspace, before)
})

test('notification selection never changes transactions, plans, budgets or profile information', () => {
  const before = structuredClone(workspace)
  const dashboardBefore = structuredClone(dashboard)
  selectSettingsNotifications(workspace, dashboard, choices({ upcomingExpenses: true, planningReminders: true }))
  assert.deepEqual(workspace, before)
  assert.deepEqual(dashboard, dashboardBefore)
})
