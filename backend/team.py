"""Agent loops for the Campus Customs team.

run_ticket(ticket_id) starts the Boss on one ticket. Any agent can `delegate` to any
other (full connectivity); each delegation is a nested run_agent call. Every step of
every agent's loop is appended to output/audit_trail.json.

Usage (from the project root):
    python -m backend.team --ticket 102
    python -m backend.team --all
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime

from pydantic_ai import CallToolsNode, ModelRequestNode, UserPromptNode
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import RunUsage, UsageLimits
from pydantic_graph import End

from backend import audit
from backend.agents import AGENTS
from backend.llm import MODEL_NAME
from backend.mcp_tools import shop_mcp
from backend.models import AgentName, AuditEntry, TeamDeps, TicketDecision, ToolCallRecord

# Token budget for ONE ticket, shared by the Boss and every agent it delegates to.
TICKET_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=60, total_tokens_limit=250_000)


def _short(value, n: int = 400) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= n else text[: n - 1] + "…"


def _args(part: ToolCallPart):
    try:
        return part.args_as_dict()
    except Exception:
        return _short(part.args)


def _entry(deps: TeamDeps, step: int, node, usage: RunUsage) -> AuditEntry:
    e = AuditEntry(
        run_id=deps.run_id,
        ticket_id=deps.ticket_id,
        agent=deps.me,
        called_by=deps.chain[-2] if len(deps.chain) > 1 else None,
        depth=len(deps.chain) - 1,
        step=step,
        node=type(node).__name__.replace("Node", ""),
        timestamp=datetime.now().isoformat(timespec="seconds"),
        run_total_tokens=usage.total_tokens,
    )
    if isinstance(node, UserPromptNode):
        e.text_preview = _short(node.user_prompt)
    elif isinstance(node, ModelRequestNode):
        e.tool_returns = [
            ToolCallRecord(tool=p.tool_name, result_preview=_short(p.model_response_str()))
            for p in node.request.parts
            if isinstance(p, ToolReturnPart)
        ]
    elif isinstance(node, CallToolsNode):
        resp = node.model_response
        e.model = MODEL_NAME
        e.served_by = resp.model_name
        e.input_tokens = resp.usage.input_tokens
        e.output_tokens = resp.usage.output_tokens
        e.tool_calls = [
            ToolCallRecord(tool=p.tool_name, args=_args(p)) for p in resp.parts if isinstance(p, ToolCallPart)
        ]
        texts = [p.content for p in resp.parts if isinstance(p, TextPart)]
        e.text_preview = _short(" ".join(texts)) if texts else None
        is_final = any(c.tool.startswith("final_result") for c in e.tool_calls) or not e.tool_calls
        e.stop_reason = "final_answer" if is_final else "tool_call"
    elif isinstance(node, End):
        e.node = "End"
        e.stop_reason = "final_answer"
        out = node.data.output
        e.text_preview = _short(out.model_dump() if hasattr(out, "model_dump") else out)
    return e


async def run_agent(name: AgentName, task: str, deps: TeamDeps, usage: RunUsage | None = None):
    """One agent loop: model -> tools -> model ... -> final output. Every step is audited."""
    agent = AGENTS[name]
    usage = usage if usage is not None else RunUsage()
    step = 0
    try:
        async with agent.iter(task, deps=deps, usage=usage, usage_limits=TICKET_LIMITS) as run:
            async for node in run:
                step += 1
                audit.append(_entry(deps, step, node, usage))
            return run.result.output
    except Exception as exc:
        step += 1
        audit.append(
            AuditEntry(
                run_id=deps.run_id, ticket_id=deps.ticket_id, agent=name,
                called_by=deps.chain[-2] if len(deps.chain) > 1 else None, depth=len(deps.chain) - 1,
                step=step, node="Error", timestamp=datetime.now().isoformat(timespec="seconds"),
                run_total_tokens=usage.total_tokens,
                stop_reason="limit" if isinstance(exc, UsageLimitExceeded) else "error",
                error=_short(f"{type(exc).__name__}: {exc}"),
            )
        )
        raise


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


async def run_ticket(ticket_id: int, run_id: str | None = None) -> tuple[TicketDecision, RunUsage]:
    """Have the Boss work one ticket end to end (shared MCP connection and token budget)."""
    deps = TeamDeps(run_id=run_id or new_run_id(), ticket_id=ticket_id, chain=["boss"])
    usage = RunUsage()
    async with shop_mcp:  # one MCP server process for the whole team
        decision = await run_agent(
            "boss",
            f"Work ticket {ticket_id}. Read it, bring in the teammates it needs, make the final call, "
            f"set the ticket status, and return your TicketDecision.",
            deps,
            usage,
        )
    return decision, usage


async def _main() -> None:
    ap = argparse.ArgumentParser(description="Run the Campus Customs agent team on tickets.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ticket", type=int, action="append", help="ticket id (repeatable)")
    g.add_argument("--all", action="store_true", help="every unresolved ticket")
    a = ap.parse_args()
    ids = a.ticket
    if a.all:
        async with shop_mcp:
            board = (await shop_mcp.direct_call_tool("list_open_tickets", {}))
        ids = [t["id"] for t in board["tickets"]]
    for tid in ids:
        decision, usage = await run_ticket(tid)
        print(f"\n=== Ticket {tid} ===")
        print(decision.model_dump_json(indent=2))
        print(f"tokens: {usage.total_tokens}  requests: {usage.requests}  tool calls: {usage.tool_calls}")
    print(f"\naudit entries in output/audit_trail.json: {audit.count()}")


if __name__ == "__main__":
    asyncio.run(_main())
