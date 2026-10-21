import {useEffect, useState} from 'react'
import {local, readText, write} from './storage'

export type ThemeChoice = 'system' | 'light' | 'dark'

const KEY = 'apilot-theme'
const META = {light: '#f4f5fb', dark: '#080e1b'}
const query = () => window.matchMedia('(prefers-color-scheme: light)')

function initial(): ThemeChoice {
  const saved = readText(local, KEY)
  return saved === 'light' || saved === 'dark' ? saved : 'system'
}

/** Theme choice persisted per browser; "system" follows the OS setting. index.html applies it before first paint. */
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(initial)

  useEffect(() => {
    const root = document.documentElement
    function apply() {
      const resolved = choice === 'system' ? (query().matches ? 'light' : 'dark') : choice
      if (choice === 'system') delete root.dataset.theme
      else root.dataset.theme = choice
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', META[resolved])
    }
    apply()
    write(local, KEY, choice)
    if (choice !== 'system') return
    const media = query()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [choice])

  return [choice, setChoice] as const
}
