import {useEffect} from 'react'
import {BookOpen, ChevronRight, Code2, ExternalLink, Layers3, Rocket, Search, Shuffle} from 'lucide-react'

export type Panel = 'explore' | 'saved'

type Props = {
  open: boolean
  panel: Panel
  savedCount: number
  catalog: {total: number; categories: number} | null
  onNavigate: (panel: Panel) => void
  onRoulette: () => void
  onClose: () => void
}

export function Sidebar({open, panel, savedCount, catalog, onNavigate, onRoulette, onClose}: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return <>
    {open && <div className="scrim" onClick={onClose} aria-hidden="true"/>}
    <aside className={open ? 'sidebar sidebar-open' : 'sidebar'} aria-label="Main navigation">
      <div className="brand">
        <div className="brand-mark"><Rocket size={22}/></div>
        <span>APilot<span className="dot">.</span><small>AI API Explorer</small></span>
      </div>

      <small className="menu-label">Workspace</small>
      <nav>
        <button className={panel === 'explore' ? 'nav-active' : ''} aria-current={panel === 'explore' ? 'page' : undefined}
          onClick={() => onNavigate('explore')}><Search size={18}/> Explore APIs {panel === 'explore' && <ChevronRight size={16} className="nav-end"/>}</button>
        <button onClick={onRoulette}><Shuffle size={18}/> API Roulette</button>
        <button className={panel === 'saved' ? 'nav-active' : ''} aria-current={panel === 'saved' ? 'page' : undefined}
          onClick={() => onNavigate('saved')}><Layers3 size={18}/> Saved Dashboards <span className="count nav-end">{savedCount}</span></button>
      </nav>

      <small className="menu-label">Project</small>
      <nav>
        <a href="https://github.com/YoniLabell/APilot" target="_blank" rel="noopener noreferrer"><Code2 size={18}/> GitHub repo <ExternalLink size={14} className="nav-end"/></a>
        <a href="https://github.com/public-apis/public-apis" target="_blank" rel="noopener noreferrer"><BookOpen size={18}/> API Directory <ExternalLink size={14} className="nav-end"/></a>
      </nav>

      <div className="sidebar-foot">
        <span className={catalog ? 'online' : 'online pending'}/>
        {catalog ? `${catalog.total.toLocaleString()} APIs indexed` : 'Loading catalog…'}
        {catalog && <small>{catalog.categories} categories · no-auth, HTTPS only</small>}
        <small>Powered by OpenAI + Public APIs</small>
      </div>
    </aside>
  </>
}
