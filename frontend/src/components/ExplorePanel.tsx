import {useState, type FormEvent} from 'react'
import {Activity, ArrowRight, Banknote, BookOpen, ChevronRight, Eye, EyeOff, FileJson, KeyRound,
  LoaderCircle, ShieldCheck, Shuffle, Sparkles, Star, Terminal, TriangleAlert, X} from 'lucide-react'
import type {Progress} from '../types'
import {ProgressPanel} from './ProgressPanel'

// Each example is pinned to a stable no-auth API (an exact catalog name) so it skips the
// keyword-ranking step, where the right provider can lose a tie to dozens of similar ones.
// All four were verified end to end on the deployed app. Avoid Open-Meteo (the agent builds
// invalid requests) and crypto/SpaceX providers (wrong provider picked, 403s).
const EXAMPLES = [
  {icon: Activity, label: 'Science', api: 'USGS Earthquake Hazards Program', q: 'Which earthquakes of magnitude 5 or more happened worldwide in the past week?'},
  {icon: BookOpen, label: 'Books', api: 'Open Library', q: 'List 10 Isaac Asimov books with their first publication years'},
  {icon: Star, label: 'Developers', api: 'GithubTrends', q: 'What are the 5 most-starred Python repositories on GitHub?'},
  {icon: Banknote, label: 'Finance', api: 'Frankfurter', q: "What is today's US dollar exchange rate against EUR, GBP and JPY?"},
]

type Props = {
  question: string
  setQuestion: (value: string) => void
  accessKey: string
  setAccessKey: (value: string) => void
  protectedApi: boolean
  loading: boolean
  progress: Progress | null
  error: string
  onDismissError: () => void
  onAsk: (text?: string, api?: string) => void
  onCancel: () => void
  onRoulette: () => void
}

export function ExplorePanel(props: Props) {
  const {question, setQuestion, accessKey, setAccessKey, protectedApi, loading, progress, error, onAsk} = props
  const [showKey, setShowKey] = useState(false)
  const ready = question.trim().length >= 4

  return <div className="content">
    <span className="pill"><Sparkles size={14}/> Autonomous API discovery</span>
    <h1>Ask anything.<br/><em>Watch data come alive.</em></h1>
    <p className="tagline">AI discovers public APIs, reads their documentation, fetches live data, and designs an interactive dashboard for your question.</p>

    {protectedApi && <label className="key-field">
      <KeyRound size={17}/>
      <span>Access key</span>
      <input value={accessKey} onChange={e => setAccessKey(e.target.value)} type={showKey ? 'text' : 'password'}
        placeholder="Enter the site access key" autoComplete="current-password"/>
      <button type="button" className="icon-btn" onClick={() => setShowKey(!showKey)} aria-label={showKey ? 'Hide access key' : 'Show access key'}>
        {showKey ? <EyeOff size={16}/> : <Eye size={16}/>}
      </button>
    </label>}

    <form className={loading ? 'ask-box busy' : 'ask-box'} onSubmit={(e: FormEvent) => { e.preventDefault(); onAsk() }}>
      <label className="ask-label" htmlFor="question"><Sparkles size={16}/> Ask a question</label>
      <textarea id="question" rows={3} maxLength={700} value={question} disabled={loading}
        onChange={e => setQuestion(e.target.value)} placeholder="For example: Which earthquakes of magnitude 5 or more happened worldwide in the past week?"
        onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); onAsk() } }}/>
      <div className="ask-bottom">
        <small><ShieldCheck size={15}/> Real data, traceable sources</small>
        <small className="shortcut"><kbd>Ctrl</kbd> + <kbd>Enter</kbd></small>
        <button type="submit" className="primary-btn" disabled={loading || !ready}>
          {loading ? <LoaderCircle size={17} className="spin"/> : <Sparkles size={17}/>}
          {loading ? 'Exploring…' : 'Explore data'}
          {!loading && <ArrowRight size={16}/>}
        </button>
      </div>
    </form>

    {progress && <ProgressPanel progress={progress} onCancel={props.onCancel}/>}

    {error && <div className="notice err" role="alert">
      <TriangleAlert size={20}/>
      <div><b>Could not complete this request</b><small>{error}</small></div>
      <button className="icon-btn" onClick={props.onDismissError} aria-label="Dismiss error"><X size={18}/></button>
    </div>}

    <div className="inspire">
      <div><small>Get inspired</small><h2>Not sure what to explore?</h2></div>
      <button onClick={props.onRoulette} disabled={loading}><Shuffle size={17}/> Surprise me <ChevronRight size={15}/></button>
    </div>
    <div className="suggestions">
      {EXAMPLES.map(item => <button key={item.label} className="suggestion" disabled={loading}
        onClick={() => { setQuestion(item.q); onAsk(item.q, item.api) }}>
        <span className="suggestion-icon"><item.icon size={20}/></span>
        <h3>{item.q}</h3>
        <small><span>{item.label} · {item.api.replace(' Earthquake Hazards Program', '')}</span> <ArrowRight size={14}/></small>
      </button>)}
    </div>

    <div className="learning">
      <Terminal size={21}/>
      <div><b>Developer mode built-in</b><small>Inspect every provider choice, HTTP URL, response and fallback in Agent X-Ray — live while the agent works.</small></div>
      <FileJson size={21}/>
    </div>
  </div>
}
