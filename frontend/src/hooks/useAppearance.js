import { useEffect, useLayoutEffect, useState } from 'react'

const storageKey = 'finset.appearance'
const choices = ['light', 'dark', 'system']

function initialAppearance() {
  try {
    const value = localStorage.getItem(storageKey)
    return { appearance: choices.includes(value) ? value : 'light', persistent: true }
  } catch {
    return { appearance: 'light', persistent: false }
  }
}

export default function useAppearance() {
  const [preference, setPreference] = useState(initialAppearance)
  const [systemDark, setSystemDark] = useState(() => matchMedia('(prefers-color-scheme: dark)').matches)
  const { appearance, persistent } = preference
  const resolvedTheme = appearance === 'system' ? (systemDark ? 'dark' : 'light') : appearance

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme
    document.documentElement.dataset.appearance = appearance
  }, [appearance, resolvedTheme])

  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)')
    const updateSystem = (event) => setSystemDark(event.matches)
    const updateStored = (event) => {
      if (event.key === storageKey || event.key === null) {
        setPreference({ appearance: choices.includes(event.newValue) ? event.newValue : 'light', persistent: true })
      }
    }
    media.addEventListener('change', updateSystem)
    window.addEventListener('storage', updateStored)
    return () => {
      media.removeEventListener('change', updateSystem)
      window.removeEventListener('storage', updateStored)
    }
  }, [])

  function setAppearance(value) {
    if (!choices.includes(value)) return
    let saved = true
    try {
      localStorage.setItem(storageKey, value)
    } catch {
      saved = false
    }
    setPreference({ appearance: value, persistent: saved })
    return saved
  }

  return { appearance, resolvedTheme, setAppearance, persistent }
}
