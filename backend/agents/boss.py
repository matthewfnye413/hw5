"""Boss: reads each ticket, routes work to the team, makes the final call."""

from backend.agents.base import make_agent
from backend.models import TicketDecision

agent = make_agent("boss", TicketDecision)
