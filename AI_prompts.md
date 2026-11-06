# AI Prompts Log: HW5 Campus Customs Multi-Agent Operations

This file logs what I typed to my vibe coder (Claude Code), one problem at a time and in my own words. It is updated as the work goes.

**Format for every section:**

1. Problem number and title
2. At least one prompt I typed, in my own words
3. A follow-up prompt only if one was needed, plus one sentence on what the first prompt lacked

## Problem 1: Vibe coder prompts

**Prompt:**
> create the prompt file

(Created this `AI_prompts.md` log, plus `prompts/` for a copy of each problem's prompts, `output/` for deliverables, and `screenshots/` with `scripts/screenshot.py` for one evidence screenshot per problem. The data is set up in `data/`: the untouched original `campus_customs.db` and the working copy `campus_customs_new.db`.)

**Panel B prompt:**
> one section for each problem and follow any additional instructions in the snip

(Set up the log as one section per problem in the required format above: number and title, my prompts in my own words, and a follow-up only if needed with one sentence on what was lacking.)

**Follow-up:** none needed

## Problem 2: Study the Campus Customs database

**Prompt:**
> open the data file and follow all additional instructions in the snip

(Opened `data/campus_customs.db` and went through all 9 tables and every field. Confirmed the working copy `data/campus_customs_new.db` is identical by SHA-256. Wrote `docs/database.md`, covering each table and field, what it's for, and how the three open tickets link to the other tables. Ticket 101 (tee S, 0 in stock) is blocked by overdue invoice 501 from Bulldog Print Co. Ticket 102 is $2,400 rent due 09-02. Ticket 103 (20 hoodies in M, only 8 on hand) needs a 12-unit PO and a margin check. Key finding: $3,400 in cash covers invoice 501 plus rent, leaving $160, but not the hoodie PO on top, so the agents will have to choose.)

**Panel B prompt:**
> start the output file and follow all additional instructions in the snip

(Started `output/harness.md`. Section 1 lists every table with its fields and one short line on why that table matters for the agents. The file will keep growing in later problems.)

**Follow-up:** none needed

## Problem 3: Build the MCP server

**Prompt:**
> write an mcp server and follow all additional instructions in snip

(Installed FastMCP and wrote `mcp_server/server.py` + `mcp_server/db.py`, pointed only at `data/campus_customs_new.db`. Three clearly named tools for the open tickets: `list_open_tickets` (the board plus `desk.date_today`), `check_stock` (stock by SKU and size), and `get_cash_balance` (cash before any payment). None invent data: an unknown SKU or account returns an error listing the real ones. The server wasn't connected or run as a service; the three tools were tested by calling them in-process, and the database hash was unchanged afterward. Harness §2 lists the tools.)

**Panel B prompt:**
> In outputs, list the 3 mcp tools and follow all additonal instructions

(Rewrote harness §2 so each tool lists the table it reads, the one ticket it unlocks, and one sentence on why: `list_open_tickets` → 101 (exposes overdue invoice 501), `check_stock` → 103 (only 8 of 20 hoodies in M), `get_cash_balance` → 102 ($3,400 vs $2,400 rent). Added `mcp_server/README.md` with what the server is for, which database file it uses, and the three tools.)

**Follow-up:** none needed

## Problem 4: Add the MCP server to vibe coder and test each tool

**Prompt:**
> Add MCP server to claude so that you can call the tools. follow all additional instructions

(Saved the connection JSON in `.mcp.json` at the project root, Claude Code's project-scoped MCP list: server `campus-customs`, stdio, `python mcp_server/server.py`. Checked it by launching the server from that exact config over stdio: it connected, listed all three tools, and returned the 3 open tickets. Harness §3 documents the connection.)

(Moved the Claude Code session into the `AI_HW5` folder so it loads `.mcp.json`. The `campus-customs` tools then appeared in the vibe coder.)

**Panel B prompt:**
> test the 3 tools and follow all additional instructions

(Claude Code called each tool through the MCP connection: `list_open_tickets` for ticket 101, `check_stock` with CC-HOOD-NAVY size M for ticket 103, and `get_cash_balance` on checking for ticket 102. Saved `output/mcp_smoke.json` with, for every tool, my prompt, the tool name, the arguments, the exact tool output, and a direct database query showing it matches `data/campus_customs_new.db`. All three match: 3 open tickets dated 2026-08-31, 8 hoodies in M, and $3,400 in checking.)

**Follow-up:** none needed

## Problem 5: Build the agent team and grow the MCP tools

**Prompt:**
> build thew agentic team in accordance with these instructions

(Built five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service), one file each under `backend/agents/`, with one detailed prompt per agent in `backend/prompts/` covering its job, scope, shop rules and when to delegate. Data types are in `backend/models.py`. Every agent runs on `gpt-6-luna` via Portkey, hard-coded in `backend/llm.py`. Each agent has a `delegate` tool that can reach any other agent (full connectivity), with guards: no self or loop delegation, max depth 3, max 8 delegations per ticket, and a shared token budget. Agent loops are in `backend/team.py`.)

**Panel B prompt:**
> add any tools the agents need in accordsance with these instructions

(Grew the MCP server from 3 to 17 tools so the agents can work every ticket through MCP only: tickets, vendors, invoices, lease, pricing and margins, approval requests, a human-only `decide_approval`, `pay_approved_request` (refuses unless a human approved and cash covers it), customer drafts, and ticket status. Each agent gets a filtered, least-privilege set of those tools; there is no second data layer. Every agent-loop step is appended to `output/audit_trail.json`. Harness §4–§7 list the agents, every tool with its tables, the audit trail and the safety guardrails, and `mcp_server/README.md` now lists all 17 tools. Live test on ticket 102: Boss → Facilities → Accounting created rent approval #1 for $2,400, pending a human, with nothing paid. Then the database was reset.)

**Follow-up:** none needed

## Problem 6: Plan the three tickets

**Prompt:**
> write the expectation and follow all additional instructions

(Built `output/desk_tickets.html`, a standalone page that opens with a double-click, with tabs for Ticket 101, Ticket 102, Ticket 103, Cash and Reflection. Each ticket tab has an **Expected** section with who should work it, the expected tool calls in order, the expected decision with real amounts and dates from the database, the expected customer draft, and what should NOT happen. Each ticket tab also has an empty dashed **Actual** box to fill in after the agents run. Cash and Reflection show "coming later". Key expectations: 101 needs the $840 overdue invoice 501 approved to unblock the tee restock (around Sept 5). 102 is $2,400 rent due Sept 2, waiting on approval. 103 has only 8 of 20 hoodies in M, and paying 501, rent and a $264 PO would take checking to −$104, so the restock must be refused or deferred.)

**Panel B prompt:**
> for each expected section, direct the boss to contact the appropriate agent/department

(Added a routing plan to each ticket's Expected section: who the Boss calls **first** and why, a table of **every** delegation expected (from → to, task, why), the agents deliberately **not** called, and the **MCP tools** expected per agent plus the ones that should NOT appear. 101: Boss → Inventory first (stock decides everything), Inventory → Accounting (invoice 501 blocks Bulldog), Boss → Customer Service; Facilities not called. 102: Boss → Facilities first (lease facts), Facilities → Accounting; Inventory and Customer Service not called. 103: Boss → Inventory first (supply before price), Boss → Accounting (margin and cash), Boss → Customer Service; Facilities not called. No ticket sends every specialist.)

**Follow-up:** none needed

## Problem 7: Backend routes

**Prompt:**
> add backend routes in accordance w the instructions

(Wrote `backend/main.py` (FastAPI) with one MCP connection for the app's lifetime:
- `GET /api/tickets`: tickets with open/resolved state.
- `POST /api/tickets/{id}/run`: runs the agent team in the background and returns a run_id; 409 if the team is busy.
- `GET /api/events`: what each agent said and which tools it used, read from the audit trail and pollable with `since`.
- `POST /api/approvals/{id}/approve`: the only route that pays and changes cash, after a named person approves; refuses agent names and insufficient cash.
- `GET /api/cash`: the checking balance.
- `POST /api/reset`: copies the original database back.

Also added a `list_tickets` MCP tool, took `pay_approved_request` away from the Accounting agent so agents only prepare payments, and made the MCP server close its database connection after every call so a reset can replace the file on Windows. Tested live (`output/routes_test.txt`): the team worked ticket 101 through the API; approving #1 as an agent name was refused; approving as a person paid $840, taking checking from $3,400 to $2,560; reset brought back $3,400. Harness §8 lists the routes.)

**Panel B prompt:**
> from the backend folder start the server w this

(Made `backend/main.py` startable from inside `backend/` by adding the project root to the import path, then started the server in a terminal tab in `backend/`. The bare `uvicorn main:app --reload --port 8000` failed because `uvicorn.exe` isn't on this PC's PATH, so it runs as `python -m uvicorn main:app --reload --port 8000`, the same server. It's up at http://localhost:8000; /api/health, /api/tickets and /api/cash all returned 200. Added every route in one line (URL and what it does) to harness §8.)

**Follow-up:** none needed

## Problem 8: Agent dashboard

**Prompt:**
> build the frontend dashboard in accordance w these instructions

(Built `frontend/` with React + Vite + TypeScript, calling the Problem 7 routes through a Vite `/api` proxy. It's a three-column ops desk in navy and paper tones:
- **Left:** a ticket board with Run agent team buttons.
- **Center:** a live agent stage (the working agent glows, agents not called are greyed out, hand-offs listed), a streaming conversation with tool chips, and a "What each agent did" summary with the Boss's final call, a card per agent, and the unsent customer drafts.
- **Right:** the checking balance with a ledger, and an approval queue with Approve & pay and Reject.

Backend additions: a ticket is marked resolved when its run finishes, and the board shows only events since the last reset. Tested in the browser: ran all three tickets, approved the $840 invoice, and checking dropped from $3,400 to $2,560. Then reset. Harness §9 describes the dashboard.)

**Panel B prompt:**
> tell the frontend to talk to the backend in accordance with these instructions and follow all addtiional instructions

(The board now calls the backend directly at `http://localhost:8000`, set by `VITE_API_URL` in `frontend/.env` with that as the default, instead of going through the Vite proxy. On the backend, CORS allows only the Vite origin `http://localhost:5173` (and `127.0.0.1:5173`) for GET and POST. A preflight from that origin returned 200 with `access-control-allow-origin: http://localhost:5173`, and a foreign origin was refused. Started the board in `frontend/` with `npm run dev`, which opens the desk in the browser. On this PC PowerShell blocks `npm.ps1`, so it runs as `npm.cmd run dev`, the same command. The browser network log shows every call going to :8000 with 200s. Wrote `output/design.md`: the layout, each agent's color and badge, how resolved tickets and cash show up, and the creative choices.)

**Follow-up:** none needed

## Problem 9: Resolve the tickets

**Prompt:**
> reset the working database and follow all addtional instructions here

(Reset `data/campus_customs_new.db` from the original. **Starting checking: $3,400.00**, with all 3 tickets open, invoice 501 open and no payments. Ran 101, 102 and 103 from the board one after another until each was resolved:

| Ticket | Tokens | Agents | Hand-offs | Approvals created |
|---|---|---|---|---|
| 101 | 38.4k | Boss, Inventory, Accounting, Customer Service | 4 | #1 invoice $840, plus draft #1 |
| 102 | 19.8k | Boss, Facilities, Accounting | 2 | #2 rent $2,400 |
| 103 | 69.7k | Boss, Inventory, Accounting, Customer Service | 7 | #3 discount $40 × 20 = $800, #4 invoice $840 again, plus draft #2; the $264 PO was refused by the MCP tool while 501 is open |

Filled the **Actual** section on each ticket tab of `output/desk_tickets.html` with the agents that worked, every delegation, the MCP tools used, the result, and an Expected vs. actual table. The Expected sections are kept. Facilities was correctly never called on 101 or 103, and 102 matched the plan exactly. Differences: more hand-offs than planned on 101 and 103, a deeper discount (31%) than the 10–20% expected, and a duplicate approval for invoice 501 (#4 duplicates #1), because the duplicate check is per ticket. Nothing was paid, so checking is still $3,400.)

**Follow-up:**
> Fix it now

*What was lacking:* the full run showed the MCP server's duplicate check for payment requests only looked within one ticket, so ticket 103 queued a second $840 request for the invoice ticket 101 had already queued.

(Changed `_pending_duplicate` in `mcp_server/server.py`: invoice and rent requests are now matched on the invoice or lease id, whatever ticket asks, and the refusal points to the existing approval. Discounts stay one per ticket. Tested on a scratch copy: a second request for 501 from ticket 103 was refused ("Approval #1 … requested for ticket 101 … refer to #1"), the same for rent, and after 501 was paid any new request was refused as "not open". Restarted the backend so its MCP server loads the fix. Approval #4 from this run stays in the queue for a person to reject. Harness §7 notes the fix.)

**Panel B prompt:**
> on the cash tab itemize the money and follow all additional instructions

(On the dashboard, as **Matt Nye**, approved and paid #1 (invoice 501, $840) and #2 (rent, $2,400), rejected duplicate #4, and left discount #3 pending. That was my choice when asked which approvals to make. Filled the **Cash** tab of `output/desk_tickets.html`: starting **$3,400.00**; 101 **−$840.00** (overdue invoice 501, unblocks Bulldog) → $2,560.00; 102 **−$2,400.00** (September rent, lease next_due → 2026-10-02) → $160.00; 103 **$0.00** (discount pending, PO refused by the MCP tool, #4 rejected). Ending **$160.00** matches `cash_accounts`, and `payments` has 2 rows, both approved by Matt Nye. The $264 restock can't be afforded. Also:
- Saved `output/resolved_tickets.json`: per ticket, the id, final status, outcome, each agent's contribution and tools, and the human approvals.
- Built `output/resolved_board.html`, which opens with a double-click and has a React board screenshot for each resolved ticket in `output/resolved_board_images/`.
- `output/audit_trail.json` holds 346 entries from 8 real runs (append-only).
- Finished `output/harness.md` with a contents list and §10 (full run results, audit contents, how to run everything).
- Fixed the board so `#ticket-N` links switch tickets without a reload.)

## Problem 10: Reflection

**Prompt:**
> fill the reflection tab and follow all additional instruccftions

(Filled the **Reflection** tab of `output/desk_tickets.html` from the full-run data:
1. **Grades per ticket with reasons:** 101 B+ (right and safe, but repeated lookups and a no-date draft, 38.4k tokens); 102 A (exact plan, 19.8k tokens); 103 B− (guardrails held and the draft was honest, but 7 hand-offs, 69.7k tokens, a generous 31% discount and the duplicate approval).
2. **Actual vs. Expected per ticket:** routing matched on all three; the volume of hand-offs didn't.
3. **What one agent with tools would do more simply:** 102 and 101 outright, plus 103's fact-gathering; why the team design costs about 128k tokens, and where it still pays off (separation of duties, the customer-facing draft).
4. **Three new problems the tools can solve:** an out-of-stock Crest Mug order through the unblocked vendor, an October rent shortfall warning ($2,240), and a bulk cap discount with 40 in stock.
5. **Three it can't, with the tools and agents needed:** receiving deliveries and fulfilling orders, money coming in (sales, refunds, forecasting), and real outside communication (sending, vendor orders, inbox to tickets), plus facility repairs.)

**Panel B prompt:**
> tie every answer to this app and the corresponding tickets and follow all addtional instructiond. ehen thats complete, run q11 panel a prompt

(Added a "How to check me" note and 18 **Evidence** link rows to the Reflection. Every grade, every Actual-vs-Expected row, each one-agent point, each of the 6 new problems, and the bottom line now link to their proof on the same page: the ticket tab (its Expected plan, Actual hand-offs, tools table, refused PO, drafts) or the Cash tab ($3,400.00 → −$840.00 → −$2,400.00 → $160.00, approvals #1–#4). Made in-page links switch tabs (hashchange) and tested it: Cash link → Cash tab, Back → Reflection, 103 link → Ticket 103, with no page errors.)

**Follow-up:** none needed

## Problem 11: Submit to GitHub

**Prompt:**
> push code to apublic github and follow all additional instruvcitons. provide url

(Added:
- `.gitignore`: keeps out the real `.env`, `node_modules` and `.claude/`.
- `.env.example`: a placeholder key.
- A root `README.md`: copy the original DB to the working copy for a clean run, start the MCP server, start the FastAPI backend, start the React board, and reset before a full three-ticket run.
- A rewritten `frontend/README.md`.

Renamed `frontend/.env` to `.env.development`; it holds only the backend URL. Committed 124 files in the expected layout, with **both** databases in `data/`. Scanned every file, images included: the real Portkey key appears nowhere. Created the **public** repo `matthewfnye413/hw5` on github.com after I signed in, pushed `main`, and confirmed with an anonymous clone that every expected file is there and no `.env` is. The URL is saved in `output/github_url.txt`.)

**Follow-up:**
> signed in

*What was lacking:* the `gh` tool isn't installed and the browser pane wasn't signed in to GitHub, so the repo couldn't be created until I signed in myself.

**Repo URL:** https://github.com/matthewfnye413/hw5
