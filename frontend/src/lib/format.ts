const compact = new Intl.NumberFormat(undefined, {notation: 'compact', maximumFractionDigits: 1})
const full = new Intl.NumberFormat(undefined, {maximumFractionDigits: 2})

export function toNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value !== 'string') return null
  const text = value.trim().replace(/,/g, '')
  return /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(text) ? Number(text) : null
}

export const formatCompact = (value: number) => compact.format(value)
export const formatNumber = (value: number) => full.format(value)

export function formatDateTime(iso: string) {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'})
}

export function formatElapsed(seconds: number) {
  const s = Math.max(0, Math.floor(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function slugify(text: string) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'apilot-dashboard'
}

export function download(filename: string, href: string) {
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  link.click()
}
