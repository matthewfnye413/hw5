import type { Ticket } from '../api'
import { TICKET_TYPE } from '../agents'

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  busyTicket: number | null
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  waiting_approval: 'Waiting approval',
  blocked: 'Blocked',
  resolved: 'Resolved',
}

function detail(t: Ticket) {
  if (t.sku) return `${t.qty ?? '?'} × ${t.sku} · size ${t.size}`
  if (t.lease_id) return `Lease #${t.lease_id}`
  if (t.invoice_id) return `Invoice #${t.invoice_id}`
  return ''
}

export function TicketList({ tickets, selectedId, busyTicket, onSelect, onRun }: Props) {
  return (
    <div className="ticket-list">
      {tickets.map((t) => {
        const type = TICKET_TYPE[t.type] ?? { label: t.type, icon: '📄' }
        const running = busyTicket === t.id
        const status = running ? 'running' : t.status
        return (
          <article
            key={t.id}
            className={`ticket ${selectedId === t.id ? 'selected' : ''} ${t.state}`}
            onClick={() => onSelect(t.id)}
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onSelect(t.id)}
          >
            <div className="ticket-top">
              <span className="ticket-icon" aria-hidden>
                {type.icon}
              </span>
              <span className="ticket-id">#{t.id}</span>
              <span className={`badge badge-${status}`}>
                {running ? <span className="dot-pulse" /> : null}
                {running ? 'Agents working' : STATUS_LABEL[t.status] ?? t.status}
              </span>
            </div>
            <h3>{t.subject}</h3>
            <p className="ticket-meta">
              {type.label} · <b>{t.requester}</b>
            </p>
            {detail(t) && <p className="ticket-detail">{detail(t)}</p>}
            <button
              className="btn btn-run"
              disabled={busyTicket !== null}
              onClick={(e) => {
                e.stopPropagation()
                onRun(t.id)
              }}
            >
              {running ? 'Running…' : t.state === 'resolved' ? '↻ Run team again' : '▶ Run agent team'}
            </button>
          </article>
        )
      })}
    </div>
  )
}
