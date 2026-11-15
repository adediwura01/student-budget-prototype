export const destinations = [
  { id: 'dashboard', label: 'Dashboard', mobileLabel: 'Dashboard', icon: 'dashboard',
    heading: 'A clearer view of your money.', description: 'Your balance, spending and monthly budgets in one place.' },
  { id: 'transactions', label: 'Transactions', mobileLabel: 'Transactions', icon: 'transactions',
    heading: 'Every transaction, in context.', description: 'Confirmed income and expenses, ready to review and export.' },
  { id: 'budgets', label: 'Budgets', mobileLabel: 'Budgets', icon: 'budget',
    heading: 'Make room for what matters.', description: 'Monthly allocations with category progress and clear limits.' },
  { id: 'financial-planning', label: 'Financial Planning', mobileLabel: 'Planning', icon: 'planning',
    heading: 'Look ahead with confidence.', description: 'Plan future income and expenses without touching actual balances.' },
  { id: 'reports', label: 'Reports', mobileLabel: 'Reports', icon: 'report',
    heading: 'Find the story behind the numbers.', description: 'Monthly summaries built from confirmed activity only.' },
  { id: 'settings', label: 'Settings', mobileLabel: 'Settings', icon: 'settings',
    heading: 'A workspace that feels like yours.', description: 'Appearance, weekly reporting and workspace preferences.' },
]

export function destinationFromHash(hash) {
  const id = hash.replace(/^#\//, '')
  return destinations.find((destination) => destination.id === id) ?? destinations[0]
}