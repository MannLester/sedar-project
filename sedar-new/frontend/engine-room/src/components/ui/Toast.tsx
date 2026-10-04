import { CheckCircle2, X } from 'lucide-react'

interface ToastProps { message: string; onClose: () => void }

export function Toast({ message, onClose }: ToastProps) {
  return <div className="toast" role="status"><CheckCircle2 size={17} /><span>{message}</span><button type="button" aria-label="Dismiss notification" onClick={onClose}><X size={15} /></button></div>
}
