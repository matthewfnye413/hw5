import type { AgentEvent, AgentName, Decision, Draft } from '../api'
import { AGENT, AGENTS, money } from '../agents'

interface Props {
  events: AgentEvent[]
  decision: Decision | null
  drafts: Draft[]
}

/** "What each agent did on this ticket": built from the run's events. */
export function Summary({ events, decision, drafts }: Props) {
  if (events.length === 0) return null
  const byAgent = new Map<AgentName, AgentEvent[]>()
  events.forEach((e) => byAgent.set(e.agent, [...(byAgent.get(e.agent) ?? []), e]))

  return (
    <div className="summary">
      {decision && (
        <div className="decision">
          <div className="decision-head">
            <span className="avatar" style={{ '--c': AGENT.boss.color } as React.CSSProperties}>
              BO
            </span>
            <div>
              <div className="eyebrow">Boss's final call</div>
              <div className="decision-status">
                Boss set <code>{decision.final_status}</code>
                {decision.cash_impact > 0 && <> · cash at stake {money(decision.cash_impact)}</>}
              </div>
            </div>
          </div>
          <p>{decision.decision}</p>
          {decision.next_steps.length > 0 && (
            <ul className="next">
              {decision.next_steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="agent-cards">
        {AGENTS.filter((a) => byAgent.has(a.name)).map((a) => {
          const evs = byAgent.get(a.name)!
          const tools = [...new Set(evs.flatMap((e) => e.tools.map((t) => t.tool)).filter((t) => t !== 'delegate'))]
          const asked = [
            ...new Set(
              evs.flatMap((e) =>
                e.tools.filter((t) => t.tool === 'delegate').map((t) => (t.args as { to?: string })?.to ?? '?'),
              ),
            ),
          ]
          const finals = evs.filter((e) => e.stop_reason === 'final_answer' && e.said)
          const last = finals[finals.length - 1]?.said
          return (
            <div key={a.name} className="agent-card" style={{ '--c': a.color } as React.CSSProperties}>
              <div className="agent-card-head">
                <span className="avatar">{a.initials}</span>
                <b>{a.label}</b>
                <span className="count">{finals.length > 1 ? `${finals.length} tasks` : '1 task'}</span>
              </div>
              {last && <p>{last}</p>}
              {asked.length > 0 && (
                <div className="mini">
                  Asked: {asked.map((t) => AGENT[t as AgentName]?.label ?? t).join(', ')}
                </div>
              )}
              {tools.length > 0 && (
                <div className="tools">
                  {tools.map((t) => (
                    <span key={t} className="tool-chip small">
                      <code>{t}</code>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {drafts.length > 0 && (
        <div className="drafts">
          {drafts.map((d) => (
            <div key={d.id} className="draft-card">
              <div className="draft-head">
                <span className="tag tag-draft">Draft #{d.id}, not sent</span>
                <span>
                  To <b>{d.to_name}</b>: {d.subject}
                </span>
              </div>
              <pre>{d.body}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
