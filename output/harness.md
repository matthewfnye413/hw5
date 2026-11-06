# Campus Customs Multi-Agent Operations: Harness

The harness is everything around the model: the data, tools, agents, rules and approvals that let the agent team run the shop safely.

- **Model:** `gpt-6-luna` via Portkey, for every agent. No other model.
- **Agents:** Boss · Inventory · Accounting · Facilities · Customer Service (any agent can delegate to any other)
- **Data:** `data/campus_customs_new.db` is the working copy. `data/campus_customs.db` is the untouched original, used to reset before a full run.

**Contents:**
- **Tables:** §1 (field details in `docs/database.md`)
- **MCP tools:** §2 (the first three, tied to tickets), §3 (connecting and smoke-testing them), §5 (all 18 with their tables)
- **The five agents:** §4
- **Audit trail:** §6
- **Safety rules:** §7
- **API routes:** §8
- **Dashboard:** §9
- **Full run results and how to run everything:** §10

## 1. Database tables

Each table lists its fields and one short line on why it matters for the agents.

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `desk` | `date_today`, `notes` | The shop's "today" (2026-08-31). Every agent uses it, not the computer clock, to decide what's overdue or due soon. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | The work board. The Boss reads each ticket's `type` and links to route it, and agents update `status` when it's resolved. |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` | Inventory checks stock by SKU and size to find shortfalls (e.g. tee S = 0, hoodie M = 8 of 20 needed). |
| `pricing` | `sku`, `unit_cost`, `list_price` | Accounting checks margins, prices discount requests so they stay above cost, and costs purchase orders. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Inventory picks who can restock an item and uses `lead_days` to promise an arrival date. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | Facilities confirms the rent amount and due date for rent tickets. |
| `cash_accounts` | `name`, `balance`, `date` | Accounting checks cash before any payment. The pay tool refuses anything that would make the balance negative. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | The payment ledger. A row is written only after a human approves (`approved_by` is required), which proves the approval happened. |
| `invoices` | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | Accounting tracks unpaid bills. An `open` invoice blocks that vendor from shipping until it's paid. |

Full field-by-field details and the ticket walkthrough are in `docs/database.md`.

## 2. MCP server tools

- **Code:** `mcp_server/server.py` (FastMCP, server name `campus-customs`) and `mcp_server/db.py`
- **Database:** only `data/campus_customs_new.db`. The `CAMPUS_DB` env var can override the path for tests.
- **Shared by:** every agent gets its shop abilities from these tools.
- **Rule:** never invent data. A SKU, size or account that isn't in the database returns an error listing what does exist, never a guessed value or a 0.

Each tool below is tied to the one ticket it unlocks.

### `list_open_tickets` → unlocks ticket **101**

- **Reads:** `tickets` (open rows) and `desk` (`date_today`)
- **Inputs / returns:** no inputs. Returns `date_today` and each open ticket with its link fields (`sku`, `size`, `qty`, `lease_id`, `invoice_id`).
- **Why it's the right tool for 101:** ticket 101 looks like a simple one-tee order, but only this tool shows its `invoice_id` = 501 next to `date_today` = 2026-08-31, which tells the Boss there's an overdue Bulldog Print Co bill blocking the restock, so the ticket goes to Accounting as well as Inventory.

### `check_stock` → unlocks ticket **103**

- **Reads:** `inventory` (qty and location by `sku` + `size`)
- **Inputs / returns:** `sku`, optional `size`. Returns qty per size and the total; an unknown SKU or size is an error, not 0.
- **Why it's the right tool for 103:** the Yale AI Club wants 20 `CC-HOOD-NAVY` in size **M**, and `check_stock` shows only **8** in M (out of 32 across all sizes), which proves a 12-unit shortfall that has to be restocked before any discount is quoted.

### `get_cash_balance` → unlocks ticket **102**

- **Reads:** `cash_accounts` (balance per account) and `desk` (`date_today`)
- **Inputs / returns:** optional `account`. Returns the balance per account and the total.
- **Why it's the right tool for 102:** the $2,400 rent is due 2026-09-02, and `get_cash_balance` shows **$3,400** in checking, so Accounting can confirm the rent fits (leaving $1,000, or only $160 if invoice 501 is also paid) before asking a human to approve it.

**Overlap:** `check_stock` also confirms ticket 101's tee S = 0, and `get_cash_balance` is the cash check before paying invoice 501.

All three only read. Tools that write, like payments and status updates, come in later problems behind human approval.

## 3. Connecting the MCP server to the vibe coder

The connection is saved in `.mcp.json` at the project root, which is Claude Code's project-scoped MCP server list:

```json
{
  "mcpServers": {
    "campus-customs": {
      "type": "stdio",
      "command": "python",
      "args": ["mcp_server/server.py"],
      "env": { "PYTHONIOENCODING": "utf-8" }
    }
  }
}
```

- **Transport:** stdio. Claude Code starts `python mcp_server/server.py` from the project root and talks to it over stdin/stdout.
- **Paths:** relative, so the repo works on any machine. The server finds `data/campus_customs_new.db` from its own file location.
- **Check:** launching the server from this exact config over stdio connected, listed `list_open_tickets`, `check_stock` and `get_cash_balance`, and returned the 3 open tickets.
- Claude Code asks for approval the first time it starts a project `.mcp.json` server.

### Smoke test from the vibe coder (`output/mcp_smoke.json`)

Claude Code loaded the server from `.mcp.json`, and each tool was called as `mcp__campus-customs__<tool>`. Every output was cross-checked against `data/campus_customs_new.db`:

| Tool | Arguments | Key output | Database value | Match |
|---|---|---|---|---|
| `list_open_tickets` | none | today 2026-08-31; open tickets 101, 102, 103; ticket 101 → invoice 501 | same rows from `tickets` + `desk` | ✅ |
| `check_stock` | `CC-HOOD-NAVY`, `M` | qty 8, Aisle A | `inventory` M = 8, Aisle A | ✅ |
| `get_cash_balance` | `checking` | $3,400 | `cash_accounts` checking = 3400.0 | ✅ |

The database hash was unchanged after the test, since all three tools only read.

## 4. The agent team (PydanticAI)

All five agents run on **`gpt-6-luna` via Portkey**. The name is a constant in `backend/llm.py`, so no env var can switch the model. Each agent has its own prompt file, its own output type, and a filtered view of the MCP server. Every agent has a `delegate` tool that can reach any other agent (**full connectivity**).

| Agent | File | Prompt | Output | Role |
|---|---|---|---|---|
| **Boss** | `backend/agents/boss.py` | `backend/prompts/boss.md` | `TicketDecision` | Reads each ticket, routes it to teammates, checks their facts, makes the final call, sets the ticket status |
| **Inventory** | `backend/agents/inventory.py` | `backend/prompts/inventory.md` | `AgentReport` | Stock by SKU **and size**, shortfall math, which vendor can restock, honest arrival dates, PO requests |
| **Accounting** | `backend/agents/accounting.py` | `backend/prompts/accounting.md` | `AgentReport` | Cash, invoices and overdue days, margins and discounts; prepares payments for human approval. Never pays; only the dashboard's approve route pays. |
| **Facilities** | `backend/agents/facilities.py` | `backend/prompts/facilities.md` | `AgentReport` | The lease, rent due dates and the landlord; hands rent payments to Accounting |
| **Customer Service** | `backend/agents/customer_service.py` | `backend/prompts/customer_service.md` | `AgentReport` | Drafts honest customer messages to the board; never sends |

**Shared pieces:**
- `backend/agents/base.py` builds each agent: model, prompt, tools, and the `delegate` tool with its guards.
- `backend/models.py` holds the data types: `AgentReport`, `Fact` (each fact names its source tool), `TicketDecision`, `TeamDeps` (the delegation chain and budget), and `AuditEntry`.
- `backend/team.py` runs the agent loops: `run_ticket`, `run_agent`, and the command line `python -m backend.team --ticket N | --all`.

**How delegation works:** `delegate(to, task)` runs the target agent's own loop as a nested run. It shares the ticket's token budget and returns that agent's report as the tool result. The Boss always has the last word.

**Live test (ticket 102)**, from `output/team_test_ticket102.txt`:
- **Path:** Boss → Facilities (`get_lease`) → Accounting (`get_cash_balance`, `request_payment_approval`) → back to Boss (`list_approvals`, `update_ticket_status`).
- **Result:** rent approval #1, $2,400, **pending a human**. No payment was made and checking stayed at $3,400. The ticket was moved to `waiting_approval`.
- **Cost:** 22,726 tokens.
- The database was reset afterwards.

## 5. All MCP tools and the tables they use

Shop facts come only from the MCP server over `data/campus_customs_new.db`. The backend has no second data layer: `backend/mcp_tools.py` connects to `mcp_server/server.py` over stdio and gives each agent a filtered list of its tools.

| Tool | Reads | Writes | Agents that get it |
|---|---|---|---|
| `list_open_tickets` | tickets, desk | none | Boss |
| `list_tickets` | tickets, desk | none | **No agent.** The dashboard uses it: all tickets with open/resolved state. |
| `get_ticket` | tickets, inventory, pricing, invoices, vendors, leases, approvals, customer_drafts, desk | none | all five |
| `update_ticket_status` | tickets, desk | tickets | Boss |
| `check_stock` | inventory | none | Inventory, Customer Service |
| `list_vendors` | vendors, invoices, desk | none | Inventory, Accounting |
| `get_cash_balance` | cash_accounts, desk | none | Accounting, Facilities |
| `list_invoices` | invoices, vendors, desk | none | Accounting |
| `get_lease` | leases, payments, desk | none | Facilities |
| `get_pricing` | pricing | none | Inventory, Accounting |
| `request_payment_approval` | invoices, leases, vendors, cash_accounts | approvals | Accounting |
| `request_purchase_order` | inventory, pricing, vendors, invoices, cash_accounts | approvals | Inventory |
| `request_discount_approval` | pricing, tickets | approvals | Accounting |
| `list_approvals` | approvals | none | Boss, Accounting |
| `pay_approved_request` | approvals, cash_accounts, invoices, leases | payments, cash_accounts, invoices, leases, approvals | **No agent.** Only the backend's approve route calls it, right after a person clicks Approve. |
| `save_customer_draft` | tickets | customer_drafts | Customer Service |
| `list_customer_drafts` | customer_drafts | none | Customer Service |
| `decide_approval` | approvals | approvals | **No agent.** Humans only, through the dashboard. |

`approvals` and `customer_drafts` are two working tables the MCP server creates in the working copy. They hold the human-approval queue and the unsent drafts. A reset (copying `campus_customs.db` over the working copy) clears them.

## 6. Audit trail (`output/audit_trail.json`)

`backend/audit.py` appends **one entry per agent-loop step** (UserPrompt, ModelRequest, CallTools, End, or Error) as the agents run.

**Each entry records:**
- `run_id`, `ticket_id`
- `agent`, `called_by`, `depth` (who delegated to whom)
- `step`, `node`, `timestamp`
- `model` (always gpt-6-luna) and `served_by`, the deployment name Portkey/Azure reports back for that same model, `gpt-6-luna-global`. The first test run's entries were written before `served_by` existed, so they show `gpt-6-luna-global` in `model`. It's the same model, not a different one.
- `tool_calls` with arguments, and `tool_returns` with a short result preview
- a short text preview
- input and output tokens, plus the running token total for the ticket
- `stop_reason` (`tool_call`, `final_answer`, `error` or `limit`) and any error

**How it's kept safe:**
- The file is **append-only**: it's never wiped or rewritten between runs.
- Each write is atomic (temp file, then replace), so a crash can't leave a half-written file.
- A corrupt file is set aside, not deleted.

The ticket 102 test added 28 entries.

## 7. Safety guardrails

What a real business needs once agents touch real customers and real money:

**Money**
- **Human approval for every payment.** Agents can only *request*: `request_payment_approval`, `request_purchase_order` and `request_discount_approval` create `pending` rows. Only `decide_approval` can approve, and it rejects agent names as the approver. `pay_approved_request` refuses anything not approved by a named human. **No agent has either tool.** Only the backend's `POST /api/approvals/{id}/approve` route calls them, after a person clicks Approve. `payments.approved_by` stores that person.
- **Amounts come from the database, not the model.** Invoice and rent amounts are read from `invoices` and `leases`, and PO cost is qty × `pricing.unit_cost`. An agent can't type a dollar amount into a payment.
- **No negative balances.** The pay tool checks the balance in the same transaction and refuses with the shortfall. Cash only goes out.
- **Business rules in code, not just prompts.** A vendor with an open invoice can't get a PO, discounts below cost are refused, approvals can't be duplicated, and a paid invoice can't be paid twice.
- **No duplicate payment requests across tickets** (fixed after the Problem 9 run). An invoice or rent request is matched on the bill itself (invoice or lease id), not on the ticket that asked. In the full run, ticket 103 had queued a second $840 request for invoice 501 (approval #4, a copy of #1). Now that's refused with "Approval #1 for this invoice already exists (requested for ticket 101)… refer to #1." Discounts stay one per ticket. Even before the fix, money was safe: once 501 is paid, the pay tool refuses a second payment because the invoice isn't open.
- **One transaction per payment:** the `payments` row, the cash balance, and the invoice or lease update happen together or not at all.

**Customers**
- **Draft-only.** No tool can send email or contact anyone. Customer Service saves drafts to the board for a person to review.
- **No made-up promises.** Prompts forbid inventing prices, dates or discounts, and every fact in a report must name its source tool.
- **Privacy.** Customer messages never mention other customers, the shop's cash, vendor invoices or approvals.

**Access and accountability**
- **Least privilege.** Each agent gets only the MCP tools its job needs (§5). For example, Customer Service can't touch money, and Facilities can't pay rent.
- **One source of truth.** All shop facts go through MCP over the working copy. The original database is never opened, so it's always available for a reset.
- **Full audit trail.** Every step, tool call and token count is logged and appended.

**Token and cost limits**
- **One model only:** gpt-6-luna, hard-coded.
- **Per-ticket budget** shared by every agent the ticket involves: 40 model requests, 60 tool calls, 250,000 total tokens (`UsageLimits`). Going over stops the run and logs a `limit` entry.
- **Reply cap:** `max_tokens` = 4,000 per model reply.
- **Delegation guards:** at most 3 agents deep, at most 8 delegations per ticket, no delegating to yourself or to any agent already in the chain (no loops), and refusals come back as text so the agent can finish.
- **Smaller toolsets** keep prompts short. Each agent sees 3–8 tool schemas, not all 18.
- **Retries:** 2 per agent for bad outputs.
- **One team run at a time** (backend lock, §8), so two tickets never spend tokens or write to the database at once.

## 8. Backend routes (`backend/main.py`, FastAPI)

**Start the server** from the `backend/` folder, so the dashboard can call it at `http://localhost:8000`:

```
cd backend
uvicorn main:app --reload --port 8000
```

On this machine the bare `uvicorn` command isn't on PATH, because pip put `uvicorn.exe` in a Python Scripts folder Windows doesn't search. `python -m uvicorn main:app --reload --port 8000` runs the same server. It also starts from the project root as `uvicorn backend.main:app --port 8000`.

### Every route in one line

- `GET  /api/tickets`: the three tickets, each with its status and open/resolved state.
- `GET  /api/tickets/{id}`: one ticket with its linked stock, invoice, lease, approvals and drafts.
- `POST /api/tickets/{id}/run`: run the agent team on that ticket in the background; returns a run_id.
- `GET  /api/runs`: every agent run started from the dashboard, with its status.
- `GET  /api/runs/{run_id}`: one run's status, the Boss's final decision, and tokens used.
- `GET  /api/events?since=N`: recent agent events: what each agent said and which tools it used, so the board can refresh.
- `GET  /api/approvals`: the approval queue (pending, approved, rejected, paid).
- `POST /api/approvals/{id}/approve`: a person approves; for payments and POs this pays and changes cash.
- `POST /api/approvals/{id}/reject`: a person rejects a request; nothing is paid.
- `GET  /api/cash`: the current checking balance from `cash_accounts`.
- `GET  /api/drafts`: customer message drafts on the board (never sent).
- `GET  /api/health`: health check showing the model, the database file and the audit entry count.
- `POST /api/reset`: copy the original database over the working copy for a fresh run.

### Route details

**How it connects:**
- The app opens **one** MCP server connection for its whole lifetime, and every route reads and writes shop data through MCP tools.
- CORS allows the Vite dev server on `localhost:5173`.

| # | Route | What it does | MCP tools behind it |
|---|---|---|---|
| 1 | `GET /api/tickets` | The three tickets with raw `status` and `state` = open/resolved, plus any agent run in progress | `list_tickets` |
| 1 | `GET /api/tickets/{id}` | One ticket with linked rows, approvals and drafts | `get_ticket` |
| 2 | `POST /api/tickets/{id}/run` | Starts the agent team on that ticket in the background and returns **202** with a `run_id`. **409** if the team is already busy, **404** for an unknown ticket. | the agents' own tools |
| 2 | `GET /api/runs/{run_id}`, `GET /api/runs` | Run status (running/done/error), the Boss's `TicketDecision`, tokens, requests and tool calls | none |
| 3 | `GET /api/events?since=N&run_id=&ticket_id=` | Recent agent events from `audit_trail.json`: agent, who called it, **what it said** (task received, delegation, final answer) and **which tools it used** with arguments. Poll with `since=next_since` so the board only fetches new events. | none (reads the audit trail) |
| 4 | `GET /api/approvals` | The approval queue | `list_approvals` |
| 4 | `POST /api/approvals/{id}/approve` `{approved_by}` | **The only place cash changes.** A person approves; for a payment or PO the route then pays it (payments row, lower checking, invoice paid / lease next_due moved). It refuses with 409 and leaves the request pending if checking can't cover it, and refuses agent names as the approver. A discount is approved without moving money. | `decide_approval`, `pay_approved_request`, `get_cash_balance` |
| 4 | `POST /api/approvals/{id}/reject` `{approved_by}` | A person rejects a request | `decide_approval` |
| 5 | `GET /api/cash` | Current checking balance from `cash_accounts` | `get_cash_balance` |
| 6 | `POST /api/reset` | Copies the untouched `campus_customs.db` over `campus_customs_new.db`, bringing back $3,400, open tickets and no approvals. **409** while the team is running. The audit trail is **not** wiped. | none (file copy) |
| – | `GET /api/drafts`, `GET /api/health` | Customer drafts on the board; health check | `list_customer_drafts` |

**Change in this problem:** `pay_approved_request` was taken away from the Accounting agent. Agents now only prepare payments, and the approve route is what pays.

## 9. Agent dashboard (`frontend/`, React + Vite + TypeScript)

**Run:**
1. Start the backend (§8).
2. In `frontend/`, run `npm install`, then `npm run dev`.
3. Open http://localhost:5173.

Vite proxies `/api` to `:8000`.

**Layout:** a three-column desk.
- **Left: ticket board.** All three tickets with type, requester, item, a status badge (Open, Agents working, Resolved) and a **Run agent team** button. Only one run can go at a time.
- **Center: the work.**
  - The ticket header shows live token and tool-call counts.
  - The **agent stage** has the five agents as avatars. The one working **glows**, the ones brought in say "on this ticket", the ones not called are greyed out, and the hand-offs (Boss → Inventory …) are listed below.
  - The **conversation** shows each agent's messages as they happen: the task it received, its delegations, the MCP tool chips with arguments, and its final report. It polls `/api/events` every 1.5 s while a run is live.
  - Under **What each agent did**, the Boss's final call (decision, status, next steps) sits in a navy card. Below it is one card per agent with its last report, who it asked, and the tools it used, then the customer drafts marked "not sent".
- **Right: money.**
  - The **checking balance** card has a bar showing spent versus starting cash and a ledger of who approved each payment. It flashes red when the balance drops.
  - **Needs your approval** shows each pending request with its amount, payee and reason, plus **Approve & pay** and **Reject** buttons. An "Approving as" name field is required. The card warns, and the button is disabled, when cash won't cover the request.
- **Top bar:** shop date, open/resolved count, checking, the model (`gpt-6-luna`), and **Reset data** (asks for confirmation; disabled during a run).

**Behaviour added for the board:**
- When a run finishes, the backend marks the ticket **resolved** and notes any approvals still pending. The Boss's own recommended status is kept in the note and on the decision card.
- `POST /api/reset` records the audit index in `output/reset_log.json`. `/api/events?current=true` shows only activity since the last reset, while the audit trail itself is never wiped.

**Tested in the browser (then reset):**
- Ran ticket 101 from the board and watched the agents live. Facilities stayed greyed out ("not called"), and the ticket was marked Resolved.
- Clicked **Approve & pay** on the $840 invoice. Checking dropped from **$3,400 to $2,560**, and the ledger shows the approver.
- Ran 102 (rent request $2,400) and 103 (discount $960 at $48 each, plus a $264 PO). Both resolved, with their approvals queued.

## 10. Full run results and how to run everything

### The full run (Problem 9, 2026-11-06)

The database was reset first, so it started at **$3,400.00** with all tickets open. Each ticket was run from the board in turn, then a person approved on the dashboard.

| Ticket | Run | Agents (first call → others) | Hand-offs | Tokens | Human approvals | Cash change |
|---|---|---|---|---|---|---|
| 101 tee size S | `838a675783c0` | Boss → **Inventory**, Accounting, Customer Service | 4 | 38,400 | #1 invoice 501, **paid** by Matt Nye | **−$840.00** → $2,560.00 |
| 102 rent | `d6c7373861d3` | Boss → **Facilities** → Accounting | 2 | 19,798 | #2 rent lease 1, **paid** by Matt Nye | **−$2,400.00** → $160.00 |
| 103 bulk hoodies | `2a359b50d7c1` | Boss → **Inventory**, Accounting, Customer Service | 7 | 69,661 | #3 discount $40 × 20 **pending**; #4 duplicate invoice **rejected** by Matt Nye | $0.00 → $160.00 |

- **Ending checking: $160.00**, which matches `cash_accounts`. There are 2 rows in `payments`, both `approved_by = Matt Nye`. Invoice 501 is `paid`, and lease 1 `next_due` is now 2026-10-02.
- **Facilities was never called on 101 or 103**, and Inventory and Customer Service never on 102. Not every specialist went on every ticket.
- **Guardrails seen working in the real run:**
  - The MCP tool **refused the restock PO** while invoice 501 was open.
  - **No payment ran without a named person** approving it on the dashboard.
  - The dashboard **disabled Approve** on duplicate #4 because $160 couldn't cover it.
  - The 12-hoodie restock ($264) **can't be afforded** with $160 left.
- **Fixed after the run:** duplicate payment requests across tickets (§7).
- **Evidence:**
  - `output/desk_tickets.html`: Expected vs. Actual per ticket, plus the Cash tab.
  - `output/resolved_tickets.json`: per ticket, the status, outcome, what each agent contributed, and the approvals.
  - `output/resolved_board.html`: board screenshots for each resolved ticket.

### Audit trail contents

`output/audit_trail.json` holds **346 entries across 8 real runs**. It has never been wiped:
- the Problem 5 test of 102;
- the Problem 7 route test of 101;
- three Problem 8 dashboard tests (101, 102, 103);
- the three Problem 9 full-run tickets.

`output/reset_log.json` records where each reset happened, so the board shows only runs since the last reset.

### How to run everything

1. **Put the data in place:** `data/campus_customs.db` (from data.zip). Copy it to `data/campus_customs_new.db`, or press **Reset data** on the board.
2. **Set the key:** put `PORTKEY_API_KEY` in a `.env` file (the project's or its parent folder's).
3. **Install the Python packages:** `pip install -r requirements.txt` (fastmcp, pydantic-ai-slim[openai], openai, python-dotenv, fastapi, uvicorn).
4. **Start the backend:** in `backend/`, run `uvicorn main:app --reload --port 8000`, or `python -m uvicorn …` if `uvicorn` isn't on PATH. It starts the MCP server itself over stdio.
5. **Start the board:** in `frontend/`, run `npm install`, then `npm run dev` (or `npm.cmd run dev` if PowerShell blocks scripts). Open http://localhost:5173.
6. **Use it:** pick a ticket, press **Run agent team**, watch the agents, then approve or reject in **Needs your approval**.
7. **Optional, from a vibe coder:** `.mcp.json` connects Claude Code to the same MCP server, and `python -m backend.team --ticket N` runs the team from the command line.
