import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, API_BASE, type AgentEvent, type Approval, type Board, type Cash, type Draft, type Run } from './api'
import { money, TICKET_TYPE } from './agents'
import { TicketList } from './components/TicketList'
import { AgentStage } from './components/AgentStage'
import { Feed } from './components/Feed'
import { Summary } from './components/Summary'
import { ApprovalQueue, CashCard } from './components/SidePanels'

const FAST = 1500 // poll while the agents are working
const SLOW = 6000 // poll while idle

function loadApprover() {
  try {
    return localStorage.getItem('cc_approver') ?? ''
  } catch {
    return ''
  }
}

export default function App() {
  const [board, setBoard] = useState<Board | null>(null)
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [approver, setApproverState] = useState(loadApprover)
  const [toast, setToast] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [flash, setFlash] = useState(false)
  const [online, setOnline] = useState(true)
  const selectedRef = useRef<number | null>(null)
  selectedRef.current = selectedId

  const activeRun = runs.find((r) => r.status === 'running') ?? null

  const say = (text: string, kind: 'ok' | 'err' = 'ok') => {
    setToast({ text, kind })
    window.setTimeout(() => setToast(null), 5000)
  }

  const setApprover = (s: string) => {
    setApproverState(s)
    try {
      localStorage.setItem('cc_approver', s)
    } catch {
      /* private mode: fine */
    }
  }

  const refresh = useCallback(async () => {
    try {
      const [b, c, a, r] = await Promise.all([api.tickets(), api.cash(), api.approvals(), api.runs()])
      setBoard(b)
      setCash((prev) => {
        if (prev && c.balance < prev.balance) {
          setFlash(true)
          window.setTimeout(() => setFlash(false), 1600)
        }
        return c
      })
      setApprovals(a.approvals)
      setRuns(r)
      setOnline(true)
      // First load: open the ticket the team is working on, else #ticket-N from the URL, else the first.
      const live = r.find((x) => x.status === 'running')?.ticket_id
      const fromHash = Number(window.location.hash.match(/ticket-(\d+)/)?.[1]) || null
      const sel = selectedRef.current ?? live ?? fromHash ?? b.tickets[0]?.id ?? null
      if (selectedRef.current === null && sel !== null) {
        selectedRef.current = sel
        setSelectedId(sel)
      }
      if (sel !== null) {
        const [ev, dr] = await Promise.all([api.events({ ticket_id: sel }), api.drafts(sel)])
        setEvents(ev.events)
        setDrafts(dr.drafts)
      }
    } catch {
      setOnline(false)
    }
  }, [])

  // Poll: fast while a run is live, slow otherwise.
  useEffect(() => {
    refresh()
    const id = window.setInterval(refresh, activeRun ? FAST : SLOW)
    return () => window.clearInterval(id)
  }, [refresh, activeRun?.run_id])

  // Follow #ticket-N links (back/forward or a pasted link) without a page reload.
  useEffect(() => {
    const onHash = () => {
      const id = Number(window.location.hash.match(/ticket-(\d+)/)?.[1])
      if (id && id !== selectedRef.current) setSelectedId(id)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    if (selectedId !== null) {
      try {
        history.replaceState(null, '', `#ticket-${selectedId}`)
      } catch {
        /* ignore */
      }
    }
    refresh()
  }, [selectedId, refresh])

  // Show only the latest run for the selected ticket.
  const runId = useMemo(() => (events.length ? events[events.length - 1].run_id : null), [events])
  const runEvents = useMemo(() => events.filter((e) => e.run_id === runId), [events, runId])
  const thisRun = runs.find((r) => r.run_id === runId) ?? null
  const running = !!activeRun && activeRun.ticket_id === selectedId
  const selected = board?.tickets.find((t) => t.id === selectedId) ?? null
  const finished = runs.filter((r) => r.status === 'done' && r.ticket_id === selectedId)

  // Tell the person when a run finishes.
  const lastStatus = useRef<Record<string, string>>({})
  useEffect(() => {
    runs.forEach((r) => {
      const prev = lastStatus.current[r.run_id]
      if (prev === 'running' && r.status === 'done') say(`Ticket ${r.ticket_id} resolved by the agent team.`)
      if (prev === 'running' && r.status === 'error') say(`Run on ticket ${r.ticket_id} failed: ${r.error}`, 'err')
      lastStatus.current[r.run_id] = r.status
    })
  }, [runs])

  async function runTeam(id: number) {
    setSelectedId(id)
    try {
      await api.runTeam(id)
      say(`Agent team started on ticket ${id}.`)
      refresh()
    } catch (e) {
      say((e as Error).message, 'err')
    }
  }

  async function decide(a: Approval, approve: boolean) {
    try {
      if (approve) {
        const r = await api.approve(a.id, approver.trim())
        say(
          r.payment
            ? `Paid ${money(r.payment.paid)} to ${a.payee}. Checking is now ${money(r.payment.balance_after)}.`
            : `Approved #${a.id}. No money moves for a discount.`,
        )
      } else {
        await api.reject(a.id, approver.trim())
        say(`Rejected request #${a.id}.`)
      }
    } catch (e) {
      say((e as Error).message, 'err')
    }
    refresh()
  }

  async function reset() {
    if (!window.confirm('Reset the shop database to the original values? Approvals, drafts and payments will be cleared.')) return
    try {
      const r = await api.reset()
      say(`Database reset. Checking back to ${money(r.checking)}.`)
      refresh()
    } catch (e) {
      say((e as Error).message, 'err')
    }
  }

  const type = selected ? TICKET_TYPE[selected.type] : null

  return (
    <div className="desk">
      <header className="topbar">
        <div className="brand">
          <div className="logo">CC</div>
          <div>
            <div className="brand-name">Campus Customs</div>
            <div className="brand-sub">Operations Desk · Chapel Street</div>
          </div>
        </div>
        <div className="top-stats">
          <div className="stat">
            <span>Shop date</span>
            <b>{board?.date_today ?? '…'}</b>
          </div>
          <div className="stat">
            <span>Open / resolved</span>
            <b>
              {board?.open ?? '–'} / {board?.resolved ?? '–'}
            </b>
          </div>
          <div className="stat">
            <span>Checking</span>
            <b className={flash ? 'drop' : ''}>{cash ? money(cash.balance) : '…'}</b>
          </div>
          <div className="stat model">
            <span>Model</span>
            <b>gpt-6-luna</b>
          </div>
          <button className="btn btn-ghost light" onClick={reset} disabled={!!activeRun}>
            ↺ Reset data
          </button>
        </div>
      </header>

      {!online && (
        <div className="offline">
          Can't reach the backend at <code>{API_BASE}</code>. Start it in backend/ with{' '}
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <main className="grid">
        <aside className="col-left">
          <div className="col-title">Ticket board</div>
          {board && (
            <TicketList
              tickets={board.tickets}
              selectedId={selectedId}
              busyTicket={activeRun?.ticket_id ?? null}
              onSelect={setSelectedId}
              onRun={runTeam}
            />
          )}
        </aside>

        <section className="col-main">
          {selected && (
            <div className="focus-head">
              <div>
                <div className="eyebrow">
                  {type?.icon} {type?.label} · ticket #{selected.id}
                </div>
                <h1>{selected.subject}</h1>
                <p className="muted">
                  From <b>{selected.requester}</b>: {selected.notes?.split('\n')[0]}
                </p>
              </div>
              <div className="run-meta">
                {running && <span className="live">● LIVE</span>}
                {thisRun?.tokens != null && (
                  <span>
                    {thisRun.tokens.toLocaleString()} tokens · {thisRun.tool_calls} tool calls
                  </span>
                )}
                {runId && <span className="mono">run {runId}</span>}
              </div>
            </div>
          )}

          <AgentStage events={runEvents} running={running} />

          <div className="main-split">
            <div className="feed-wrap">
              <div className="col-title">Agent conversation</div>
              <Feed events={runEvents} running={running} />
            </div>
          </div>

          {!running && runEvents.length > 0 && (
            <div className="summary-wrap">
              <div className="col-title">What each agent did</div>
              <Summary
                events={runEvents}
                decision={thisRun?.decision ?? finished[finished.length - 1]?.decision ?? null}
                drafts={drafts}
              />
            </div>
          )}
        </section>

        <aside className="col-right">
          <CashCard cash={cash} approvals={approvals} flash={flash} />
          <ApprovalQueue
            approvals={approvals}
            approver={approver}
            setApprover={setApprover}
            onDecide={decide}
            cash={cash}
          />
        </aside>
      </main>

      {toast && <div className={`toast toast-${toast.kind}`}>{toast.text}</div>}
    </div>
  )
}
