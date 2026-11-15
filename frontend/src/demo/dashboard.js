// Synthetic NGN workspace. No API adapter, credentials, or production records.
// All monetary values are integer kobo. The demo clock makes reviews repeatable.
export const demoDate = '2026-11-13'

export const dashboardCategories = [
  { id: 'housing', name: 'Housing & bills', icon: 'wallet', tone: 'purple' },
  { id: 'food', name: 'Food & groceries', icon: 'food', tone: 'lavender' },
  { id: 'transport', name: 'Transport', icon: 'transport', tone: 'blue' },
  { id: 'education', name: 'Education', icon: 'book', tone: 'peach' },
  { id: 'lifestyle', name: 'Lifestyle', icon: 'bag', tone: 'green' },
  { id: 'health', name: 'Health & wellbeing', icon: 'bag', tone: 'peach' },
]

export const dashboardIncomeCategories = [
  { id: 'allowance', name: 'Family allowance', icon: 'cash-coin', tone: 'green', type: 'income' },
  { id: 'work', name: 'Work & freelance', icon: 'wallet', tone: 'blue', type: 'income' },
  { id: 'scholarship', name: 'Scholarship', icon: 'book', tone: 'peach', type: 'income' },
]

const monthlyAllocation = { housing: 3000000, food: 1200000, transport: 500000, education: 600000, lifestyle: 700000 }
const entries = [
  ['sep01', 'Family allowance', 'income', 'allowance', 4000000, '2026-09-01'],
  ['sep02', 'Room rent', 'expense', 'housing', 2500000, '2026-09-02'],
  ['sep10', 'Groceries & meals', 'expense', 'food', 1200000, '2026-09-10'],
  ['sep14', 'Campus transport', 'expense', 'transport', 500000, '2026-09-14'],
  ['sep15', 'Design work', 'income', 'work', 3500000, '2026-09-15'],
  ['sep18', 'Course materials', 'expense', 'education', 700000, '2026-09-18'],
  ['sep25', 'Data & subscriptions', 'expense', 'lifestyle', 500000, '2026-09-25'],
  ['oct01', 'Family allowance', 'income', 'allowance', 4500000, '2026-10-01'],
  ['oct02', 'Room rent', 'expense', 'housing', 2500000, '2026-10-02'],
  ['oct09', 'Groceries & meals', 'expense', 'food', 1600000, '2026-10-09'],
  ['oct12', 'Campus transport', 'expense', 'transport', 600000, '2026-10-12'],
  ['oct16', 'Campus design work', 'income', 'work', 2700000, '2026-10-16'],
  ['oct18', 'Course materials', 'expense', 'education', 700000, '2026-10-18'],
  ['oct20', 'Scholarship payment', 'income', 'scholarship', 2000000, '2026-10-20'],
  ['oct25', 'Data & subscriptions', 'expense', 'lifestyle', 600000, '2026-10-25'],
  ['nov01', 'Family allowance', 'income', 'allowance', 4500000, '2026-11-01'],
  ['nov02', 'Room rent', 'expense', 'housing', 2500000, '2026-11-02'],
  ['nov03a', 'Campus design work', 'income', 'work', 1800000, '2026-11-03'],
  ['nov03b', 'Weekly groceries', 'expense', 'food', 450000, '2026-11-03'],
  ['nov04', 'Campus shuttle', 'expense', 'transport', 120000, '2026-11-04'],
  ['nov05', 'Data structures textbook', 'expense', 'education', 350000, '2026-11-05'],
  ['nov06', 'Mobile data', 'expense', 'lifestyle', 200000, '2026-11-06'],
  ['nov08', 'Lunch with friends', 'expense', 'food', 180000, '2026-11-08'],
  ['nov09', 'Weekly groceries', 'expense', 'food', 320000, '2026-11-09'],
  ['nov10a', 'Freelance illustration', 'income', 'work', 1250000, '2026-11-10'],
  ['nov10b', 'Campus commute', 'expense', 'transport', 100000, '2026-11-10'],
  ['nov11', 'Printing & study notes', 'expense', 'education', 80000, '2026-11-11'],
  ['nov12a', 'Scholarship payment', 'income', 'scholarship', 3000000, '2026-11-12'],
  ['nov12b', 'Market groceries', 'expense', 'food', 265000, '2026-11-12'],
  ['nov13a', 'Coffee & a snack', 'expense', 'food', 90000, '2026-11-13'],
  ['nov13b', 'Bus fare & errands', 'expense', 'transport', 175000, '2026-11-13'],
  ['nov13c', 'Student gym membership', 'expense', 'lifestyle', 200000, '2026-11-13'],
]

export function createDashboardWorkspace() {
  return {
    asOf: demoDate,
    profile: { name: 'Amara Okafor', course: 'Computer Science student', weekStart: 1 },
    categories: dashboardCategories.map((category) => ({ ...category })),
    incomeCategories: dashboardIncomeCategories.map((category) => ({ ...category })),
    transactions: entries.map(([id, name, type, category, amount, date]) => ({ id, name, type, category, amount, date, confirmed: true, deleted: false })),
    monthlyBudgets: ['2026-09', '2026-10', '2026-11'].flatMap((month) => dashboardCategories
      .filter(({ id }) => monthlyAllocation[id] !== undefined)
      .map(({ id }) => ({ id: `${month}-${id}`, month, category: id, allocation: monthlyAllocation[id], archived: false }))),
    trackingLimits: [
      { id: 'daily-food', period: 'daily', category: 'food', amount: 150000 },
      { id: 'weekly-food', period: 'weekly', category: 'food', amount: 500000 },
    ],
    plans: [
      { id: 'plan-allowance', name: 'Family allowance', type: 'income', amount: 1800000, date: '2026-11-15', category: 'allowance', status: 'pending', note: 'Monthly transfer from home' },
      { id: 'plan-books', name: 'Course materials', type: 'expense', amount: 450000, date: '2026-11-16', category: 'education', status: 'pending', note: 'Two textbooks and a lab manual' },
      { id: 'plan-power', name: 'Shared electricity bill', type: 'expense', amount: 300000, date: '2026-11-18', category: 'housing', status: 'pending', note: 'Split three ways with flatmates' },
      { id: 'plan-design', name: 'Design project payout', type: 'income', amount: 2200000, date: '2026-11-19', category: 'work', status: 'pending', note: 'Final invoice for the campus poster set' },
      { id: 'plan-transport', name: 'Transport for next week', type: 'expense', amount: 600000, date: '2026-11-21', category: 'transport', status: 'pending', note: 'Weekly shuttle pass' },
    ],
  }
}
