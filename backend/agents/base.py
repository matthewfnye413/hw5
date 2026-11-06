"""Shared builder for the five agents.

Every agent gets:
  * gpt-6-luna (backend/llm.py), the only model allowed
  * its prompt file from backend/prompts/<role>.md
  * its filtered view of the campus-customs MCP server (backend/mcp_tools.py)
  * a `delegate` tool that can reach ANY other agent (full connectivity), with guards
    against loops, runaway depth and runaway token use
"""

from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent, RunContext

from backend.llm import MODEL_SETTINGS, get_model
from backend.mcp_tools import toolset_for
from backend.models import AGENT_NAMES, AgentName, TeamDeps

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


def make_agent(role: AgentName, output_type) -> Agent[TeamDeps, object]:
    agent = Agent(
        get_model(),
        name=role,
        deps_type=TeamDeps,
        output_type=output_type,
        instructions=(PROMPTS / f"{role}.md").read_text(encoding="utf-8"),
        toolsets=[toolset_for(role)],
        model_settings=MODEL_SETTINGS,
        retries=2,
    )

    @agent.instructions
    def run_context(ctx: RunContext[TeamDeps]) -> str:
        chain = " -> ".join(ctx.deps.chain)
        others = ", ".join(a for a in AGENT_NAMES if a != role)
        left = ctx.deps.max_delegations - ctx.deps.delegations_used[0]
        return (
            f"You are the {role} agent. Ticket in focus: {ctx.deps.ticket_id}. "
            f"Delegation chain so far: {chain}. You can delegate to: {others} "
            f"(not to anyone already in the chain). Delegations left for this ticket: {left}."
        )

    @agent.tool
    async def delegate(ctx: RunContext[TeamDeps], to: AgentName, task: str) -> str:
        """Ask another agent to do a specific piece of work and return its report.

        Args:
            to: boss, inventory, accounting, facilities or customer_service.
            task: a specific request with the ids you know (ticket, sku, size, qty,
                invoice_id, lease_id) and what answer you need back.
        """
        from backend.team import run_agent  # imported here to avoid a circular import

        d = ctx.deps
        if to == role:
            return "Refused: you can't delegate to yourself."
        if to in d.chain:
            return f"Refused: {to} is already working on this ({' -> '.join(d.chain)}); avoid loops."
        if len(d.chain) >= d.max_depth:
            return f"Refused: max delegation depth {d.max_depth} reached. Finish with what you have."
        if d.delegations_used[0] >= d.max_delegations:
            return f"Refused: this ticket used all {d.max_delegations} delegations. Finish with what you have."
        d.delegations_used[0] += 1
        try:
            report = await run_agent(to, task, d.child(to), usage=ctx.usage)
        except Exception as exc:  # report the failure to the caller instead of crashing the team
            return f"{to} failed: {type(exc).__name__}: {exc}"
        return report.model_dump_json()

    return agent
