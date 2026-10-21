import {Monitor, Moon, Sun} from 'lucide-react'
import type {ThemeChoice} from '../lib/theme'

const OPTIONS: {value: ThemeChoice; label: string; icon: typeof Sun}[] = [
  {value: 'light', label: 'Light theme', icon: Sun},
  {value: 'system', label: 'Match system theme', icon: Monitor},
  {value: 'dark', label: 'Dark theme', icon: Moon},
]

export function ThemeToggle({value, onChange}: {value: ThemeChoice; onChange: (value: ThemeChoice) => void}) {
  return <div className="theme-toggle" role="group" aria-label="Color theme">
    {OPTIONS.map(({value: option, label, icon: Icon}) => <button key={option} type="button" title={label} aria-label={label}
      aria-pressed={value === option} className={value === option ? 'active' : ''} onClick={() => onChange(option)}>
      <Icon size={15}/>
    </button>)}
  </div>
}
