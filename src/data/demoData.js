export const expenseCategories = [
  { id: 'housing', name: 'Housing & bills', icon: 'home', color: '#8062d6', tint: '#f0eafa' },
  { id: 'food', name: 'Food & drinks', icon: 'food', color: '#af91df', tint: '#f4eefb' },
  { id: 'education', name: 'Education', icon: 'book', color: '#c8b6e5', tint: '#f4f0fa' },
  { id: 'transport', name: 'Transport', icon: 'bus', color: '#98aecb', tint: '#edf2f8' },
  { id: 'lifestyle', name: 'Lifestyle', icon: 'bag', color: '#d7a5b8', tint: '#fbf0f4' },
]

export const incomeCategories = [
  { id: 'work', name: 'Part-time work', icon: 'work', color: '#28846a', tint: '#eaf6ef' },
  { id: 'allowance', name: 'Allowance', icon: 'income', color: '#28846a', tint: '#eaf6ef' },
  { id: 'scholarship', name: 'Scholarship', icon: 'graduation', color: '#28846a', tint: '#eaf6ef' },
  { id: 'freelance', name: 'Freelance', icon: 'pen', color: '#28846a', tint: '#eaf6ef' },
]

export const categories = [...expenseCategories, ...incomeCategories]

// All monetary values are integer cents, including the sample data.
export const defaultBudget = { housing: 80000, food: 30000, education: 15000, transport: 10000, lifestyle: 15000 }

const octoberTransactions = [
  { id: 'oct-01', name: 'Campus library', type: 'income', category: 'work', amount: 18500, date: '2026-10-29' },
  { id: 'oct-02', name: 'Weekly groceries', type: 'expense', category: 'food', amount: 4850, date: '2026-10-28' },
  { id: 'oct-03', name: 'Spotify Student', type: 'expense', category: 'lifestyle', amount: 599, date: '2026-10-27' },
  { id: 'oct-04', name: 'Coffee with friends', type: 'expense', category: 'food', amount: 1250, date: '2026-10-26' },
  { id: 'oct-05', name: 'Freelance design', type: 'income', category: 'freelance', amount: 32000, date: '2026-10-25' },
  { id: 'oct-06', name: 'Design textbooks', type: 'expense', category: 'education', amount: 6400, date: '2026-10-24' },
  { id: 'oct-07', name: 'Campus lunch', type: 'expense', category: 'food', amount: 975, date: '2026-10-23' },
  { id: 'oct-08', name: 'Monthly bus pass', type: 'expense', category: 'transport', amount: 4500, date: '2026-10-21' },
  { id: 'oct-09', name: 'Weekly groceries', type: 'expense', category: 'food', amount: 6235, date: '2026-10-19' },
  { id: 'oct-10', name: 'Student allowance', type: 'income', category: 'allowance', amount: 90000, date: '2026-10-18' },
  { id: 'oct-11', name: 'Room rent', type: 'expense', category: 'housing', amount: 65000, date: '2026-10-16' },
  { id: 'oct-12', name: 'Study supplies', type: 'expense', category: 'education', amount: 2800, date: '2026-10-14' },
  { id: 'oct-13', name: 'Campus library', type: 'income', category: 'work', amount: 24500, date: '2026-10-12' },
  { id: 'oct-14', name: 'Movie night', type: 'expense', category: 'lifestyle', amount: 1800, date: '2026-10-10' },
  { id: 'oct-15', name: 'Weekly groceries', type: 'expense', category: 'food', amount: 5490, date: '2026-10-08' },
  { id: 'oct-16', name: 'Mobile data', type: 'expense', category: 'lifestyle', amount: 2000, date: '2026-10-06' },
  { id: 'oct-17', name: 'Film club membership', type: 'expense', category: 'lifestyle', amount: 2500, date: '2026-10-05' },
  { id: 'oct-18', name: 'Campus lunch', type: 'expense', category: 'food', amount: 1050, date: '2026-10-04' },
  { id: 'oct-19', name: 'Shared utilities', type: 'expense', category: 'housing', amount: 8000, date: '2026-10-02' },
  { id: 'oct-20', name: 'Merit scholarship', type: 'income', category: 'scholarship', amount: 160000, date: '2026-10-01' },
  { id: 'oct-21', name: 'Student allowance', type: 'income', category: 'allowance', amount: 60000, date: '2026-10-01' },
]

// Earlier demo months make the month selector and comparisons useful in review.
const earlierTransactions = ['2026-09', '2026-08'].flatMap((month, index) =>
  octoberTransactions.map((transaction) => ({
    ...transaction,
    id: `${month}-${transaction.id}`,
    date: `${month}${transaction.date.slice(7)}`,
    amount: Math.round(transaction.amount * (transaction.type === 'income' ? 0.91 - index * 0.07 : 1.08 + index * 0.04)),
  })),
)

export function createDemoWorkspace() {
  return {
    transactions: [...octoberTransactions, ...earlierTransactions].map((transaction) => ({ ...transaction })),
    budgets: { '2026-10': { ...defaultBudget }, '2026-09': { ...defaultBudget }, '2026-08': { ...defaultBudget } },
    goals: [
      { id: 'laptop', name: 'A new laptop', saved: 75000, target: 150000, icon: 'laptop', color: 'purple' },
      { id: 'emergency', name: 'Emergency fund', saved: 24000, target: 60000, icon: 'shield', color: 'green' },
      { id: 'semester', name: 'Next semester', saved: 32000, target: 100000, icon: 'graduation', color: 'peach' },
    ],
    profile: { name: 'Alex Johnson', course: 'Computer Science student' },
    showCents: true,
  }
}
