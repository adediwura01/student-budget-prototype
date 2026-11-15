import TransactionModal from './TransactionModal'

export default function AddTransactionModal({ categories, asOf, onClose, onSubmit }) {
  return (
    <TransactionModal
      categories={categories}
      asOf={asOf}
      onClose={onClose}
      onSubmit={onSubmit}
    />
  )
}