import {CheckCircle2, X} from 'lucide-react'

export type ToastState = {id: number; message: string; action?: {label: string; run: () => void}}

export function Toast({toast, onClose}: {toast: ToastState | null; onClose: () => void}) {
  if (!toast) return null
  return <div className="toast" role="status" key={toast.id}>
    <CheckCircle2 size={17}/>
    <span>{toast.message}</span>
    {toast.action && <button className="toast-action" onClick={() => { toast.action?.run(); onClose() }}>{toast.action.label}</button>}
    <button className="icon-btn" onClick={onClose} aria-label="Dismiss notification"><X size={15}/></button>
  </div>
}
