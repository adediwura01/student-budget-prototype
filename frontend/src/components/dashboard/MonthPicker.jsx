import Icon from '../Icon'
import { monthName } from '../../finance/dashboard'

export default function MonthPicker({ months, value, onChange, label = 'Reporting month' }) {
  return (
    <label className="month-picker">
      <Icon name="calendar3" size={16} className="month-picker-icon" />
      <span className="sr-only">{label}</span>
      <select className="month-picker-select" value={value} aria-label={label} onChange={(event) => onChange(event.target.value)}>
        {months.map((month) => <option key={month} value={month}>{monthName(month)}</option>)}
      </select>
      <Icon name="chevron" size={14} className="month-picker-chevron" />
    </label>
  )
}