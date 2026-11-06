"""The five Campus Customs agents. Prompts live in backend/prompts/<role>.md."""

from backend.agents.accounting import agent as accounting
from backend.agents.boss import agent as boss
from backend.agents.customer_service import agent as customer_service
from backend.agents.facilities import agent as facilities
from backend.agents.inventory import agent as inventory

AGENTS = {
    "boss": boss,
    "inventory": inventory,
    "accounting": accounting,
    "facilities": facilities,
    "customer_service": customer_service,
}
