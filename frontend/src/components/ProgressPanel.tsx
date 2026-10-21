import {useEffect, useRef, useState} from 'react'
import {Check, CircleStop, Clock, Info} from 'lucide-react'
import type {Progress} from '../types'
import {formatElapsed} from '../lib/format'
import {currentProvider, estimatedStage, liveStage, STAGE_TONE, STAGES} from '../lib/stages'

export function ProgressPanel({progress, onCancel}: {progress: Progress; onCancel: () => void}) {
  const [now, setNow] = useState(Date.now())
  const feed = useRef<HTMLOListElement>(null)
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(timer)
  }, [])
  useEffect(() => {
    feed.current?.scrollTo({top: feed.current.scrollHeight, behavior: 'smooth'})
  }, [progress.events.length])

  const elapsed = (now - progress.startedAt) / 1000
  const live = progress.mode === 'live'
  const stage = Math.min(live ? liveStage(progress.events) : estimatedStage(elapsed), STAGES.length - 1)
  const provider = currentProvider(progress.events)
  const attempts = new Set(progress.events.filter(e => e.stage === 'DOCUMENTATION').map(e => e.message)).size
  const percent = Math.round(((stage + 0.5) / STAGES.length) * 100)

  return <section className="progress" aria-live="polite" aria-busy="true">
    <div className="progress-bar"><span style={{width: `${percent}%`}}/></div>
    <header className="progress-head">
      <div>
        <b>{STAGES[stage].hint}…</b>
        <small>
          {provider ? <>Trying <em>{provider}</em>{attempts > 1 ? ` · provider ${attempts} of 3` : ''}</> : 'Agent is exploring real APIs'}
        </small>
      </div>
      <span className="elapsed"><Clock size={14}/> {formatElapsed(elapsed)}</span>
      <button className="secondary-btn" onClick={onCancel}><CircleStop size={15}/> Cancel</button>
    </header>

    <ol className="stepper">
      {STAGES.map(({label, icon: Icon}, i) => {
        const state = i < stage ? 'done' : i === stage ? 'active' : 'pending'
        return <li key={label} className={`step ${state}`} aria-current={state === 'active' ? 'step' : undefined}>
          <span className="step-dot">{state === 'done' ? <Check size={15}/> : <Icon size={15}/>}</span>
          <span className="step-label">{label}</span>
        </li>
      })}
    </ol>

    {live
      ? <ol className="live-feed" ref={feed}>
          {progress.events.map((event, i) => <li key={i}>
            <span className={`stage-chip tone-${STAGE_TONE[event.stage] ?? 'info'}`}>{event.stage}</span>
            <span className="feed-text">{event.provider && <em className="feed-provider">{event.provider}</em>}{event.message}{event.detail && <code>{event.detail}</code>}</span>
            {event.elapsed !== undefined && <small>{event.elapsed.toFixed(1)}s</small>}
          </li>)}
          {!progress.events.length && <li className="feed-empty">Connecting to the agent…</li>}
        </ol>
      : <p className="progress-note"><Info size={14}/> Live progress isn’t available from this server, so these stages are estimated. The full Agent X-Ray appears with the result.</p>}
  </section>
}
