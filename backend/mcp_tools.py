"""The agents' only way to touch shop data: the campus-customs MCP server.

There is no second tools layer. Each agent gets a filtered view of the same MCP server
(least privilege). decide_approval is in NO agent's list, because only a human approves.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "server.py"

# Which MCP tools each role may call.
ROLE_TOOLS: dict[str, set[str]] = {
    "boss": {"get_ticket", "list_open_tickets", "list_approvals", "update_ticket_status"},
    "inventory": {"check_stock", "list_vendors", "get_pricing", "request_purchase_order", "get_ticket"},
    "accounting": {
        "get_cash_balance", "list_invoices", "list_vendors", "get_pricing", "request_payment_approval",
        "request_discount_approval", "list_approvals", "get_ticket",
    },
    "facilities": {"get_lease", "get_ticket", "get_cash_balance"},
    "customer_service": {"get_ticket", "check_stock", "save_customer_draft", "list_customer_drafts"},
}
# Only the dashboard's approve route (backend/main.py) calls these, after a person clicks
# Approve. Agents prepare payments; they never approve or pay.
HUMAN_ONLY_TOOLS = {"decide_approval", "pay_approved_request"}
assert not any(HUMAN_ONLY_TOOLS & tools for tools in ROLE_TOOLS.values())
AGENT_NAMES_LOWER = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service"}

# One MCP server process (stdio) shared by every agent in a run.
shop_mcp = MCPToolset(
    Client(StdioTransport(command=sys.executable, args=[str(SERVER)], cwd=str(ROOT))),
    id="campus-customs",
    tool_error_behavior="error",
)


def toolset_for(role: str):
    allowed = ROLE_TOOLS[role]
    return shop_mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)
