import Icon from './Icon'

export default function SummaryCard({ title, amount, icon, tone, change, note, lowerIsBetter = false, featured = false }) {
  const improved = change !== null && (lowerIsBetter ? change <= 0 : change >= 0)
  return <article className={`summary-card ${featured ? 'summary-featured' : ''}`}>
    <div className="summary-card-heading"><span className={`summary-icon tone-${tone}`}><Icon name={icon} size={19} /></span><h3>{title}</h3><Icon className="summary-corner-icon" name="arrowUp" size={15} /></div>
    <p className="summary-amount">{amount}</p>
    <div className="summary-card-footer">{change !== undefined && change !== null ? <><span className={`change-badge ${improved ? 'is-positive' : 'is-negative'}`}><Icon name={change >= 0 ? 'trendUp' : 'trendDown'} size={12} />{Math.abs(change).toFixed(1)}%</span><span>vs. last month</span></> : <><span className={`summary-note-icon tone-${tone}`}><Icon name={icon === 'savings' ? 'target' : 'check'} size={13} /></span><span>{note ?? 'No previous month data'}</span></>}</div>
  </article>
}
