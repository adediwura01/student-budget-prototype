const icons = new Set(['transactions', 'budget', 'planning', 'report', 'settings', 'sun', 'moon', 'system',
  'chevron', 'chevron-right', 'check', 'more', 'close', 'plus', 'info', 'arrow', 'bell', 'wallet', 'profile', 'refresh', 'alert',
  'basket', 'bus-front', 'book', 'bag', 'cash-coin', 'receipt', 'calendar3', 'clock', 'download', 'search', 'arrow-up', 'arrow-down', 'piggy-bank'])
const aliases = { dashboard: 'grid', logo: 'grid', calendar: 'calendar3', balance: 'wallet', savings: 'piggy-bank',
  success: 'check', error: 'alert', warning: 'alert', help: 'info', display: 'system', menu: 'more',
  food: 'basket', transport: 'bus-front', income: 'cash-coin', expense: 'receipt', week: 'calendar3' }

export default function Icon({ name, size = 20, className = '' }) {
  const symbol = aliases[name] ?? (icons.has(name) ? name : 'info')
  return <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" focusable="false"><use href={`${import.meta.env.BASE_URL}bootstrap-icons.svg#${symbol}`} /></svg>
}
