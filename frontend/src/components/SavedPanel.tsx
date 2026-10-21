import {useState} from 'react'
import {BarChart3, Database, Layers3, RefreshCw, Search, Sparkles, Trash2} from 'lucide-react'
import type {Saved} from '../types'

type Props = {
  saved: Saved[]
  loading: boolean
  onOpen: (item: Saved) => void
  onRefresh: (item: Saved) => void
  onDelete: (item: Saved) => void
  onExplore: () => void
}

export function SavedPanel({saved, loading, onOpen, onRefresh, onDelete, onExplore}: Props) {
  const [query, setQuery] = useState('')
  const needle = query.trim().toLowerCase()
  const items = saved.filter(s => !needle || [s.result.ui.title, s.question, s.result.provider.name]
    .some(text => text.toLowerCase().includes(needle)))

  return <div className="content">
    <span className="pill"><Layers3 size={14}/> Saved explorations</span>
    <h1>Saved <em>Dashboards.</em></h1>
    <p className="tagline">Your previous explorations, saved locally in this browser.</p>

    {saved.length > 0 && <label className="search-field">
      <Search size={17}/>
      <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search by title, question or provider" type="search"/>
    </label>}

    {!saved.length && <div className="empty">
      <div className="empty-icon"><Layers3 size={26}/></div>
      <b>No saved dashboards yet</b>
      <small>Ask a question, then press <em>Save</em> on the result to keep it here.</small>
      <button className="primary-btn" onClick={onExplore}><Sparkles size={16}/> Start exploring</button>
    </div>}

    {saved.length > 0 && !items.length && <p className="muted">No saved dashboards match “{query}”.</p>}

    <div className="saved-list">
      {items.map(item => <article className="saved-item" key={item.question}>
        <button className="saved-open" onClick={() => onOpen(item)}>
          <span className="saved-icon"><BarChart3 size={21}/></span>
          <span className="saved-text">
            <b>{item.result.ui.title}</b>
            <small>{item.question}</small>
            <span className="saved-meta">
              <span><Database size={12}/> {item.result.provider.name}</span>
              <span>{item.result.ui.blocks.length} blocks</span>
              <span>{new Date(item.date).toLocaleDateString(undefined, {dateStyle: 'medium'})}</span>
            </span>
          </span>
        </button>
        <div className="saved-actions">
          <button className="icon-btn" onClick={() => onRefresh(item)} disabled={loading} aria-label={`Refresh “${item.result.ui.title}” with live data`} title="Refresh with live data"><RefreshCw size={17}/></button>
          <button className="icon-btn danger" onClick={() => onDelete(item)} aria-label={`Delete “${item.result.ui.title}”`} title="Delete"><Trash2 size={17}/></button>
        </div>
      </article>)}
    </div>
  </div>
}
