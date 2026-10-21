export type TEvent = {stage: string; message: string; detail?: string; elapsed?: number}

export type Stats = {type: 'stats'; title: string; items: {label: string; value: string}[]}
export type Series = {key: string; label: string; unit?: string}
export type Chart = {type: 'chart'; title: string; chartType: 'line' | 'bar'; xKey: string; series: Series[]; data: Record<string, string | number | null>[]}
export type Table = {type: 'table'; title: string; columns: string[]; rows: string[][]}
export type TextBlock = {type: 'text'; title: string; content: string}
export type Block = Stats | Chart | Table | TextBlock

export type Provider = {name: string; url: string; description: string; category: string}

export type Answer = {
  ui: {title: string; subtitle: string; summary: string; caveat: string; blocks: Block[]}
  provider: Provider
  source_url: string
  trace: TEvent[]
  raw_excerpt: string
  retrieved_at: string
}

export type Saved = {question: string; result: Answer; date: string}

export type Health = 'loading' | 'ok' | 'unconfigured' | 'offline'

export type Progress = {mode: 'live' | 'estimated'; events: TEvent[]; startedAt: number}
