"""Inventory: stock by SKU and size, shortfalls, which vendor can restock and when."""

from backend.agents.base import make_agent
from backend.models import AgentReport

agent = make_agent("inventory", AgentReport)
