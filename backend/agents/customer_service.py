"""Customer Service: drafts messages for customers (never sends)."""

from backend.agents.base import make_agent
from backend.models import AgentReport

agent = make_agent("customer_service", AgentReport)
