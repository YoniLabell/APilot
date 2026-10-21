import {useId, useMemo, useState} from 'react'
import {ArrowDown, ArrowUp, ArrowUpDown} from 'lucide-react'
import {Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps} from 'recharts'
import type {Block, Chart, Series, Stats, Table, TextBlock} from '../types'
import {formatCompact, formatNumber, toNumber} from '../lib/format'

// Theme-aware palette, defined as --c1..--c4 in styles.css.
export const CHART_COLORS = ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)']

function StatsBlock({block}: {block: Stats}) {
  return <section className="block">
    {block.title && <h3>{block.title}</h3>}
    <div className="stats">
      {block.items.map((item, i) => <div className="stat" key={i} style={{'--tone': CHART_COLORS[i % CHART_COLORS.length]} as React.CSSProperties}>
        <small>{item.label}</small><strong dir="auto">{item.value}</strong>
      </div>)}
    </div>
  </section>
}

function ChartTooltip({active, payload, label, series}: TooltipProps<number, string> & {series: Series[]}) {
  if (!active || !payload?.length) return null
  return <div className="chart-tooltip">
    <b>{label}</b>
    {payload.map(item => {
      const unit = series.find(s => s.key === item.dataKey)?.unit
      return <span key={String(item.dataKey)}>
        <i style={{background: item.color}}/>{item.name}
        <strong>{typeof item.value === 'number' ? formatNumber(item.value) : item.value}{unit ? ` ${unit}` : ''}</strong>
      </span>
    })}
  </div>
}

function ChartBlock({block}: {block: Chart}) {
  const id = useId().replace(/:/g, '')
  // Older saved results may still carry numbers as strings.
  const data = useMemo(() => block.data.map(row => {
    const copy: Record<string, string | number | null> = {...row}
    for (const s of block.series) copy[s.key] = toNumber(row[s.key])
    return copy
  }), [block])
  const series = block.series.filter(s => data.some(row => typeof row[s.key] === 'number'))
  if (!series.length) return null
  const axis = {tick: {fill: 'var(--text-3)', fontSize: 11}, tickLine: false, axisLine: false}
  const common = {data, margin: {top: 8, left: 0, right: 8, bottom: 0}}
  const shared = <>
    <defs>{series.map((s, i) => <linearGradient key={s.key} id={`${id}-${i}`} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor={CHART_COLORS[i]} stopOpacity={block.chartType === 'line' ? 0.35 : 1}/>
      <stop offset="100%" stopColor={CHART_COLORS[i]} stopOpacity={block.chartType === 'line' ? 0 : 0.55}/>
    </linearGradient>)}</defs>
    <CartesianGrid stroke="var(--grid)" strokeDasharray="3 6" vertical={false}/>
    <XAxis dataKey={block.xKey} {...axis} minTickGap={12}/>
    <YAxis {...axis} width={48} tickFormatter={(v: number) => formatCompact(v)}/>
    <Tooltip content={<ChartTooltip series={series}/>} cursor={{fill: 'var(--cursor)', stroke: 'var(--line-strong)'}}/>
    {series.length > 1 && <Legend iconType="circle" iconSize={8} wrapperStyle={{fontSize: 12, paddingTop: 8}}/>}
  </>
  const name = (s: Series) => s.unit ? `${s.label || s.key} (${s.unit})` : s.label || s.key
  return <section className="block">
    <h3>{block.title}</h3>
    <div className="chart" dir="ltr">
      <ResponsiveContainer width="100%" height={280}>
        {block.chartType === 'line'
          ? <AreaChart {...common}>{shared}{series.map((s, i) => <Area key={s.key} name={name(s)} type="monotone" dataKey={s.key}
              stroke={CHART_COLORS[i]} strokeWidth={2.5} fill={`url(#${id}-${i})`} connectNulls
              dot={data.length <= 16 ? {r: 3, strokeWidth: 0, fill: CHART_COLORS[i]} : false} activeDot={{r: 5}}/>)}</AreaChart>
          : <BarChart {...common}>{shared}{series.map((s, i) => <Bar key={s.key} name={name(s)} dataKey={s.key}
              fill={`url(#${id}-${i})`} radius={[6, 6, 0, 0]} maxBarSize={48}/>)}</BarChart>}
      </ResponsiveContainer>
    </div>
  </section>
}

type Sort = {column: number; direction: 'asc' | 'desc'} | null

function TableBlock({block}: {block: Table}) {
  const [sort, setSort] = useState<Sort>(null)
  const rows = useMemo(() => {
    if (!sort) return block.rows
    const {column, direction} = sort
    const factor = direction === 'asc' ? 1 : -1
    return [...block.rows].sort((a, b) => {
      const x = toNumber(a[column]), y = toNumber(b[column])
      if (x !== null && y !== null) return (x - y) * factor
      return String(a[column] ?? '').localeCompare(String(b[column] ?? ''), undefined, {numeric: true}) * factor
    })
  }, [block.rows, sort])
  function toggle(column: number) {
    setSort(prev => prev?.column !== column ? {column, direction: 'asc'} : prev.direction === 'asc' ? {column, direction: 'desc'} : null)
  }
  return <section className="block">
    <div className="block-head"><h3>{block.title}</h3><small>{block.rows.length} rows</small></div>
    <div className="table-wrap">
      <table>
        <thead><tr>{block.columns.map((column, i) => {
          const active = sort?.column === i
          const Icon = !active ? ArrowUpDown : sort.direction === 'asc' ? ArrowUp : ArrowDown
          return <th key={i} aria-sort={!active ? 'none' : sort.direction === 'asc' ? 'ascending' : 'descending'}>
            <button className={active ? 'sorted' : ''} onClick={() => toggle(i)}>{column}<Icon size={13}/></button>
          </th>
        })}</tr></thead>
        <tbody>{rows.map((row, i) => <tr key={i}>{row.map((value, j) =>
          <td dir="auto" key={j} className={toNumber(value) !== null ? 'num' : ''}>{value}</td>)}</tr>)}</tbody>
      </table>
    </div>
  </section>
}

function TextBlockView({block}: {block: TextBlock}) {
  return <section className="block">{block.title && <h3>{block.title}</h3>}<p className="block-text">{block.content}</p></section>
}

export function RenderBlock({block}: {block: Block}) {
  if (block.type === 'stats') return <StatsBlock block={block}/>
  if (block.type === 'chart') return <ChartBlock block={block}/>
  if (block.type === 'table') return <TableBlock block={block}/>
  if (block.type === 'text') return <TextBlockView block={block}/>
  return null
}
