import { useState } from 'react'
import type { Approval, Cash } from '../api'
import { money } from '../agents'

const KIND: Record<Approval['kind'], { label: string; icon: string }> = {
  invoice: { label: 'Pay vendor invoice', icon: '🧾' },
  rent: { label: 'Pay rent', icon: '🏠' },
  purchase_order: { label: 'Purchase order', icon: '📦' },
  discount: { label: 'Approve discount', icon: '🏷️' },
}

export function CashCard({ cash, approvals, flash }: { cash: Cash | null; approvals: Approval[]; flash: boolean }) {
  const paid = approvals.filter((a) => a.status === 'paid')
  const spent = paid.reduce((s, a) => s + a.amount, 0)
  const start = (cash?.balance ?? 0) + spent
  const pct = start > 0 ? Math.max(0, Math.min(100, ((cash?.balance ?? 0) / start) * 100)) : 100
  return (
    <section className={`panel cash ${flash ? 'flash' : ''}`}>
      <div className="eyebrow">Checking balance</div>
      <div className="balance">{cash ? money(cash.balance) : '…'}</div>
      <div className="bar">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="cash-sub">
        as of {cash?.as_of ?? '…'} · money only goes out
        {spent > 0 && <> · spent {money(spent)} of {money(start)}</>}
      </div>
      {paid.length > 0 && (
        <ul className="ledger">
          {paid.map((a) => (
            <li key={a.id}>
              <span>
                {KIND[a.kind].icon} {a.payee}
              </span>
              <span className="neg">−{money(a.amount)}</span>
              <span className="who">approved by {a.decided_by}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

interface ApprovalProps {
  approvals: Approval[]
  approver: string
  setApprover: (s: string) => void
  onDecide: (a: Approval, approve: boolean) => Promise<void>
  cash: Cash | null
}

export function ApprovalQueue({ approvals, approver, setApprover, onDecide, cash }: ApprovalProps) {
  const [busy, setBusy] = useState<number | null>(null)
  const pending = approvals.filter((a) => a.status === 'pending')
  const done = approvals.filter((a) => a.status !== 'pending').slice(-4).reverse()
  return (
    <section className="panel approvals">
      <div className="panel-head">
        <h2>Needs your approval</h2>
        <span className={`count-pill ${pending.length ? 'hot' : ''}`}>{pending.length}</span>
      </div>
      <label className="approver">
        <span>Approving as</span>
        <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name" />
      </label>
      {pending.length === 0 && <p className="muted small">Nothing waiting. Agents only prepare payments; you approve them here.</p>}
      {pending.map((a) => {
        const short = a.kind !== 'discount' && cash !== null && cash.balance < a.amount
        return (
          <div key={a.id} className={`approval ${short ? 'short' : ''}`}>
            <div className="approval-top">
              <span className="kind">
                {KIND[a.kind].icon} {KIND[a.kind].label}
              </span>
              <span className="ticket-ref">#{a.id}{a.ticket_id ? ` · ticket ${a.ticket_id}` : ''}</span>
            </div>
            <div className="approval-amount">
              {money(a.amount)} <span>to {a.payee}</span>
            </div>
            <p className="reason">{a.reason}</p>
            <div className="mini">requested by {a.requested_by.replace('_', ' ')}</div>
            {short && <div className="warn">Not enough cash: checking has {money(cash!.balance)}</div>}
            <div className="approval-actions">
              <button
                className="btn btn-approve"
                disabled={busy !== null || approver.trim().length < 2 || short}
                onClick={async () => {
                  setBusy(a.id)
                  await onDecide(a, true)
                  setBusy(null)
                }}
              >
                {busy === a.id ? 'Paying…' : a.kind === 'discount' ? 'Approve' : `Approve & pay`}
              </button>
              <button
                className="btn btn-ghost"
                disabled={busy !== null || approver.trim().length < 2}
                onClick={async () => {
                  setBusy(a.id)
                  await onDecide(a, false)
                  setBusy(null)
                }}
              >
                Reject
              </button>
            </div>
          </div>
        )
      })}
      {done.length > 0 && (
        <div className="history">
          {done.map((a) => (
            <div key={a.id} className={`hist hist-${a.status}`}>
              <span>
                {KIND[a.kind].icon} #{a.id} {money(a.amount)}
              </span>
              <span>
                {a.status} · {a.decided_by}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
