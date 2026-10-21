import {useCallback, useEffect, useRef, useState} from 'react'
import {Menu} from 'lucide-react'
import type {Answer, Failure, Health, Progress, Saved, TEvent} from './types'
import {api, ask as askPlain, AskError, askStream, StreamUnavailable} from './lib/api'
import {local, readJSON, readText, session, write} from './lib/storage'
import {Sidebar, type Panel} from './components/Sidebar'
import {ExplorePanel} from './components/ExplorePanel'
import {SavedPanel} from './components/SavedPanel'
import {ResultModal} from './components/ResultModal'
import {Toast, type ToastState} from './components/Toast'
import {ThemeToggle} from './components/ThemeToggle'
import {useTheme} from './lib/theme'

const SAVED_KEY = 'apilot-saved'
const ACCESS_KEY = 'apilot-key'
const MAX_SAVED = 12

const HEALTH_LABEL: Record<Health, string> = {
  loading: 'Connecting…', ok: 'Agent online', unconfigured: 'OpenAI key missing', offline: 'Server offline',
}

export default function App() {
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<Answer | null>(null)
  const [answered, setAnswered] = useState('')
  const [progress, setProgress] = useState<Progress | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [accessKey, setAccessKeyState] = useState(() => readText(session, ACCESS_KEY))
  const [protectedApi, setProtectedApi] = useState(false)
  const [health, setHealth] = useState<Health>('loading')
  const [catalog, setCatalog] = useState<{total: number; categories: number} | null>(null)
  const [panel, setPanel] = useState<Panel>('explore')
  const [menu, setMenu] = useState(false)
  const [saved, setSaved] = useState<Saved[]>(() => readJSON(local, SAVED_KEY, []))
  const [toast, setToast] = useState<ToastState | null>(null)
  const [theme, setTheme] = useTheme()
  const controller = useRef<AbortController | null>(null)
  const loading = progress !== null

  useEffect(() => {
    api<{openai_configured: boolean; protected: boolean}>('/api/health')
      .then(x => { setProtectedApi(Boolean(x.protected)); setHealth(x.openai_configured ? 'ok' : 'unconfigured') })
      .catch(() => setHealth('offline'))
    api<{total: number; categories: number}>('/api/catalog/stats')
      .then(x => setCatalog({total: Number(x.total), categories: Number(x.categories)}))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), toast.action ? 6000 : 3200)
    return () => clearTimeout(timer)
  }, [toast])

  const notify = useCallback((message: string, action?: ToastState['action']) => setToast({id: Date.now(), message, action}), [])

  function setAccessKey(value: string) {
    setAccessKeyState(value)
    write(session, ACCESS_KEY, value)
  }

  function persist(list: Saved[]) {
    setSaved(list)
    if (!write(local, SAVED_KEY, JSON.stringify(list))) notify('Could not save in this browser’s storage')
  }

  async function ask(text = question, forcedApi = '') {
    const trimmed = text.trim()
    if (loading || trimmed.length < 4) return
    setFailure(null)
    setResult(null)
    setPanel('explore')
    const abort = new AbortController()
    controller.current = abort
    const body = {question: trimmed, forced_api: forcedApi}
    const events: TEvent[] = []  // Kept for Technical details if the question fails.
    setProgress({mode: 'live', events: [], startedAt: Date.now()})
    try {
      let answer: Answer
      try {
        answer = await askStream(body, accessKey, event => {
          events.push(event)
          setProgress(p => p && {...p, events: [...p.events, event]})
        }, abort.signal)
      } catch (e) {
        if (!(e instanceof StreamUnavailable)) throw e
        setProgress(p => p && {...p, mode: 'estimated'})
        answer = await askPlain(body, accessKey, abort.signal)
      }
      setAnswered(trimmed)
      setResult(answer)
    } catch (e) {
      if (abort.signal.aborted) notify('Exploration cancelled')
      else setFailure({
        message: e instanceof Error ? e.message : 'Unexpected error',
        technical: e instanceof AskError ? e.technical : '',
        events, question: trimmed, api: forcedApi,
      })
    } finally {
      controller.current = null
      setProgress(null)
    }
  }

  async function roulette() {
    setMenu(false)
    if (loading) return
    try {
      setFailure(null)
      const pick = await api<{name: string; description: string}>('/api/roulette', {headers: {'X-APilot-Key': accessKey}})
      const prompt = `Show interesting real data from the ${pick.name} API. ${pick.description}`
      setQuestion(prompt)
      void ask(prompt, pick.name)
    } catch (e) {
      setPanel('explore')
      setFailure({message: e instanceof Error ? e.message : 'Roulette failed', technical: '', events: [], question: '', api: ''})
    }
  }

  function saveResult() {
    if (!result) return
    persist([{question: answered, result, date: new Date().toISOString()}, ...saved.filter(s => s.question !== answered)].slice(0, MAX_SAVED))
    notify('Dashboard saved')
  }

  function deleteSaved(item: Saved) {
    const before = saved
    persist(saved.filter(s => s !== item))
    notify(`Deleted “${item.result.ui.title}”`, {label: 'Undo', run: () => persist(before)})
  }

  function refresh(text: string) {
    setQuestion(text)
    setResult(null)
    void ask(text)
  }

  return <div className="shell">
    <Sidebar open={menu} panel={panel} savedCount={saved.length} catalog={catalog}
      onNavigate={p => { setPanel(p); setMenu(false) }} onRoulette={() => void roulette()} onClose={() => setMenu(false)}/>
    <main className="main">
      <header className="topbar">
        <button className="mobile-menu icon-btn" onClick={() => setMenu(!menu)} aria-label="Open navigation menu" aria-expanded={menu}><Menu size={20}/></button>
        <span className="breadcrumbs">Workspace / <b>{panel === 'explore' ? 'Explore' : 'Saved'}</b></span>
        <div className="topbar-end">
          <div className={`status status-${health}`} title={HEALTH_LABEL[health]}><span className="online"/> <span className="status-label">{HEALTH_LABEL[health]}</span></div>
          <ThemeToggle value={theme} onChange={setTheme}/>
        </div>
      </header>
      {panel === 'explore'
        ? <ExplorePanel question={question} setQuestion={setQuestion} accessKey={accessKey} setAccessKey={setAccessKey}
            protectedApi={protectedApi} loading={loading} progress={progress} failure={failure} onDismissError={() => setFailure(null)}
            onRetry={() => failure && void ask(failure.question, failure.api)}
            onAsk={(text, api) => void ask(text, api)} onCancel={() => controller.current?.abort()} onRoulette={() => void roulette()}/>
        : <SavedPanel saved={saved} loading={loading} onOpen={item => { setResult(item.result); setAnswered(item.question) }}
            onRefresh={item => refresh(item.question)} onDelete={deleteSaved} onExplore={() => setPanel('explore')}/>}
      <footer className="site-footer">
        Built by <a href="https://github.com/YoniLabell" target="_blank" rel="noopener noreferrer">Yoni Labell</a>
        <span aria-hidden="true">·</span>
        <a href="https://github.com/YoniLabell/APilot" target="_blank" rel="noopener noreferrer">Source on GitHub</a>
      </footer>
    </main>
    {result && <ResultModal key={result.retrieved_at + answered} answer={result} question={answered}
      saved={saved.some(s => s.question === answered && s.result.retrieved_at === result.retrieved_at)}
      onClose={() => setResult(null)} onSave={saveResult} onRefresh={() => refresh(answered)} notify={notify}/>}
    <Toast toast={toast} onClose={() => setToast(null)}/>
  </div>
}
