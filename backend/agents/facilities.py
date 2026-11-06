"""Facilities: the shop space, lease and rent."""

from backend.agents.base import make_agent
from backend.models import AgentReport

agent = make_agent("facilities", AgentReport)
