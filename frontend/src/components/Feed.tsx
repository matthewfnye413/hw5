import { useEffect, useRef } from 'react'
import type { AgentEvent } from '../api'
import { AGENT } from '../agents'

function argText(args: unknown): string {
  if (!args || typeof args !== 'object') return ''
  const parts = Object.entries(args as Record<string, unknown>)
    .filter(([k]) => !['reason', 'requested_by', 'note', 'body', 'updated_by', 'drafted_by', 'task'].includes(k))
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
  return parts.join(', ')
}

function time(ts: string) {
  return ts.slice(11, 19)
}

/** Live conversation of the agent team: who said what, and which MCP tools they called. */
export function Feed({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  // Keep the newest message in view by scrolling the feed box itself, never the whole page.
  useEffect(() => {
    if (running && box.current) box.current.scrollTo({ top: box.current.scrollHeight, behavior: 'smooth' })
  }, [events.length, running])

  if (events.length === 0) {
    return (
      <div className="feed empty">
        <p>No agent activity yet. Pick a ticket and press <b>Run agent team</b>.</p>
      </div>
    )
  }

  return (
    <div className="feed" ref={box}>
      {events.map((e) => {
        const a = AGENT[e.agent]
        const isFinal = e.stop_reason === 'final_answer'
        const isTask = e.node === 'UserPrompt'
        const delegations = e.tools.filter((t) => t.tool === 'delegate')
        const otherTools = e.tools.filter((t) => t.tool !== 'delegate')
        return (
          <div
            key={e.index}
            className={`msg ${isFinal ? 'final' : ''} ${isTask ? 'task' : ''}`}
            style={{ '--c': a.color, marginLeft: `${e.depth * 22}px` } as React.CSSProperties}
          >
            <div className="avatar">{a.initials}</div>
            <div className="msg-body">
              <div className="msg-head">
                <b>{a.label}</b>
                {e.called_by && isTask && <span className="from">asked by {AGENT[e.called_by].label}</span>}
                {isFinal && <span className="tag tag-final">✓ final report</span>}
                <span className="when">{time(e.timestamp)}</span>
              </div>
              {delegations.map((d, i) => {
                const args = (d.args ?? {}) as { to?: string; task?: string }
                const to = args.to ? AGENT[args.to as keyof typeof AGENT] : null
                return (
                  <div key={i} className="delegation" style={{ '--c2': to?.color ?? '#555' } as React.CSSProperties}>
                    <span className="arrow-pill">→ {to?.label ?? args.to}</span>
                    <span>{args.task}</span>
                  </div>
                )
              })}
              {e.said && delegations.length === 0 && (
                <p className={isTask ? 'said task-text' : 'said'}>{isTask ? e.said.replace(/^Got task: /, '') : e.said}</p>
              )}
              {otherTools.length > 0 && (
                <div className="tools">
                  {otherTools.map((t, i) => (
                    <span key={i} className="tool-chip" title={argText(t.args)}>
                      <code>{t.tool}</code>
                      {argText(t.args) && <span className="tool-args">{argText(t.args)}</span>}
                    </span>
                  ))}
                </div>
              )}
              {!e.said && otherTools.length === 0 && delegations.length === 0 && <p className="said muted">thinking…</p>}
            </div>
          </div>
        )
      })}
      {running && (
        <div className="typing">
          <span />
          <span />
          <span />
        </div>
      )}
    </div>
  )
}
