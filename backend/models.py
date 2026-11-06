"""Data types for the Campus Customs agent team.

Shop facts never live here. They come from the MCP server over data/campus_customs_new.db.
These types describe what the agents hand to each other, what the Boss decides,
and what goes into the audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

TicketStatus = Literal["open", "in_progress", "waiting_approval", "blocked", "resolved"]


# --------------------------------------------------------------------------- agent outputs


class Fact(BaseModel):
    """One fact an agent relies on, with the MCP tool it came from (no tool = not a fact)."""

    statement: str = Field(description="The fact in plain words, with the exact number/date from the tool.")
    source_tool: str = Field(description="The MCP tool that returned it, e.g. check_stock.")


class AgentReport(BaseModel):
    """What a specialist agent (Inventory, Accounting, Facilities, Customer Service) returns
    to whoever delegated the task to it."""

    agent: AgentName
    summary: str = Field(description="Two or three sentences answering the task.")
    facts: list[Fact] = Field(default_factory=list, description="Facts used, each tied to an MCP tool.")
    actions_taken: list[str] = Field(
        default_factory=list, description="Things written to the database, e.g. 'approval #2 requested'."
    )
    approval_ids: list[int] = Field(default_factory=list, description="Approval requests created or found.")
    draft_ids: list[int] = Field(default_factory=list, description="Customer drafts saved.")
    blockers: list[str] = Field(default_factory=list, description="What stops the work right now.")
    needs_human: bool = Field(False, description="True if a person must approve or decide something.")


class TicketDecision(BaseModel):
    """The Boss's final call on one ticket."""

    ticket_id: int
    assigned_agents: list[AgentName] = Field(description="Agents the Boss brought in, in order.")
    decision: str = Field(description="The final call in two to four sentences, with amounts and dates.")
    final_status: TicketStatus = Field(description="The status the Boss set on the ticket.")
    approvals_pending: list[int] = Field(default_factory=list, description="Approval ids waiting on a human.")
    customer_draft_ids: list[int] = Field(default_factory=list)
    cash_impact: float = Field(0.0, description="Total of payments requested for this ticket (not yet paid).")
    next_steps: list[str] = Field(default_factory=list, description="What a human or agent must do next.")


# --------------------------------------------------------------------------- run state


@dataclass
class TeamDeps:
    """Passed to every agent run. Tracks the delegation chain so the team can't loop
    forever, and shares one budget across the whole ticket."""

    run_id: str
    ticket_id: int | None
    chain: list[AgentName] = field(default_factory=list)  # who called whom, root first
    delegations_used: list[int] = field(default_factory=lambda: [0])  # shared counter (mutable box)
    max_depth: int = 3          # boss -> specialist -> specialist, no deeper
    max_delegations: int = 8    # per ticket, across all agents

    @property
    def me(self) -> AgentName:
        return self.chain[-1]

    def child(self, agent: AgentName) -> "TeamDeps":
        return TeamDeps(
            run_id=self.run_id,
            ticket_id=self.ticket_id,
            chain=[*self.chain, agent],
            delegations_used=self.delegations_used,
            max_depth=self.max_depth,
            max_delegations=self.max_delegations,
        )


# --------------------------------------------------------------------------- audit trail


class ToolCallRecord(BaseModel):
    tool: str
    args: dict | str | None = None
    result_preview: str | None = None


class AuditEntry(BaseModel):
    """One step of one agent's loop, appended to output/audit_trail.json."""

    run_id: str
    ticket_id: int | None
    agent: AgentName
    called_by: AgentName | None = Field(description="Parent agent if this run was a delegation.")
    depth: int
    step: int = Field(description="Step number inside this agent's loop.")
    node: str = Field(description="UserPrompt | ModelRequest | CallTools | End")
    timestamp: str
    model: str | None = Field(None, description="Model requested: always gpt-6-luna.")
    served_by: str | None = Field(
        None, description="Deployment name the gateway reports back, e.g. gpt-6-luna-global (same model)."
    )
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    tool_returns: list[ToolCallRecord] = Field(default_factory=list)
    text_preview: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    run_total_tokens: int | None = Field(None, description="Tokens used so far for the whole ticket.")
    stop_reason: str | None = Field(None, description="tool_call | final_answer | error | limit")
    error: str | None = None
