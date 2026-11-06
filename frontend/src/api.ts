// Typed calls to the FastAPI routes from Problem 7 (backend/main.py).

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  state: 'open' | 'resolved'
  notes: string | null
  created_at: string
  agent_run: string | null
}

export interface Board {
  date_today: string
  tickets: Ticket[]
  open: number
  resolved: number
}

export interface AgentEvent {
  index: number
  run_id: string
  ticket_id: number | null
  agent: AgentName
  called_by: AgentName | null
  depth: number
  step: number
  node: string
  timestamp: string
  said: string | null
  tools: { tool: string; args: Record<string, unknown> | string | null }[]
  stop_reason: string | null
  tokens_so_far: number | null
}

export interface Decision {
  ticket_id: number
  assigned_agents: AgentName[]
  decision: string
  final_status: string
  approvals_pending: number[]
  customer_draft_ids: number[]
  cash_impact: number
  next_steps: string[]
}

export interface Run {
  run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'error'
  model: string
  started_at: string
  finished_at: string | null
  decision: Decision | null
  tokens: number | null
  requests: number | null
  tool_calls: number | null
  error: string | null
  boss_status?: string
}

export interface Approval {
  id: number
  ticket_id: number | null
  kind: 'invoice' | 'rent' | 'purchase_order' | 'discount'
  ref_id: number | null
  payee: string
  amount: number
  details: Record<string, unknown> | null
  reason: string
  requested_by: string
  status: 'pending' | 'approved' | 'rejected' | 'paid'
  decided_by: string | null
  decided_at: string | null
  created_at: string
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  date_today: string
}

export interface Draft {
  id: number
  ticket_id: number
  to_name: string
  subject: string
  body: string
  drafted_by: string
  status: string
  created_at: string
}

// The backend the board talks to. Set VITE_API_URL in frontend/.env to change it.
export const API_BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body?.detail ?? `${res.status} ${res.statusText}`)
  return body as T
}

export const api = {
  tickets: () => call<Board>('/tickets'),
  runTeam: (id: number) => call<Run>(`/tickets/${id}/run`, { method: 'POST' }),
  runs: () => call<Run[]>('/runs'),
  run: (runId: string) => call<Run>(`/runs/${runId}`),
  events: (q: { since?: number; ticket_id?: number; run_id?: string }) => {
    const p = new URLSearchParams()
    if (q.since) p.set('since', String(q.since))
    if (q.ticket_id != null) p.set('ticket_id', String(q.ticket_id))
    if (q.run_id) p.set('run_id', q.run_id)
    p.set('limit', '1000')
    p.set('current', 'true') // only activity since the last database reset
    return call<{ events: AgentEvent[]; next_since: number; total: number }>(`/events?${p}`)
  },
  approvals: () => call<{ approvals: Approval[] }>('/approvals'),
  approve: (id: number, approvedBy: string) =>
    call<{ payment: { paid: number; balance_after: number } | null }>(`/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  reject: (id: number, approvedBy: string) =>
    call(`/approvals/${id}/reject`, { method: 'POST', body: JSON.stringify({ approved_by: approvedBy }) }),
  cash: () => call<Cash>('/cash'),
  drafts: (ticketId: number) => call<{ drafts: Draft[] }>(`/drafts?ticket_id=${ticketId}`),
  reset: () => call<{ checking: number }>('/reset', { method: 'POST' }),
}
