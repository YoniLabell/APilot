import { useEffect, useState, type FormEvent } from 'react'
import { Activity, ArrowLeft, BarChart3, BookOpen, CheckCircle2, ChevronLeft, CloudRain,
  Code2, Copy, Database, ExternalLink, FileJson, Globe2, KeyRound, Layers3,
  LoaderCircle, Lock, Menu, Rocket, Search, ShieldCheck, Shuffle, Sparkles, Terminal, X } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type TEvent = {stage:string;message:string;detail?:string}
type Stats = {type:'stats';title:string;items:{label:string;value:string}[]}
type Chart = {type:'chart';title:string;chartType:'line'|'bar';xKey:string;series:{key:string;label:string}[];data:Record<string,string|number>[]}
type Table = {type:'table';title:string;columns:string[];rows:string[][]}
type TextBlock = {type:'text';title:string;content:string}
type Block = Stats|Chart|Table|TextBlock
type Answer = {ui:{title:string;subtitle:string;summary:string;caveat:string;blocks:Block[]};
  provider:{name:string;url:string;description:string;category:string};source_url:string;trace:TEvent[];
  raw_excerpt:string;retrieved_at:string}
type Saved = {question:string;result:Answer;date:string}
const EXAMPLES = [
  {icon:CloudRain,label:'Weather',q:'How much rain fell in Mexico City yesterday?'},
  {icon:Activity,label:'Science',q:'What were the strongest earthquakes worldwide last week?'},
  {icon:Globe2,label:'World Data',q:'Compare the populations of Japan, India and Brazil'},
  {icon:BookOpen,label:'Books',q:'Find Isaac Asimov books and show their publication years'},
]
const COLORS = ['#9b8cff','#41d6c2','#e7a7ff','#ffc77b']
async function api(url:string, options?:RequestInit) {
  const resp=await fetch(url,options)
  const result=await resp.json().catch(()=>({}))
  if(!resp.ok) throw Error(typeof result.detail==='string'?result.detail:`Request failed (${resp.status})`)
  return result
}
function RenderBlock({block}:{block:Block}) {
  if(block.type==='stats')return <section className="block"><h3>{block.title}</h3><div className="stats">{block.items.map((item,i)=><div className="stat" key={i}><small>{item.label}</small><strong dir="auto">{item.value}</strong></div>)}</div></section>
  if(block.type==='chart') {
    const ChartComponent=block.chartType==='line'?LineChart:BarChart
    return <section className="block"><h3>{block.title}</h3><div dir="ltr" className="chart">
      <ResponsiveContainer width="100%" height={260}><ChartComponent data={block.data} margin={{top:10,left:-20,right:10,bottom:4}}>
        <CartesianGrid stroke="#28344a" strokeDasharray="4 7" vertical={false}/>
        <XAxis dataKey={block.xKey} tick={{fill:'#91a0ba',fontSize:11}} tickLine={false} axisLine={false}/>
        <YAxis tick={{fill:'#91a0ba',fontSize:11}} tickLine={false} axisLine={false}/>
        <Tooltip contentStyle={{background:'#1e293b',border:'1px solid #42516b',color:'#fff',borderRadius:10}}/>
        <Legend/>{block.series.map((s,i)=>block.chartType==='line'?<Line key={i} name={s.label} type="monotone" dataKey={s.key} stroke={COLORS[i%COLORS.length]} strokeWidth={3}/>:
          <Bar key={i} name={s.label} dataKey={s.key} fill={COLORS[i%COLORS.length]} radius={[5,5,0,0]}/>)}</ChartComponent></ResponsiveContainer>
    </div></section>
  }
  if(block.type==='table')return <section className="block"><h3>{block.title}</h3><div className="table-wrap"><table><thead><tr>{block.columns.map((h,i)=><th key={i}>{h}</th>)}</tr></thead><tbody>{block.rows.map((r,i)=><tr key={i}>{r.map((v,j)=><td dir="auto" key={j}>{v}</td>)}</tr>)}</tbody></table></div></section>
  if(block.type==='text')return <section className="block"><h3>{block.title}</h3><p className="block-text">{block.content}</p></section>
  return null
}
function ResultPopup({answer,question,onClose,onSave,onRefresh,alreadySaved}:{answer:Answer;question:string;onClose:()=>void;onSave:()=>void;onRefresh:()=>void;alreadySaved:boolean}){
  const [tab,setTab]=useState<'dashboard'|'trace'|'json'>('dashboard')
  return <div className="overlay" onClick={onClose}><div className="popup" onClick={e=>e.stopPropagation()} role="dialog" aria-modal="true">
    <div className="popup-head"><div className="popup-title"><div className="popup-icon"><Sparkles size={23}/></div><div><small>AI GENERATED DASHBOARD</small><h2>{answer.ui.title}</h2></div></div><button className="icon-btn" onClick={onClose} aria-label="Close dashboard"><X size={21}/></button></div>
    <div className="tabs" dir="ltr"><button className={tab==='dashboard'?'active':''} onClick={()=>setTab('dashboard')}><BarChart3 size={16}/> Dashboard</button>
      <button className={tab==='trace'?'active':''} onClick={()=>setTab('trace')}><Terminal size={16}/> Agent X-Ray <i>{answer.trace.length}</i></button>
      <button className={tab==='json'?'active':''} onClick={()=>setTab('json')}><FileJson size={16}/> Raw JSON</button></div>
    <div className="popup-body">{tab==='dashboard'?<>
      <span className="source-badge"><CheckCircle2 size={14}/> Real API JSON retrieved</span>
      <p className="question-label">{question}</p><p className="result-summary">{answer.ui.summary}</p>
      {answer.ui.blocks.map((b,i)=><RenderBlock block={b} key={i}/>)}
      {answer.ui.caveat&&<div className="warning"><ShieldCheck size={19}/><span>{answer.ui.caveat}</span></div>}
      <div className="source-link"><Database size={16}/> {answer.provider.name}<a href={answer.source_url} target="_blank" rel="noopener noreferrer">Open actual API request <ExternalLink size={14}/></a></div>
    </>:tab==='trace'?<div className="trace">{answer.trace.map((step,i)=><div className="trace-row" key={i}><div className="trace-num">{i+1}</div><div><small>{step.stage}</small><b>{step.message}</b>{step.detail&&<pre>{step.detail}</pre>}</div></div>)}</div>
    :<div><small>Actual API data excerpt (truncated when large)</small><pre className="raw" dir="ltr">{answer.raw_excerpt}</pre></div>}</div>
    <div className="popup-footer"><small>Fetched: {new Date(answer.retrieved_at).toLocaleString()}</small><div>
      <button className="secondary-btn" onClick={()=>void navigator.clipboard?.writeText(answer.source_url)}><Copy size={15}/> Copy source</button>
      <button className="secondary-btn" onClick={onRefresh}><ArrowLeft size={15}/> Refresh</button>
      <button className="primary-btn" onClick={onSave}>{alreadySaved?<CheckCircle2 size={16}/>:<Layers3 size={16}/>} {alreadySaved?'Saved':'Save'}</button>
    </div></div>
  </div></div>
}
export default function App(){
  const [question,setQuestion]=useState('')
  const [result,setResult]=useState<Answer|null>(null)
  const [answered,setAnswered]=useState('')
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')
  const [key,setKey]=useState(()=>sessionStorage.getItem('apilot-key')||'')
  const [protectedApi,setProtectedApi]=useState(false)
  const [apiCount,setApiCount]=useState<number|null>(null)
  const [panel,setPanel]=useState<'explore'|'saved'>('explore')
  const [menu,setMenu]=useState(false)
  const [saved,setSaved]=useState<Saved[]>(()=>{try{return JSON.parse(localStorage.getItem('apilot-saved')||'[]')}catch{return []}})
  useEffect(()=>{
    void api('/api/health').then(x=>setProtectedApi(Boolean(x.protected))).catch(()=>{})
    void api('/api/catalog/stats').then(x=>setApiCount(Number(x.total))).catch(()=>{})
  },[])
  function setAccess(value:string){setKey(value);sessionStorage.setItem('apilot-key',value)}
  async function ask(text=question,forced_api=''){
    if(loading||text.trim().length<4)return
    setError('');setResult(null);setLoading(true)
    try{
      const response=await api('/api/ask',{method:'POST',headers:{'Content-Type':'application/json','X-APilot-Key':key},body:JSON.stringify({question:text.trim(),forced_api})}) as Answer
      setAnswered(text.trim());setResult(response)
    }catch(e){setError(e instanceof Error?e.message:'Unexpected error')}
    finally{setLoading(false)}
  }
  async function roulette(){
    if(loading)return
    try{
      setError('')
      const pick=await api('/api/roulette',{headers:{'X-APilot-Key':key}}) as {name:string;description:string}
      const prompt=`Show interesting real data from the ${pick.name} API. ${pick.description}`
      setQuestion(prompt);setPanel('explore');void ask(prompt,pick.name)
    }catch(e){setError(e instanceof Error?e.message:'Roulette failed')}
  }
  function saveResult(){if(!result)return;const list=[{question:answered,result,date:new Date().toISOString()},...saved.filter(s=>s.question!==answered)].slice(0,12);setSaved(list);localStorage.setItem('apilot-saved',JSON.stringify(list))}
  const alreadySaved=saved.some(s=>s.question===answered)
  return <div className="shell" dir="ltr">
    <aside className={menu?'sidebar sidebar-open':'sidebar'}>
      <div className="brand"><div className="brand-mark"><Rocket size={23}/></div><span>APilot<span className="dot">.</span><small>AI API EXPLORER</small></span></div>
      <small className="menu-label">WORKSPACE</small><nav>
        <button className={panel==='explore'?'nav-active':''} onClick={()=>{setPanel('explore');setMenu(false)}}><Search size={18}/> Explore APIs <ChevronLeft size={16}/> </button>
        <button onClick={()=>{setMenu(false);void roulette()}}><Shuffle size={18}/> API Roulette</button>
        <button className={panel==='saved'?'nav-active':''} onClick={()=>{setPanel('saved');setMenu(false)}}><Layers3 size={18}/> Saved Dashboards <span className="count">{saved.length}</span></button>
      </nav><small className="menu-label">PROJECT</small><nav>
        <a href="https://github.com/YoniLabell/APilot" target="_blank" rel="noopener noreferrer"><Code2 size={18}/> GitHub repo <ExternalLink size={15}/></a>
        <a href="https://github.com/public-apis/public-apis" target="_blank" rel="noopener noreferrer"><BookOpen size={18}/> API Directory <ExternalLink size={15}/></a>
      </nav><div className="sidebar-foot"><span className="online"/> {apiCount?`${apiCount.toLocaleString()} APIs indexed`:'Loading catalog…'}<small>Powered by OpenAI + Public APIs</small></div>
    </aside>
    <main className="main" dir="ltr">
      <header className="topbar"><button className="mobile-menu icon-btn" onClick={()=>setMenu(!menu)} aria-label="Open navigation menu"><Menu size={20}/></button><span className="breadcrumbs">WORKSPACE / <b>{panel==='explore'?'EXPLORE':'SAVED'}</b></span><div className="status"><span className="online"/> Agent Online</div></header>
      {panel==='explore'?<div className="content"><span className="pill"><Sparkles size={14}/> AUTONOMOUS API DISCOVERY</span>
        <h1>Ask anything.<br/><em>Watch data come alive.</em></h1>
        <p className="tagline">AI discovers public APIs, reads their documentation, fetches live data, and designs an interactive dashboard for your question.</p>
        {protectedApi&&<label className="key-field" dir="ltr"><Lock size={17}/> Render Access Key <input value={key} onChange={e=>setAccess(e.target.value)} type="password" placeholder="APP_ACCESS_KEY from Render"/><KeyRound size={17}/></label>}
        <form className="ask-box" onSubmit={(e:FormEvent)=>{e.preventDefault();void ask()}}><div className="ask-label"><Sparkles size={16}/> Ask a question</div>
          <textarea rows={3} maxLength={700} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="For example: How much did it rain in Mexico City yesterday?" onKeyDown={e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();void ask()}}}/>
          <div className="ask-bottom"><small><ShieldCheck size={15}/> Real data, traceable sources</small><button type="submit" className="primary-btn" disabled={loading||question.trim().length<4}>{loading?<LoaderCircle size={17} className="spin"/>:<Sparkles size={17}/>} {loading?'Exploring…':'Explore data'} <ArrowLeft size={16}/></button></div></form>
        {loading&&<div className="notice"><LoaderCircle size={20} className="spin"/><div><b>Agent is exploring real APIs…</b><small>Discovering sources, reading docs, fetching data and designing UI. This can take several requests.</small></div></div>}
        {error&&<div className="notice err"><ShieldCheck size={21}/><div><b>Could not complete this request</b><small>{error}</small></div><button className="icon-btn" onClick={()=>setError('')}><X size={18}/></button></div>}
        <div className="inspire"><div><small>GET INSPIRED</small><h2>Not sure what to explore?</h2></div><button onClick={()=>void roulette()}><Shuffle size={17}/> Surprise me <ChevronLeft size={15}/></button></div>
        <div className="suggestions">{EXAMPLES.map(item=><button key={item.label} className="suggestion" onClick={()=>setQuestion(item.q)}><span className="suggestion-icon"><item.icon size={21}/></span><h3>{item.q}</h3><small>{item.label} <ArrowLeft size={13}/></small></button>)}</div>
        <div className="learning"><Terminal size={21}/><div><b>Developer mode built-in</b><small>Inspect every provider choice, HTTP URL, response and fallback in Agent X-Ray.</small></div><FileJson size={21}/></div>
      </div>:<div className="content"><span className="pill"><Layers3 size={14}/> SAVED EXPLORATIONS</span><h1>Saved <em>Dashboards.</em></h1><p className="tagline">Your previous explorations, saved locally in this browser.</p><div className="saved-list">{saved.length?saved.map((s,i)=><button className="saved-item" key={i} onClick={()=>{setResult(s.result);setAnswered(s.question)}}><BarChart3 size={23}/><b>{s.result.ui.title}</b><small>{s.question}</small><span>{new Date(s.date).toLocaleDateString()}</span></button>):<p>No saved dashboards yet. Start by asking a question!</p>}</div></div>}
    </main>
    {result&&<ResultPopup key={result.retrieved_at+answered} answer={result} question={answered} onClose={()=>setResult(null)} onSave={saveResult} onRefresh={()=>{setQuestion(answered);setResult(null);void ask(answered)}} alreadySaved={alreadySaved}/>}
  </div>
}
