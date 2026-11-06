# Campus Customs Ops Desk: design notes

The dashboard is a **desk**, not an admin panel. Someone at Campus Customs should be able to sit down with a coffee, see what's on the board, press one button, watch the team work, and sign off on money with confidence. Every choice below serves one of three jobs: **pick the work**, **watch the work**, **approve the money**.

## 1. Layout: three columns that match how a person reads the desk

| Column | What's there | Why |
|---|---|---|
| **Left: the board** (300 px) | The three tickets as cards: icon, ticket number, title, requester, the exact item ("20 × CC-HOOD-NAVY · size M") and a big **▶ Run agent team** button | This is the to-do list. You scan it top to bottom, pick one, and press go. The button lives on the card so there's no hunting. |
| **Center: the work** (flexible) | The ticket header, the **agent stage**, the **live conversation**, and after the run, **What each agent did** | The widest column holds what changes the most: the agents talking. |
| **Right: the money** (330 px) | **Checking balance** on top, **Needs your approval** under it | Money decisions sit apart from the agent chatter, always in the same spot, so a person never has to scroll to find what needs a signature. |

- The left and right columns are **sticky**, so the board and the cash stay in view while the conversation scrolls.
- At laptop widths the money column drops under the work as two cards side by side. On a phone everything stacks into one column.
- The **top bar** is the desk's status strip: shop date (`2026-08-31`, from `desk.date_today`), open/resolved count, checking, the model badge (`gpt-6-luna`) and **↺ Reset data**. Reset asks for confirmation and is disabled mid-run, so it can't be hit by accident.

## 2. How the agents read differently

Each agent has its **own color and two-letter badge**, used the same way everywhere: the stage, the conversation, the summary cards and the hand-off pills.

| Agent | Badge | Color | Why that color |
|---|---|---|---|
| Boss | **BO** | Yale navy `#00356b` | The shop's own color for the one who makes the final call |
| Inventory | **IN** | Teal `#0f7c7a` | Calm, warehouse-shelf color for counting stock |
| Accounting | **AC** | Amber `#a46b00` | Gold for money, but muted so it doesn't shout |
| Facilities | **FA** | Terracotta `#b5492f` | Brick and building, for the shop space |
| Customer Service | **CS** | Purple `#6b4fa3` | A warmer, human color for the agent that talks to people |

**The agent stage** sits across the top of the work column. All five agents appear as avatars, in one of three states:
- **Working:** the avatar glows with a soft pulsing halo, and "working…" shows under it.
- **On this ticket:** a light tint of the agent's color.
- **Not called:** greyed out and desaturated.

You can see at a glance that ticket 102 never involved Inventory, without reading a word. That matches the Problem 6 plan of not sending every specialist. Below the stage, **hand-off pills** ("Boss → Inventory", "Accounting → Inventory") show the delegation path.

**The conversation reads like a team chat, not a log file:**
- Each message is a bubble tinted in the agent's color, with its badge, name and a time stamp.
- **Delegations are indented** by depth and shown as a colored "→ Inventory" pill followed by the task. You can see who asked whom, and nested asks step further right.
- The **task an agent received** is a dashed, italic bubble labeled "asked by Boss", so it's clearly input, not something the agent said.
- **MCP tool calls are chips**, e.g. `check_stock sku=CC-HOOD-NAVY, size=M`. You see exactly which shop data each agent touched, and hovering shows the full arguments.
- The **final report** gets a stronger border and a green "✓ final report" tag.
- Three bouncing dots show the team is still thinking, and the feed scrolls itself (only inside its own box) to keep the newest message in view.

## 3. How resolved tickets show up

- **Ticket badges** change as the work moves: navy **OPEN**, then amber **● AGENTS WORKING** with a pulsing dot, then green **RESOLVED**. A resolved card gets a faint green wash, and its button changes to **↻ Run team again**.
- A **LIVE** marker blinks in the ticket header during a run. When it finishes, the token and tool-call counts appear, and a toast says "Ticket 103 resolved by the agent team."
- **What each agent did** appears once the run is over:
  - The **Boss's final call** is a dark navy card with the decision, the status the Boss recommended (e.g. `waiting_approval`), the cash at stake and the next steps. It's the first thing your eye lands on.
  - **One card per agent** follows, with a colored top stripe, its last report, which teammates it asked, and the tools it used.
  - **Customer drafts** sit on cream "paper" with a dashed border and a **DRAFT #2, NOT SENT** tag. They look like a letter waiting on your desk, not something that already went out.

## 4. How cash shows up

- **The balance is the biggest number on the page** (38 px, tabular figures so digits don't jump). Under it, a green bar shows how much of the starting cash is left, and a caption says "money only goes out", which is the shop rule for this homework.
- **When an approved payment lands**, the balance card flashes with a red ring, the number turns red for a moment, the top-bar figure tints, and a toast confirms: "Paid $840.00 to Bulldog Print Co. Checking is now $2,560.00." You *feel* money leave, which is the right reaction.
- **The ledger** under the balance lists each payment as payee, a red **−$840.00**, and "approved by <name>". There's always a person's name next to money that moved.
- **Approval cards** are warm amber "sticky notes", with a counter that pulses when something is waiting. Each one has:
  - the kind with an icon (🧾 invoice, 🏠 rent, 📦 purchase order, 🏷️ discount),
  - the amount in large type with the payee,
  - the agent's reason and who requested it,
  - green **Approve & pay** (just **Approve** for a discount, since no money moves) and a quiet **Reject**.
- **Guardrails you can see:**
  - The buttons stay disabled until an **"Approving as"** name is typed. The name is remembered on that browser.
  - If checking can't cover a request, the card turns pink with "Not enough cash: checking has $160.00", and Approve is disabled. The backend refuses it too.

## 5. The creative choices that make it feel special

1. **A desk, not a database.** The page background is a warm paper tone (`#f6f3ee`) instead of stark white, with white cards that sit on it like papers. Drafts look like letters and approvals look like sticky notes.
2. **The agents feel like coworkers.** Named avatars that light up when they're working, plus chat bubbles, make it easy and a little fun to watch the team pass work around. It's like watching colleagues through a glass wall.
3. **Motion only where it means something.** The working agent glows, messages rise in, the LIVE marker blinks, the approval counter pulses, and cash flashes when it drops. Nothing moves for decoration, and everything is turned off for people who set "reduce motion".
4. **Type with character.** Space Grotesk for headings and big numbers gives a modern ops-room feel. Inter keeps body text easy to read. JetBrains Mono marks anything that is real system data (tool names, SKUs, run ids).
5. **Yale-blue identity.** The navy gradient top bar and "CC" logo tie the desk to the Campus Customs storefront brand.
6. **Honesty built into the look.** "Not called", "not sent", "approved by", "money only goes out", "Not enough cash": the interface tells the truth about what the agents did and didn't do, so a person can trust it before clicking Approve.

## 6. How it connects

- The board calls the backend directly at **`http://localhost:8000`** (`VITE_API_URL` in `frontend/.env`, which defaults to that).
- The backend's CORS setting allows only the Vite page's origin, **`http://localhost:5173`** (and `127.0.0.1:5173`), for GET and POST. A request from any other origin is refused.
- It polls every **1.5 s** while agents are working and every **6 s** when idle, so it feels live without hammering the server.
- **Start:** `uvicorn main:app --reload --port 8000` in `backend/`, then `npm run dev` in `frontend/`, which opens the desk in the browser.
