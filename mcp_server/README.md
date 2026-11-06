# Campus Customs MCP server

**What it's for:** this is the shared toolbox for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Every agent gets its shop abilities by calling these tools; there is no other path to shop data. The tools return only what is in the database. Anything missing comes back as an error, never as a guessed value.

**Database:** `data/campus_customs_new.db`, the working copy. The original `data/campus_customs.db` is never opened, so it stays clean for resets: copy it over the working copy to start fresh. Set the `CAMPUS_DB` environment variable to point at a different copy for testing.

On first use the server also creates two working tables in that copy:
- `approvals`: the human-approval queue for payments, POs and discounts.
- `customer_drafts`: unsent messages.

**Built with:** FastMCP (`pip install fastmcp`). Server name: `campus-customs`.

## Tools (18)

| Tool | Reads | Writes | What it's for |
|---|---|---|---|
| `list_open_tickets()` | tickets, desk | none | The board: every unresolved ticket plus `date_today` |
| `list_tickets()` | tickets, desk | none | Every ticket, including resolved ones, with `state` open/resolved (used by the dashboard) |
| `get_ticket(ticket_id)` | tickets, inventory, pricing, invoices, vendors, leases, approvals, customer_drafts | none | One ticket with all its linked rows |
| `update_ticket_status(ticket_id, status, note, updated_by)` | tickets | tickets | Move a ticket (open / in_progress / waiting_approval / blocked / resolved) with a dated note |
| `check_stock(sku, size=None)` | inventory | none | Stock by SKU and size (ticket 101: tee S = 0; 103: hoodie M = 8) |
| `list_vendors(specialty=None)` | vendors, invoices | none | Lead days, open invoices, `can_ship`, arrival date if ordered today |
| `get_cash_balance(account=None)` | cash_accounts | none | Cash on hand before any payment |
| `list_invoices(status=None, vendor_id=None)` | invoices, vendors | none | Unpaid bills and `days_overdue` vs `date_today` |
| `get_lease(lease_id)` | leases, payments | none | Rent, next due date, days until due, paid this cycle? |
| `get_pricing(sku, proposed_unit_price=None, qty=None)` | pricing | none | Cost, list price, margin; tests a discount (`below_cost` flag) |
| `request_payment_approval(kind, ref_id, reason, requested_by, ticket_id=None)` | invoices, leases, cash_accounts | approvals | Pending request to pay an invoice or rent; the amount comes from the DB |
| `request_purchase_order(sku, size, qty, vendor_id, reason, requested_by, ticket_id=None)` | inventory, pricing, vendors, invoices | approvals | Pending restock PO; refused if the vendor has an open invoice |
| `request_discount_approval(ticket_id, sku, qty, unit_price, reason, requested_by)` | pricing, tickets | approvals | Pending discount quote; refused below unit cost |
| `list_approvals(status=None, ticket_id=None)` | approvals | none | The approval queue |
| `decide_approval(approval_id, decision, human_name)` | approvals | approvals | **Human only** (dashboard). Agents are never given this tool. |
| `pay_approved_request(approval_id, account="checking")` | approvals, cash_accounts | payments, cash_accounts, invoices, leases, approvals | **Human only.** Called by the backend's approve route; pays only a human-approved request and refuses if cash would go negative. |
| `save_customer_draft(ticket_id, to_name, subject, body, drafted_by)` | tickets | customer_drafts | Saves a message as a draft. Never sent. |
| `list_customer_drafts(ticket_id=None)` | customer_drafts | none | Drafts on the board |

## Rules built into the tools

- Today is `desk.date_today`, never the computer clock.
- Payment amounts and payees come from the database, not from the agent.
- Nothing is paid without a named human's approval, and never past a zero balance.
- A vendor with an open unpaid invoice can't get a new purchase order.
- Customer messages are drafts only.

## Files

- `server.py`: the FastMCP server and all tools.
- `db.py`: the database connection (working copy only, foreign keys on, closed after every call so a reset can replace the file), the extra working tables, and date helpers.

## Run

From the project root (stdio transport):

```
python mcp_server/server.py
```

Claude Code connects through `.mcp.json`. The agent backend connects in `backend/mcp_tools.py`.
