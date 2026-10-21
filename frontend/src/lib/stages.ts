import {BookOpen, Brain, Download, LayoutDashboard, Search, type LucideIcon} from 'lucide-react'
import type {TEvent} from '../types'

export const STAGES: {label: string; hint: string; icon: LucideIcon}[] = [
  {label: 'Discover', hint: 'Matching your question to public APIs', icon: Search},
  {label: 'Read docs', hint: 'Reading the provider documentation', icon: BookOpen},
  {label: 'Fetch data', hint: 'Calling the live API endpoint', icon: Download},
  {label: 'Analyze', hint: 'Checking what the data actually says', icon: Brain},
  {label: 'Design', hint: 'Designing your dashboard', icon: LayoutDashboard},
]

/** Seconds after which each stage is assumed to have started when live progress is unavailable. */
const ESTIMATED_STARTS = [0, 4, 9, 17, 25]

const STAGE_OF_EVENT: Record<string, number> = {
  CATALOG: 0, DISCOVERY: 0, DOCUMENTATION: 1, FALLBACK: 1, 'HTTP GET': 2, RESPONSE: 2, RETRY: 2,
  ANALYSIS: 3, 'UI GENERATION': 4, DONE: STAGES.length,
}

/** The furthest stage reached. Two providers can run at once, so the latest event alone would jump back and forth. */
export function liveStage(events: TEvent[]) {
  return events.reduce((stage, event) =>
    event.stage === 'FALLBACK' ? stage : Math.max(stage, STAGE_OF_EVENT[event.stage] ?? 0), 0)
}

export function estimatedStage(elapsedSeconds: number) {
  return ESTIMATED_STARTS.filter(start => elapsedSeconds >= start).length - 1
}

/** The provider currently being tried, taken from the latest "Reading documentation for X" event. */
export function currentProvider(events: TEvent[]) {
  const docs = [...events].reverse().find(e => e.stage === 'DOCUMENTATION')
  return docs?.message.replace(/^Reading documentation for /, '') ?? ''
}

export const STAGE_TONE: Record<string, string> = {
  CATALOG: 'info', DISCOVERY: 'info', DOCUMENTATION: 'info', 'HTTP GET': 'accent', RESPONSE: 'good',
  RETRY: 'warn', FALLBACK: 'warn', ANALYSIS: 'accent', 'UI GENERATION': 'accent', DONE: 'good',
}
