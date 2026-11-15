import { useEffect, useState } from 'react'

const fallbacks = { income: '#27714f', expense: '#6037a2', grid: '#e9e5ef', axis: '#746a80', cursor: '#f0eafa' }

function readChartTheme() {
  const style = getComputedStyle(document.documentElement)
  const read = (name, fallback) => style.getPropertyValue(name).trim() || fallback
  return {
    income: read('--success', fallbacks.income),
    expense: read('--brand', fallbacks.expense),
    grid: read('--border', fallbacks.grid),
    axis: read('--text-muted', fallbacks.axis),
    cursor: read('--brand-soft', fallbacks.cursor),
  }
}

export default function useChartTheme() {
  const [theme, setTheme] = useState(readChartTheme)

  useEffect(() => {
    const update = () => setTheme(readChartTheme())
    const observer = new MutationObserver(update)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    window.addEventListener('storage', update)
    return () => {
      observer.disconnect()
      window.removeEventListener('storage', update)
    }
  }, [])

  return theme
}