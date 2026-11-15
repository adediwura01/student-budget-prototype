import Input from '../ui/Input'
import Select from '../ui/Select'
import Button from '../ui/Button'
import { activeFilterCount, categoriesForType, transactionSorts } from '../../finance/transactions'

const typeOptions = [
  { value: 'all', label: 'All types' },
  { value: 'income', label: 'Income' },
  { value: 'expense', label: 'Expenses' },
]

const sortLabels = {
  newest: 'Newest first',
  oldest: 'Oldest first',
  highest: 'Highest amount',
  lowest: 'Lowest amount',
}

export default function TransactionFilters({ filters, categories, onChange, onClear, dateError }) {
  const expenses = categoriesForType(categories, 'expense')
  const incomes = categoriesForType(categories, 'income')
  const active = activeFilterCount(filters)

  return (
    <div className="tx-filters" role="search" aria-label="Filter transactions">
      <div className="tx-filter-search">
        <Input
          label="Search"
          type="search"
          value={filters.search}
          placeholder="Search descriptions"
          autoComplete="off"
          onChange={(event) => onChange('search', event.target.value)}
        />
      </div>
      <div className="tx-filter-field">
        <Select label="Type" value={filters.type} onChange={(event) => onChange('type', event.target.value)}>
          {typeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </Select>
      </div>
      <div className="tx-filter-field">
        <Select label="Category" value={filters.category} onChange={(event) => onChange('category', event.target.value)}>
          <option value="all">All categories</option>
          {expenses.length > 0 && <optgroup label="Expenses">{expenses.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</optgroup>}
          {incomes.length > 0 && <optgroup label="Income">{incomes.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</optgroup>}
        </Select>
      </div>
      <div className="tx-filter-dates">
        <Input
          label="From"
          type="date"
          value={filters.from}
          max={filters.to || undefined}
          onChange={(event) => onChange('from', event.target.value)}
        />
        <Input
          label="To"
          type="date"
          value={filters.to}
          min={filters.from || undefined}
          onChange={(event) => onChange('to', event.target.value)}
        />
      </div>
      <div className="tx-filter-field">
        <Select label="Sort" value={filters.sort} onChange={(event) => onChange('sort', event.target.value)}>
          {transactionSorts.map((sort) => <option key={sort} value={sort}>{sortLabels[sort]}</option>)}
        </Select>
      </div>
      <div className="tx-filter-actions">
        <Button variant="tertiary" icon="refresh" onClick={onClear} disabled={active === 0}>Clear filters</Button>
      </div>
      {dateError && <p className="ui-field-error tx-date-error" role="alert">{dateError}</p>}
    </div>
  )
}