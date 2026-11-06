import type { AgentEvent, AgentName } from '../api'
import { AGENTS } from '../agents'

interface Props {
  events: AgentEvent[]
  running: boolean
}

/** The five agents across the top of the desk. The one currently speaking glows while a run is live. */
export function AgentStage({ events, running }: Props) {
  const involved = new Set<AgentName>(events.map((e) => e.agent))
  const last = events[events.length - 1]
  const active = running && last ? last.agent : null
  const handoffs = events
    .flatMap((e) =>
      e.tools
        .filter((t) => t.tool === 'delegate' && typeof t.args === 'object' && t.args)
        .map((t) => `${e.agent}→${(t.args as { to?: string }).to}`),
    )
    .filter((v, i, a) => a.indexOf(v) === i)

  return (
    <div className="stage">
      <div className="stage-row">
        {AGENTS.map((a) => {
          const state = active === a.name ? 'active' : involved.has(a.name) ? 'involved' : 'idle'
          return (
            <div key={a.name} className={`stage-agent ${state}`} style={{ '--c': a.color } as React.CSSProperties}>
              <div className="avatar big">{a.initials}</div>
              <div className="stage-name">{a.label}</div>
              <div className="stage-role">{a.role}</div>
              <div className="stage-state">
                {state === 'active' ? 'working…' : state === 'involved' ? 'on this ticket' : 'not called'}
              </div>
            </div>
          )
        })}
      </div>
      {handoffs.length > 0 && (
        <div className="handoffs">
          <span>Hand-offs:</span>
          {handoffs.map((h) => (
            <span key={h} className="handoff">
              {h.replace('customer_service', 'customer service').replace('→', ' → ')}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
