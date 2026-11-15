export default function Brand({ compact = false }) {
  return <a className={`brand ${compact ? 'brand--compact' : ''}`} href="#/dashboard" aria-label="FinSet dashboard">
    <span className="brand-symbol" aria-hidden="true"><span /><span /><span /></span>
    <span className="brand-wordmark">FinSet<span>Money, made clear.</span></span>
  </a>
}
