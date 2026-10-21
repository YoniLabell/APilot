import {useRef, useState} from 'react'
import {BarChart3, CheckCircle2, Copy, Database, ExternalLink, FileDown, FileJson, ImageDown, Layers3,
  LoaderCircle, RefreshCw, ShieldCheck, Sparkles, Terminal, X} from 'lucide-react'
import type {Answer} from '../types'
import {download, formatDateTime, slugify} from '../lib/format'
import {STAGE_TONE} from '../lib/stages'
import {useModal} from '../lib/useModal'
import {RenderBlock} from './Blocks'
import {JsonView} from './JsonView'

type Tab = 'dashboard' | 'trace' | 'json'

type Props = {
  answer: Answer
  question: string
  saved: boolean
  onClose: () => void
  onSave: () => void
  onRefresh: () => void
  notify: (message: string) => void
}

export function ResultModal({answer, question, saved, onClose, onSave, onRefresh, notify}: Props) {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [exporting, setExporting] = useState(false)
  const dialog = useRef<HTMLDivElement>(null)
  const capture = useRef<HTMLDivElement>(null)
  useModal(dialog, onClose)
  const {ui} = answer

  async function copy(text: string, message: string) {
    try {
      await navigator.clipboard.writeText(text)
      notify(message)
    } catch {
      notify('Clipboard is not available in this browser')
    }
  }

  function exportJSON() {
    const blob = new Blob([JSON.stringify({question, ...answer}, null, 2)], {type: 'application/json'})
    const url = URL.createObjectURL(blob)
    download(`${slugify(ui.title)}.json`, url)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    notify('Dashboard exported as JSON')
  }

  async function exportPNG() {
    if (!capture.current || exporting) return
    setExporting(true)
    const node = capture.current
    node.classList.add('capturing')
    try {
      const {toPng} = await import('html-to-image')
      const background = getComputedStyle(document.documentElement).getPropertyValue('--surface').trim() || '#111b2b'
      download(`${slugify(ui.title)}.png`, await toPng(node, {backgroundColor: background, pixelRatio: 2, cacheBust: true}))
      notify('Dashboard exported as PNG')
    } catch {
      notify('Could not export an image in this browser')
    } finally {
      node.classList.remove('capturing')
      setExporting(false)
    }
  }

  const tabs: {id: Tab; label: string; icon: typeof BarChart3; count?: number}[] = [
    {id: 'dashboard', label: 'Dashboard', icon: BarChart3},
    {id: 'trace', label: 'Agent X-Ray', icon: Terminal, count: answer.trace.length},
    {id: 'json', label: 'Raw JSON', icon: FileJson},
  ]

  if (answer.verified !== true) {
    return <div className="overlay" onClick={onClose}>
      <div className="popup" ref={dialog} tabIndex={-1} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Unverified result">
        <header className="popup-head"><div className="popup-title"><h2>Unverified saved result</h2></div>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={20}/></button></header>
        <div className="popup-body"><div className="warning"><ShieldCheck size={18}/>
          <span>This older result has no verified API provenance and cannot be displayed as live data. Run the question again.</span></div></div>
      </div>
    </div>
  }
  return <div className="overlay" onClick={onClose}>
    <div className="popup" ref={dialog} tabIndex={-1} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="result-title">
      <header className="popup-head">
        <div className="popup-title">
          <div className="popup-icon"><Sparkles size={22}/></div>
          <div>
            <small>AI-generated dashboard</small>
            <h2 id="result-title">{ui.title}</h2>
            {ui.subtitle && <p>{ui.subtitle}</p>}
          </div>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close dashboard"><X size={20}/></button>
      </header>

      <div className="tabs" role="tablist">
        {tabs.map(({id, label, icon: Icon, count}) => <button key={id} role="tab" aria-selected={tab === id}
          className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
          <Icon size={16}/> {label}{count !== undefined && <i>{count}</i>}
        </button>)}
      </div>

      <div className="popup-body" role="tabpanel">
        {tab === 'dashboard' && <div className="dashboard" ref={capture}>
          <div className="result-meta">
            <span className="source-badge"><CheckCircle2 size={14}/> Validated API response</span>
            <span className="meta-chip"><Database size={13}/> {answer.provider.name}</span>
            {answer.provider.category && <span className="meta-chip">{answer.provider.category}</span>}
          </div>
          <p className="question-label">“{question}”</p>
          {ui.summary && <p className="result-summary">{ui.summary}</p>}
          {ui.blocks.map((block, i) => <RenderBlock block={block} key={i}/>)}
          {ui.caveat && <div className="warning"><ShieldCheck size={18}/><span>{ui.caveat}</span></div>}
          <div className="source-link">
            <span>Source: <b>{answer.provider.name}</b></span>
            <a href={answer.source_url} target="_blank" rel="noopener noreferrer">Open the API request <ExternalLink size={13}/></a>
          </div>
        </div>}

        {tab === 'trace' && <ol className="trace">
          {answer.trace.map((step, i) => <li className="trace-row" key={i}>
            <div className="trace-num">{i + 1}</div>
            <div>
              <div className="trace-meta">
                <span className={`stage-chip tone-${STAGE_TONE[step.stage] ?? 'info'}`}>{step.stage}</span>
                {step.elapsed !== undefined && <small>+{step.elapsed.toFixed(1)}s</small>}
              </div>
              <b>{step.message}</b>
              {step.detail && <pre>{step.detail}</pre>}
            </div>
          </li>)}
        </ol>}

        {tab === 'json' && <JsonView raw={answer.raw_excerpt} onCopy={text => void copy(text, 'JSON copied')}/>}
      </div>

      <footer className="popup-footer">
        <small>Fetched {formatDateTime(answer.retrieved_at)}</small>
        <div className="footer-actions">
          <button className="secondary-btn" onClick={() => void copy(answer.source_url, 'Source URL copied')}><Copy size={15}/> Copy source</button>
          <div className="btn-group" role="group" aria-label="Export">
            <button className="secondary-btn" onClick={() => void exportPNG()} disabled={tab !== 'dashboard' || exporting}
              title={tab !== 'dashboard' ? 'Open the Dashboard tab to export an image' : 'Download the dashboard as an image'}>
              {exporting ? <LoaderCircle size={15} className="spin"/> : <ImageDown size={15}/>} PNG
            </button>
            <button className="secondary-btn" onClick={exportJSON} title="Download the full result as JSON"><FileDown size={15}/> JSON</button>
          </div>
          <button className="secondary-btn" onClick={onRefresh}><RefreshCw size={15}/> Refresh</button>
          <button className={saved ? 'primary-btn is-saved' : 'primary-btn'} onClick={onSave}>
            {saved ? <CheckCircle2 size={16}/> : <Layers3 size={16}/>} {saved ? 'Saved' : 'Save'}
          </button>
        </div>
      </footer>
    </div>
  </div>
}
