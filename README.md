# Campus Customs Multi-Agent Operations (HW5)

An agent team that runs the Campus Customs ticket board. It has three pieces that talk to each other:

| Piece | Folder | What it does |
|---|---|---|
| **MCP server** (FastMCP) | `mcp_server/` | 18 shop tools over `data/campus_customs_new.db`. This is the only way the agents touch shop data. |
| **FastAPI backend** with the agent team (PydanticAI) | `backend/` | Five agents (Boss, Inventory, Accounting, Facilities, Customer Service) on **gpt-6-luna** via Portkey, with full delegation. Also the API routes for the board. |
| **React dashboard** (Vite + TS) | `frontend/` | Pick a ticket, watch the agents work live, approve payments, and watch checking change. |

**Rules the code enforces:**
- A person must approve every payment. Agents only prepare requests, and the dashboard's approve route is what pays.
- A payment that would leave checking below $0 is refused.
- A vendor with an open unpaid invoice can't get a purchase order.
- Customer messages stay as drafts and are never sent.
- `desk.date_today` is "today".

The full design is in `output/harness.md`.

---

## 1. Setup (once)

```bash
pip install -r requirements.txt
cp .env.example .env            # then put your PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

Python 3.11+ and Node 18+. Only `gpt-6-luna` is used (hard-coded in `backend/llm.py`).

## 2. The database: copy the original to the working copy for a clean run

- `data/campus_customs.db` is the **original**. It is never modified.
- `data/campus_customs_new.db` is the **working copy**. The MCP server and backend read and write only this file.

For a clean start, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

On Windows PowerShell: `Copy-Item data\campus_customs.db data\campus_customs_new.db -Force`

Or press **↺ Reset data** on the dashboard, or call `POST http://localhost:8000/api/reset`, which does the same copy. The repo's working copy is committed in its **after-the-full-run** state (checking $160.00), so reset it before you run the agents yourself.

## 3. Start the MCP server

```bash
python mcp_server/server.py
```

It uses the stdio transport. You normally **don't need to start it by hand**:
- The backend starts it automatically and keeps one connection open.
- Claude Code starts it from `.mcp.json` when you open this folder.

The tool list is in `mcp_server/README.md`.

## 4. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

If `uvicorn` isn't on your PATH, use `python -m uvicorn main:app --reload --port 8000`. The API runs at http://localhost:8000; the routes are listed at `/docs` and in harness §8.

## 5. Start the React board

```bash
cd frontend
npm run dev
```

This opens http://localhost:5173. On Windows PowerShell, use `npm.cmd run dev` if scripts are blocked. The board calls the backend at `http://localhost:8000`, and the backend's CORS allows only this page's origin.

## 6. A full three-ticket run

1. **Reset the database first** (step 2, or **↺ Reset data**). Checking should read **$3,400.00** and all three tickets should be **Open**.
2. On the board, press **▶ Run agent team** on **101**, wait for **Resolved**, then do **102**, then **103**. Only one run can go at a time.
3. Watch the agent stage and the conversation. In **Needs your approval**, type your name in "Approving as", then **Approve & pay** or **Reject** each request. Checking drops only when you approve a payment.

Command-line alternative: `python -m backend.team --ticket 101` (or `--all`).

## 7. Where the results are

| File | What's in it |
|---|---|
| `AI_prompts.md`, `prompts/` | Every prompt I gave the vibe coder, by problem |
| `output/harness.md` | Tables, MCP tools, the five agents, API routes, the dashboard, safety rules, and the full-run results |
| `output/mcp_smoke.json` | The vibe coder calling each MCP tool, checked against the database |
| `output/desk_tickets.html` | Expected vs. Actual per ticket, the Cash tab and the Reflection. Double-click to open. |
| `output/design.md` | Dashboard design choices |
| `output/resolved_tickets.json` | Per ticket: status, outcome, agent contributions, approvals |
| `output/resolved_board.html` | Board screenshots for each resolved ticket |
| `output/audit_trail.json` | Append-only log of every agent-loop step (never wiped) |
| `output/github_url.txt` | This repo's URL |
| `screenshots/SCREENSHOTS.md` | One screenshot (or more) per problem |

**Full-run result:**
- Checking went **$3,400.00 → $160.00** (−$840 invoice 501, −$2,400 rent, both approved by a person).
- The 103 discount is waiting for approval.
- The $264 hoodie restock can't be afforded.
- Details are on the Cash tab.

## Layout

```
hw5/
├── AI_prompts.md   requirements.txt   .env.example   .gitignore   .mcp.json   README.md
├── data/           campus_customs.db (original) · campus_customs_new.db (working copy)
├── mcp_server/     server.py · db.py · README.md
├── backend/        main.py · models.py · team.py · llm.py · mcp_tools.py · audit.py
│   ├── agents/     boss.py · inventory.py · accounting.py · facilities.py · customer_service.py · base.py
│   └── prompts/    boss.md · inventory.md · accounting.md · facilities.md · customer_service.md
├── frontend/       React + Vite + TypeScript board
├── output/         harness.md · mcp_smoke.json · desk_tickets.html · design.md · resolved_tickets.json
│                   resolved_board.html · audit_trail.json · github_url.txt · (evidence files)
├── docs/database.md
├── scripts/screenshot.py
└── screenshots/
```
