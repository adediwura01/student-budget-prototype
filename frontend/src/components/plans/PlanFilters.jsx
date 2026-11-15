import Input from '../ui/Input'
import Select from '../ui/Select'
import Button from '../ui/Button'
import { activePlanFilterCount, planSortLabel, planSorts } from '../../finance/plans'
import { categoriesForType } from '../../finance/transactions'

const typeOptions = [
  { value: 'all', label: 'All types' },
  { value: 'income', label: 'Expected income' },
  { value: 'expense', label: 'Planned expenses' },
]

const statusOptions = [
  { value: 'all', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'confirmed', label: 'Confirmed' },
]

export default function PlanFilters({ filters, categories, onChange, onClear }) {
  const expenses = categoriesForType(categories, 'expense')
  const incomes = categoriesForType(categories, 'income')
  const active = activePlanFilterCount(filters)

  return (
    <div className="plan-filters" role="search" aria-label="Filter plans">
      <div className="plan-filter-search">
        <Input
          label="Search"
          type="search"
          value={filters.search}
          placeholder="Search descriptions"
          autoComplete="off"
          onChange={(event) => onChange('search', event.target.value)}
        />
      </div>
      <div className="plan-filter-field">
        <Select label="Type" value={filters.type} onChange={(event) => onChange('type', event.target.value)}>
          {typeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </Select>
      </div>
      <div className="plan-filter-field">
        <Select label="Status" value={filters.status} onChange={(event) => onChange('status', event.target.value)}>
          {statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </Select>
      </div>
      <div className="plan-filter-field">
        <Select label="Category" value={filters.category} onChange={(event) => onChange('category', event.target.value)}>
          <option value="all">All categories</option>
          {expenses.length > 0 && <optgroup label="Planned expenses">{expenses.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</optgroup>}
          {incomes.length > 0 && <optgroup label="Expected income">{incomes.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</optgroup>}
        </Select>
      </div>
      <div className="plan-filter-field">
        <Select label="Sort" value={filters.sort} onChange={(event) => onChange('sort', event.target.value)}>
          {planSorts.map((sort) => <option key={sort} value={sort}>{planSortLabel(sort)}</option>)}
        </Select>
      </div>
      <div className="plan-filter-actions">
        <Button variant="tertiary" icon="refresh" onClick={onClear} disabled={active === 0}>Clear filters</Button>
      </div>
    </div>
  )
}