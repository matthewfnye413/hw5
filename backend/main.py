"""Campus Customs Multi-Agent Operations: FastAPI backend for the React dashboard.

Shop facts and every database change go through the campus-customs MCP server
(backend/mcp_tools.py). Agents only PREPARE payments; the approve route is the one
place a payment actually runs and cash changes, and only after a person clicks Approve.

Run (from the backend/ folder):
    uvicorn main:app --reload --port 8000
or from the project root:
    uvicorn backend.main:app --port 8000
"""

from __future__ import annotations

import sys
from pathlib import Path

# Started from backend/ (uvicorn main:app), the project root isn't on the import path,
# so `import backend.*` would fail. Add it so both ways of starting work.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import asyncio  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from datetime import datetime  # noqa: E402

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend import audit
from backend.llm import MODEL_NAME
from backend.mcp_tools import AGENT_NAMES_LOWER, shop_mcp
from backend.team import new_run_id, run_ticket

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"
# Each reset appends {time, audit_index} here. The audit trail itself is never wiped, so the
# board uses the latest audit_index to show only agent activity since the last reset.
RESET_LOG = ROOT / "output" / "reset_log.json"


def _resets() -> list[dict]:
    try:
        return json.loads(RESET_LOG.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _last_reset_index() -> int:
    r = _resets()
    return r[-1]["audit_index"] if r else 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with shop_mcp:  # one MCP server process for the life of the API
        yield


app = FastAPI(title="Campus Customs Multi-Agent Operations", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # Only the Vite dashboard page may call these routes from a browser.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Agent runs started from the dashboard (kept in memory; the audit trail is the permanent record).
RUNS: dict[str, dict] = {}
_run_lock = asyncio.Lock()  # one team run at a time: keeps tokens in check and avoids DB races


async def mcp(tool: str, **args) -> dict:
    """Call one campus-customs MCP tool and turn a tool error into an HTTP error."""
    try:
        result = await shop_mcp.direct_call_tool(tool, args)
    except Exception as exc:  # MCP/tool failure
        raise HTTPException(502, f"MCP tool {tool} failed: {exc}") from exc
    return result


def _busy() -> dict | None:
    return next((r for r in RUNS.values() if r["status"] == "running"), None)


# --------------------------------------------------------------------------- 1. tickets


@app.get("/api/tickets")
async def list_tickets():
    """The three tickets, each with its raw status and open/resolved state."""
    board = await mcp("list_tickets")
    for t in board["tickets"]:
        active = next((r for r in RUNS.values() if r["ticket_id"] == t["id"] and r["status"] == "running"), None)
        t["agent_run"] = active["run_id"] if active else None
    return board


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    """One ticket with its linked rows, approvals and drafts."""
    out = await mcp("get_ticket", ticket_id=ticket_id)
    if "error" in out:
        raise HTTPException(404, out["error"])
    return out


# --------------------------------------------------------------------------- 2. run the team


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_team(ticket_id: int):
    """Start the agent team on one ticket. Returns at once with a run_id; watch progress
    with GET /api/events?run_id=... and the result with GET /api/runs/{run_id}."""
    ticket = await mcp("get_ticket", ticket_id=ticket_id)
    if "error" in ticket:
        raise HTTPException(404, ticket["error"])
    if busy := _busy():
        raise HTTPException(409, f"The team is already working ticket {busy['ticket_id']} (run {busy['run_id']}).")
    run_id = new_run_id()
    RUNS[run_id] = {
        "run_id": run_id, "ticket_id": ticket_id, "status": "running", "model": MODEL_NAME,
        "started_at": datetime.now().isoformat(timespec="seconds"), "finished_at": None,
        "decision": None, "tokens": None, "requests": None, "tool_calls": None, "error": None,
        "audit_start": audit.count(),
    }

    async def work():
        async with _run_lock:
            run = RUNS[run_id]
            try:
                decision, usage = await run_ticket(ticket_id, run_id=run_id)
                run.update(status="done", decision=decision.model_dump(), tokens=usage.total_tokens,
                           requests=usage.requests, tool_calls=usage.tool_calls)
                # The team's work on this ticket is finished, so the board marks it resolved.
                # Anything still waiting on a person stays in the approval queue and is noted here.
                pending = ", ".join(f"#{a}" for a in decision.approvals_pending) or "none"
                await mcp(
                    "update_ticket_status", ticket_id=ticket_id, status="resolved", updated_by="dashboard",
                    note=f"Agent run {run_id} finished (Boss set '{decision.final_status}'). "
                         f"Human approvals still pending: {pending}.",
                )
                run["boss_status"] = decision.final_status
            except Exception as exc:
                run.update(status="error", error=f"{type(exc).__name__}: {exc}")
            finally:
                run["finished_at"] = datetime.now().isoformat(timespec="seconds")

    RUNS[run_id]["task"] = asyncio.create_task(work())
    return {k: v for k, v in RUNS[run_id].items() if k != "task"}


@app.get("/api/runs")
async def list_runs():
    return [{k: v for k, v in r.items() if k != "task"} for r in RUNS.values()]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id}.")
    return {k: v for k, v in RUNS[run_id].items() if k != "task"}


# --------------------------------------------------------------------------- 3. agent events


def _said(entry: dict) -> str | None:
    """Turn one audit step into a line the board can show: what the agent said or did."""
    calls = entry.get("tool_calls") or []
    for c in calls:
        args = c.get("args") if isinstance(c.get("args"), dict) else {}
        if c["tool"].startswith("final_result"):
            return args.get("decision") or args.get("summary") or "Finished."
        if c["tool"] == "delegate":
            return f"Asked {args.get('to')}: {args.get('task')}"
    if entry.get("node") == "UserPrompt":
        return f"Got task: {entry.get('text_preview')}"
    if entry.get("error"):
        return f"Error: {entry['error']}"
    return entry.get("text_preview")


@app.get("/api/events")
async def events(
    since: int = Query(0, ge=0, description="Return events after this index (use next_since to poll)."),
    run_id: str | None = None,
    ticket_id: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
    current: bool = Query(False, description="Only events since the last database reset."),
):
    """Recent agent events from the append-only audit trail: who said what and which tools
    they used. Poll with since=<next_since> so the board only fetches new events."""
    with audit._lock:
        trail = audit._load()
    if current:
        since = max(since, _last_reset_index())
    out = []
    for i, e in enumerate(trail[since:], start=since):
        if run_id and e.get("run_id") != run_id:
            continue
        if ticket_id is not None and e.get("ticket_id") != ticket_id:
            continue
        if e.get("node") in ("ModelRequest", "End"):  # tool returns / duplicate final: skip on the board
            continue
        out.append({
            "index": i, "run_id": e["run_id"], "ticket_id": e["ticket_id"], "agent": e["agent"],
            "called_by": e["called_by"], "depth": e["depth"], "step": e["step"], "node": e["node"],
            "timestamp": e["timestamp"], "said": _said(e),
            "tools": [{"tool": c["tool"], "args": c.get("args")} for c in (e.get("tool_calls") or [])
                      if not c["tool"].startswith("final_result")],
            "stop_reason": e.get("stop_reason"), "tokens_so_far": e.get("run_total_tokens"),
        })
    return {"events": out[-limit:], "next_since": len(trail), "total": len(trail)}


# --------------------------------------------------------------------------- 4. approvals (the only place cash moves)


class Decision(BaseModel):
    approved_by: str = Field(min_length=2, description="The person clicking Approve/Reject.")


@app.get("/api/approvals")
async def approvals(status: str | None = None, ticket_id: int | None = None):
    args = {k: v for k, v in {"status": status, "ticket_id": ticket_id}.items() if v is not None}
    return await mcp("list_approvals", **args)


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: Decision):
    """A human approved a payment, purchase order or discount. For payments and POs this
    route then PAYS it: payments row, lower checking, invoice paid / lease moved / PO dated.
    Refused (and left pending) if checking can't cover it."""
    if body.approved_by.strip().lower() in AGENT_NAMES_LOWER:
        raise HTTPException(403, "Approvals must come from a named person, not an agent.")
    found = (await mcp("list_approvals"))["approvals"]
    a = next((x for x in found if x["id"] == approval_id), None)
    if not a:
        raise HTTPException(404, f"No approval {approval_id}.")
    if a["status"] != "pending":
        raise HTTPException(409, f"Approval {approval_id} is already {a['status']}.")
    if a["kind"] != "discount":
        cash = (await mcp("get_cash_balance", account="checking"))["accounts"][0]["balance"]
        if cash < a["amount"]:
            raise HTTPException(409, f"Not enough cash: checking ${cash:,.2f}, payment ${a['amount']:,.2f}. "
                                     "Left pending; nothing was paid.")
    decided = await mcp("decide_approval", approval_id=approval_id, decision="approve",
                        human_name=body.approved_by.strip())
    if "error" in decided:
        raise HTTPException(409, decided["error"])
    if a["kind"] == "discount":
        return {"approval": decided, "payment": None, "note": "Discount approved; no money moves."}
    paid = await mcp("pay_approved_request", approval_id=approval_id)
    if "error" in paid:
        raise HTTPException(409, paid["error"])
    cash = await mcp("get_cash_balance", account="checking")
    return {"approval": decided, "payment": paid, "checking": cash["accounts"][0]}


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: Decision):
    out = await mcp("decide_approval", approval_id=approval_id, decision="reject",
                    human_name=body.approved_by.strip())
    if "error" in out:
        raise HTTPException(409, out["error"])
    return out


# --------------------------------------------------------------------------- 5. cash


@app.get("/api/cash")
async def cash():
    """Current checking balance from cash_accounts."""
    out = await mcp("get_cash_balance", account="checking")
    acct = out["accounts"][0]
    return {"account": acct["name"], "balance": acct["balance"], "as_of": acct["date"], "date_today": out["date_today"]}


# --------------------------------------------------------------------------- extras for the board


@app.get("/api/drafts")
async def drafts(ticket_id: int | None = None):
    args = {"ticket_id": ticket_id} if ticket_id is not None else {}
    return await mcp("list_customer_drafts", **args)


@app.get("/api/health")
async def health():
    return {"ok": True, "model": MODEL_NAME, "db": str(WORKING_DB.relative_to(ROOT)), "audit_entries": audit.count()}


# --------------------------------------------------------------------------- 6. reset


@app.post("/api/reset")
async def reset():
    """Copy the untouched original database over the working copy for a fresh run.
    Approvals, drafts, payments and ticket statuses go back to the start. The audit
    trail is NOT wiped (it is append-only)."""
    if busy := _busy():
        raise HTTPException(409, f"Can't reset while the team is working ticket {busy['ticket_id']}.")
    async with _run_lock:
        shutil.copyfile(ORIGINAL_DB, WORKING_DB)
        resets = _resets()
        resets.append({"time": datetime.now().isoformat(timespec="seconds"), "audit_index": audit.count()})
        RESET_LOG.parent.mkdir(parents=True, exist_ok=True)
        RESET_LOG.write_text(json.dumps(resets, indent=2), encoding="utf-8")
    cash_now = await cash()
    board = await mcp("list_tickets")
    return {"reset": True, "from": ORIGINAL_DB.name, "to": WORKING_DB.name, "checking": cash_now["balance"],
            "tickets": [{"id": t["id"], "status": t["status"]} for t in board["tickets"]],
            "audit_entries_kept": audit.count()}
