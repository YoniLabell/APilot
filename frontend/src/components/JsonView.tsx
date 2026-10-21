import {useMemo} from 'react'
import {Copy, Info} from 'lucide-react'

const TOKEN = /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(?:\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g

function highlight(text: string) {
  const parts: React.ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(TOKEN)) {
    const token = match[0]
    const index = match.index ?? 0
    if (index > last) parts.push(text.slice(last, index))
    const kind = token.startsWith('"') ? (token.trimEnd().endsWith(':') ? 'key' : 'str')
      : token === 'null' ? 'null' : token === 'true' || token === 'false' ? 'bool' : 'num'
    parts.push(<span key={index} className={`j-${kind}`}>{token}</span>)
    last = index + token.length
  }
  parts.push(text.slice(last))
  return parts
}

export function JsonView({raw, onCopy}: {raw: string; onCopy: (text: string) => void}) {
  const {text, parsed} = useMemo(() => {
    try {
      return {text: JSON.stringify(JSON.parse(raw), null, 2), parsed: true}
    } catch {
      return {text: raw, parsed: false}
    }
  }, [raw])
  const lines = text.split('\n').length
  return <div className="json-view">
    <div className="json-head">
      <small>{parsed ? `${lines.toLocaleString()} lines · sampled API response` : 'Excerpt was truncated, shown as plain text'}</small>
      <button className="ghost-btn" onClick={() => onCopy(text)}><Copy size={14}/> Copy</button>
    </div>
    {!parsed && <p className="json-note"><Info size={14}/> Large responses are sampled before they reach the agent.</p>}
    <pre className="raw" dir="ltr">{parsed ? highlight(text) : text}</pre>
  </div>
}
