"""Accounting: cash, invoices, margins; prepares payments and POs for human approval."""

from backend.agents.base import make_agent
from backend.models import AgentReport

agent = make_agent("accounting", AgentReport)
