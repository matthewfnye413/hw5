"""Campus Customs MCP server (FastMCP).

Every agent on the team (Boss, Inventory, Accounting, Facilities, Customer Service)
gets its shop abilities from the tools here. All tools use data/campus_customs_new.db.

Rules built into the tools (not just the prompts):
  * Never invent data. Only return what is in the database; unknown ids are errors.
  * 'Today' is desk.date_today, never the computer clock.
  * Money: amounts come from the database (invoice, lease, pricing), never from the
    agent. A payment can only run after a HUMAN approved it (decide_approval, which
    the agents are not given), and it is refused if cash would go negative.
  * A vendor with an open unpaid invoice cannot get a new purchase order.
  * Customer messages are saved as drafts only. Nothing is ever emailed or sent.

Run:  python mcp_server/server.py      (stdio transport)
"""

from __future__ import annotations

import json
from datetime import datetime

from fastmcp import FastMCP

try:  # run as a script (python mcp_server/server.py) or as a package
    from db import add_days, add_month, connect, days_between, one, rows, today
except ImportError:  # pragma: no cover
    from mcp_server.db import add_days, add_month, connect, days_between, one, rows, today

mcp = FastMCP(
    name="campus-customs",
    instructions=(
        "Tools for the Campus Customs shop. Data comes only from the shop database; "
        "never invent stock, prices, dates or balances. 'Today' is desk.date_today. "
        "Payments need a human-approved request; customer messages are drafts only."
    ),
)

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service"}
TICKET_STATUSES = ("open", "in_progress", "waiting_approval", "blocked", "resolved")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _open_invoices(conn, vendor_id: int) -> list[dict]:
    return rows(
        conn,
        "SELECT id, amount, due_date, description FROM invoices WHERE vendor_id = ? AND status = 'open'",
        (vendor_id,),
    )


def _approval(conn, approval_id: int) -> dict | None:
    a = one(conn, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
    if a and a.get("details"):
        a["details"] = json.loads(a["details"])
    return a


def _pending_duplicate(conn, kind: str, ref_id, ticket_id) -> dict | None:
    """An open (pending or approved, not yet paid) request that already covers this.

    Invoice and rent payments are matched on the bill itself (kind + invoice/lease id),
    whatever ticket asked, so two tickets can't queue the same $840 invoice twice.
    Discounts have no bill to match, so they stay one per ticket."""
    if kind in ("invoice", "rent"):
        return one(
            conn,
            """SELECT id, status, ticket_id FROM approvals WHERE kind = ? AND ref_id = ?
               AND status IN ('pending', 'approved') ORDER BY id LIMIT 1""",
            (kind, ref_id),
        )
    return one(
        conn,
        """SELECT id, status, ticket_id FROM approvals WHERE kind = ? AND IFNULL(ref_id, -1) = IFNULL(?, -1)
           AND IFNULL(ticket_id, -1) = IFNULL(?, -1) AND status IN ('pending', 'approved') ORDER BY id LIMIT 1""",
        (kind, ref_id, ticket_id),
    )


# --------------------------------------------------------------------------- tickets


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that is not resolved yet, plus the shop's 'today' date.

    Used by the Boss to read the work and decide who should handle each ticket.
    Each ticket includes its links (sku/size/qty, lease_id, invoice_id) so the right
    agent can look up the related rows. Reads: tickets, desk.
    """
    with connect() as conn:
        tickets = rows(
            conn,
            """SELECT id, type, requester, subject, sku, size, qty, lease_id,
                      invoice_id, status, notes, created_at
               FROM tickets WHERE status != 'resolved' ORDER BY created_at, id""",
        )
        return {"date_today": today(conn), "open_count": len(tickets), "tickets": tickets}


@mcp.tool
def list_tickets() -> dict:
    """List EVERY ticket (resolved too) with its status, plus 'today'.

    state is "resolved" when status = resolved, otherwise "open" (open, in_progress,
    waiting_approval and blocked all still need work). Used by the dashboard board.
    Reads: tickets, desk.
    """
    with connect() as conn:
        tickets = rows(
            conn,
            """SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id,
                      status, notes, created_at FROM tickets ORDER BY id""",
        )
        for t in tickets:
            t["state"] = "resolved" if t["status"] == "resolved" else "open"
        return {
            "date_today": today(conn),
            "tickets": tickets,
            "open": sum(t["state"] == "open" for t in tickets),
            "resolved": sum(t["state"] == "resolved" for t in tickets),
        }


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket with the rows it links to (stock, pricing, invoice, lease) and
    any approvals or customer drafts already made for it. Reads: tickets, inventory,
    pricing, invoices, vendors, leases, approvals, customer_drafts, desk.
    """
    with connect() as conn:
        t = one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if not t:
            ids = [r["id"] for r in rows(conn, "SELECT id FROM tickets ORDER BY id")]
            return {"error": f"No ticket {ticket_id}.", "known_ticket_ids": ids}
        linked: dict = {}
        if t["sku"]:
            linked["stock"] = one(
                conn, "SELECT size, qty, location FROM inventory WHERE sku = ? AND size = ?", (t["sku"], t["size"])
            )
            linked["pricing"] = one(conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (t["sku"],))
        if t["invoice_id"]:
            linked["invoice"] = one(
                conn,
                """SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id
                   WHERE i.id = ?""",
                (t["invoice_id"],),
            )
        if t["lease_id"]:
            linked["lease"] = one(conn, "SELECT * FROM leases WHERE id = ?", (t["lease_id"],))
        linked["approvals"] = rows(
            conn, "SELECT id, kind, amount, status, decided_by FROM approvals WHERE ticket_id = ?", (ticket_id,)
        )
        linked["customer_drafts"] = rows(
            conn, "SELECT id, to_name, subject, created_at FROM customer_drafts WHERE ticket_id = ?", (ticket_id,)
        )
        return {"date_today": today(conn), "ticket": t, "linked": linked}


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, note: str, updated_by: str) -> dict:
    """Move a ticket to a new status and add a dated note explaining why.

    Args:
        ticket_id: the ticket to update.
        status: one of open, in_progress, waiting_approval, blocked, resolved.
        note: one or two sentences on what was done or what is blocking it.
        updated_by: the agent making the change, e.g. "boss".
    Only mark 'resolved' when the work is truly done (e.g. paid, or the customer
    reply is drafted and nothing else is pending). Writes: tickets.
    """
    status = status.strip().lower()
    if status not in TICKET_STATUSES:
        return {"error": f"Status must be one of {list(TICKET_STATUSES)}."}
    with connect() as conn:
        t = one(conn, "SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,))
        if not t:
            return {"error": f"No ticket {ticket_id}."}
        stamp = f"[{today(conn)} {updated_by}] {note.strip()}"
        notes = f"{t['notes']}\n{stamp}" if t["notes"] else stamp
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
        return {"ticket_id": ticket_id, "old_status": t["status"], "new_status": status, "note_added": stamp}


# --------------------------------------------------------------------------- inventory


@mcp.tool
def check_stock(sku: str, size: str | None = None) -> dict:
    """Check stock for a SKU, either one size or all sizes.

    Args:
        sku: product SKU exactly as stored, e.g. "CC-TEE-WHITE".
        size: optional size, e.g. "S", "M", "L", "XL" or "OS" (one size).
            Leave empty to get every size for the SKU.

    Returns the quantity on hand and shelf location per size, plus the total.
    Used by Inventory to spot shortfalls. A missing SKU or size is an error, not 0.
    Reads: inventory.
    """
    sku = sku.strip().upper()
    with connect() as conn:
        if size:
            size = size.strip().upper()
            found = rows(
                conn,
                "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
                (sku, size),
            )
        else:
            found = rows(
                conn,
                "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid",
                (sku,),
            )
        if not found:
            known = [r["sku"] for r in rows(conn, "SELECT DISTINCT sku FROM inventory ORDER BY sku")]
            what = f"{sku} size {size}" if size else sku
            return {"error": f"No inventory row for {what}.", "known_skus": known}
        return {
            "sku": sku,
            "name": found[0]["name"],
            "sizes": [{"size": r["size"], "qty": r["qty"], "location": r["location"]} for r in found],
            "total_qty": sum(r["qty"] for r in found),
        }


@mcp.tool
def list_vendors(specialty: str | None = None) -> dict:
    """List vendors with lead time and whether they can ship right now.

    Args:
        specialty: optional word to filter on, e.g. "apparel" or "mugs".

    can_ship is false when the vendor still has an open unpaid invoice (shop rule:
    no new product until it is paid). expected_arrival_if_ordered_today uses
    desk.date_today + lead_days. Reads: vendors, invoices, desk.
    """
    with connect() as conn:
        t = today(conn)
        if specialty:
            vs = rows(conn, "SELECT * FROM vendors WHERE specialty LIKE ? ORDER BY id", (f"%{specialty.strip()}%",))
        else:
            vs = rows(conn, "SELECT * FROM vendors ORDER BY id")
        out = []
        for v in vs:
            inv = _open_invoices(conn, v["id"])
            out.append(
                {
                    **v,
                    "open_invoices": inv,
                    "open_invoice_total": round(sum(i["amount"] for i in inv), 2),
                    "can_ship": not inv,
                    "expected_arrival_if_ordered_today": add_days(t, v["lead_days"]),
                }
            )
        if not out:
            return {"error": f"No vendor matches specialty '{specialty}'.", "date_today": t}
        return {"date_today": t, "vendors": out}


# --------------------------------------------------------------------------- money: read


@mcp.tool
def get_cash_balance(account: str | None = None) -> dict:
    """Get the cash on hand, for one account or all of them.

    Args:
        account: optional account name, e.g. "checking". Leave empty for every account.

    Used by Accounting before preparing any payment. A payment larger than the
    balance must be refused (no negative balances, and no money comes in).
    Reads: cash_accounts, desk.
    """
    with connect() as conn:
        if account:
            found = rows(
                conn,
                "SELECT name, balance, date FROM cash_accounts WHERE name = ?",
                (account.strip().lower(),),
            )
            if not found:
                known = [r["name"] for r in rows(conn, "SELECT name FROM cash_accounts")]
                return {"error": f"No cash account named '{account}'.", "known_accounts": known}
        else:
            found = rows(conn, "SELECT name, balance, date FROM cash_accounts ORDER BY name")
        return {
            "date_today": today(conn),
            "accounts": found,
            "total_balance": round(sum(r["balance"] for r in found), 2),
        }


@mcp.tool
def list_invoices(status: str | None = None, vendor_id: int | None = None) -> dict:
    """List vendor invoices with how overdue each one is.

    Args:
        status: optional, e.g. "open" or "paid".
        vendor_id: optional vendor to filter on.

    days_overdue is counted from due_date to desk.date_today (0 if not yet due).
    Reads: invoices, vendors, desk.
    """
    with connect() as conn:
        t = today(conn)
        sql = """SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, i.status, i.description
                 FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE 1=1"""
        params: list = []
        if status:
            sql += " AND i.status = ?"
            params.append(status.strip().lower())
        if vendor_id is not None:
            sql += " AND i.vendor_id = ?"
            params.append(vendor_id)
        found = rows(conn, sql + " ORDER BY i.due_date", tuple(params))
        for i in found:
            late = days_between(i["due_date"], t)
            i["days_overdue"] = max(late, 0) if i["status"] == "open" else 0
            i["overdue"] = i["status"] == "open" and late > 0
        return {
            "date_today": t,
            "invoices": found,
            "open_total": round(sum(i["amount"] for i in found if i["status"] == "open"), 2),
        }


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Get a lease: space, landlord, monthly rent, next due date and days until due.

    Used by Facilities on rent tickets. Reads: leases, desk.
    """
    with connect() as conn:
        t = today(conn)
        lease = one(conn, "SELECT * FROM leases WHERE id = ?", (lease_id,))
        if not lease:
            ids = [r["id"] for r in rows(conn, "SELECT id FROM leases")]
            return {"error": f"No lease {lease_id}.", "known_lease_ids": ids}
        until = days_between(t, lease["next_due"])
        return {
            "date_today": t,
            "lease": lease,
            "days_until_due": until,
            "overdue": until < 0,
            "rent_paid_this_cycle": bool(
                one(
                    conn,
                    "SELECT id FROM payments WHERE kind = 'rent' AND ref_id = ? AND paid_at >= ?",
                    (lease_id, add_days(lease["next_due"], -31)),
                )
            ),
        }


@mcp.tool
def get_pricing(sku: str, proposed_unit_price: float | None = None, qty: int | None = None) -> dict:
    """Get cost, list price and margin for a SKU, and test a proposed (discounted) price.

    Args:
        sku: product SKU, e.g. "CC-HOOD-NAVY".
        proposed_unit_price: optional price per unit to evaluate, e.g. a bulk discount.
        qty: optional quantity, to get order totals.

    Returns margin per unit and %, the discount % vs list, totals, and below_cost
    (a price under unit_cost loses money and must not be offered). Reads: pricing.
    """
    sku = sku.strip().upper()
    with connect() as conn:
        p = one(conn, "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
        if not p:
            known = [r["sku"] for r in rows(conn, "SELECT sku FROM pricing ORDER BY sku")]
            return {"error": f"No pricing for {sku}.", "known_skus": known}
        cost, lst = p["unit_cost"], p["list_price"]
        out = {
            **p,
            "list_margin_per_unit": round(lst - cost, 2),
            "list_margin_pct": round((lst - cost) / lst * 100, 1),
        }
        if proposed_unit_price is not None:
            pp = float(proposed_unit_price)
            out["proposed"] = {
                "unit_price": pp,
                "discount_pct_vs_list": round((lst - pp) / lst * 100, 1),
                "margin_per_unit": round(pp - cost, 2),
                "margin_pct": round((pp - cost) / pp * 100, 1) if pp else None,
                "below_cost": pp < cost,
            }
        if qty:
            out["qty"] = qty
            out["order_total_at_list"] = round(lst * qty, 2)
            out["order_cost"] = round(cost * qty, 2)
            if proposed_unit_price is not None:
                out["order_total_at_proposed"] = round(float(proposed_unit_price) * qty, 2)
                out["order_margin_at_proposed"] = round((float(proposed_unit_price) - cost) * qty, 2)
        return out


# --------------------------------------------------------------------------- approvals


@mcp.tool
def request_payment_approval(kind: str, ref_id: int, reason: str, requested_by: str,
                             ticket_id: int | None = None) -> dict:
    """Ask a human to approve paying an invoice or rent. Does NOT pay anything.

    Args:
        kind: "invoice" (ref_id = invoices.id) or "rent" (ref_id = leases.id).
        ref_id: the invoice or lease id.
        reason: why it should be paid now (e.g. overdue, blocks a restock, due in 2 days).
        requested_by: the agent asking, e.g. "accounting".
        ticket_id: the ticket this unblocks, if any.

    The amount and payee are read from the database, never taken from the agent.
    Also reports whether cash covers it. Writes: approvals. Reads: invoices, leases,
    vendors, cash_accounts.
    """
    kind = kind.strip().lower()
    with connect() as conn:
        t = today(conn)
        if kind == "invoice":
            inv = one(
                conn,
                "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ref_id,),
            )
            if not inv:
                return {"error": f"No invoice {ref_id}."}
            if inv["status"] != "open":
                return {"error": f"Invoice {ref_id} is '{inv['status']}', not open; nothing to pay."}
            amount, payee = inv["amount"], inv["vendor_name"]
            details = {"vendor_id": inv["vendor_id"], "due_date": inv["due_date"],
                       "days_overdue": max(days_between(inv["due_date"], t), 0),
                       "description": inv["description"]}
        elif kind == "rent":
            lease = one(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            if not lease:
                return {"error": f"No lease {ref_id}."}
            amount, payee = lease["monthly_rent"], lease["landlord"]
            details = {"space": lease["space_name"], "due_date": lease["next_due"],
                       "days_until_due": days_between(t, lease["next_due"])}
        else:
            return {"error": "kind must be 'invoice' or 'rent'. Use request_purchase_order for restocks."}
        dup = _pending_duplicate(conn, kind, ref_id, ticket_id)
        if dup:
            asked_by = f" (requested for ticket {dup['ticket_id']})" if dup["ticket_id"] else ""
            return {"error": f"Approval #{dup['id']} for this {kind} already exists{asked_by} and is "
                             f"{dup['status']}. Don't create another; refer to #{dup['id']}.",
                    "approval_id": dup["id"], "existing_status": dup["status"]}
        cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()["balance"]
        cur = conn.execute(
            """INSERT INTO approvals (ticket_id, kind, ref_id, payee, amount, details, reason, requested_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, kind, ref_id, payee, amount, json.dumps(details), reason, requested_by, _now()),
        )
        return {
            "approval_id": cur.lastrowid, "status": "pending", "kind": kind, "payee": payee,
            "amount": amount, "details": details, "checking_balance": cash,
            "cash_covers_it": cash >= amount, "balance_after_if_paid": round(cash - amount, 2),
            "next_step": "Wait for a human to approve this on the dashboard. Do not call pay until approved.",
        }


@mcp.tool
def request_purchase_order(sku: str, size: str, qty: int, vendor_id: int, reason: str,
                           requested_by: str, ticket_id: int | None = None) -> dict:
    """Prepare a restock purchase order for human approval. Does NOT order or pay.

    Refused if the vendor still has an open unpaid invoice (they will not ship).
    Cost = qty x pricing.unit_cost; expected arrival = today + vendor lead_days
    (counted from approval). Writes: approvals. Reads: inventory, pricing, vendors,
    invoices, cash_accounts.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    if qty <= 0:
        return {"error": "qty must be positive."}
    with connect() as conn:
        t = today(conn)
        if not one(conn, "SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)):
            return {"error": f"No inventory row for {sku} size {size}."}
        price = one(conn, "SELECT unit_cost FROM pricing WHERE sku = ?", (sku,))
        vendor = one(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if not price or not vendor:
            return {"error": "Unknown SKU pricing or vendor."}
        blocking = _open_invoices(conn, vendor_id)
        if blocking:
            return {
                "error": f"{vendor['name']} has open unpaid invoice(s); they will not ship until paid.",
                "blocked_by_invoices": blocking,
                "next_step": "Get the invoice approved and paid first, then request the PO again.",
            }
        amount = round(qty * price["unit_cost"], 2)
        details = {"sku": sku, "size": size, "qty": qty, "unit_cost": price["unit_cost"],
                   "vendor_id": vendor_id, "lead_days": vendor["lead_days"],
                   "expected_arrival_if_approved_today": add_days(t, vendor["lead_days"])}
        cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()["balance"]
        cur = conn.execute(
            """INSERT INTO approvals (ticket_id, kind, ref_id, payee, amount, details, reason, requested_by, created_at)
               VALUES (?, 'purchase_order', NULL, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, vendor["name"], amount, json.dumps(details), reason, requested_by, _now()),
        )
        return {"approval_id": cur.lastrowid, "status": "pending", "payee": vendor["name"], "amount": amount,
                "details": details, "checking_balance": cash, "cash_covers_it": cash >= amount,
                "next_step": "Wait for a human to approve this on the dashboard."}


@mcp.tool
def request_discount_approval(ticket_id: int, sku: str, qty: int, unit_price: float, reason: str,
                              requested_by: str) -> dict:
    """Ask a human to approve a discounted price for a customer. No money moves.

    Refused if the price is below unit cost. amount = qty x unit_price (the quote).
    Writes: approvals. Reads: pricing, tickets.
    """
    sku = sku.strip().upper()
    with connect() as conn:
        if not one(conn, "SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)):
            return {"error": f"No ticket {ticket_id}."}
        p = one(conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
        if not p:
            return {"error": f"No pricing for {sku}."}
        if unit_price < p["unit_cost"]:
            return {"error": f"${unit_price:.2f} is below unit cost ${p['unit_cost']:.2f}; refused."}
        dup = _pending_duplicate(conn, "discount", None, ticket_id)
        if dup:
            return {"error": f"Discount approval #{dup['id']} already exists ({dup['status']}).",
                    "approval_id": dup["id"]}
        requester = conn.execute("SELECT requester FROM tickets WHERE id = ?", (ticket_id,)).fetchone()[0]
        details = {"sku": sku, "qty": qty, "unit_price": unit_price, "list_price": p["list_price"],
                   "unit_cost": p["unit_cost"],
                   "discount_pct": round((p["list_price"] - unit_price) / p["list_price"] * 100, 1),
                   "margin_per_unit": round(unit_price - p["unit_cost"], 2)}
        cur = conn.execute(
            """INSERT INTO approvals (ticket_id, kind, ref_id, payee, amount, details, reason, requested_by, created_at)
               VALUES (?, 'discount', NULL, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, requester, round(qty * unit_price, 2), json.dumps(details), reason, requested_by, _now()),
        )
        return {"approval_id": cur.lastrowid, "status": "pending", "quote_total": round(qty * unit_price, 2),
                "details": details, "next_step": "Wait for a human to approve the discount."}


@mcp.tool
def list_approvals(status: str | None = None, ticket_id: int | None = None) -> dict:
    """List approval requests (pending, approved, rejected, paid). Reads: approvals."""
    with connect() as conn:
        sql, params = "SELECT * FROM approvals WHERE 1=1", []
        if status:
            sql += " AND status = ?"
            params.append(status.strip().lower())
        if ticket_id is not None:
            sql += " AND ticket_id = ?"
            params.append(ticket_id)
        found = rows(conn, sql + " ORDER BY id", tuple(params))
        for a in found:
            a["details"] = json.loads(a["details"]) if a["details"] else None
        return {"approvals": found}


@mcp.tool
def decide_approval(approval_id: int, decision: str, human_name: str) -> dict:
    """HUMAN ONLY: approve or reject a request. Called by the dashboard, never by an agent
    (the backend does not give this tool to the agents). Writes: approvals.
    """
    decision = decision.strip().lower()
    if decision not in ("approve", "reject"):
        return {"error": "decision must be 'approve' or 'reject'."}
    if not human_name.strip() or human_name.strip().lower() in AGENT_NAMES:
        return {"error": "A named human must decide; agents cannot approve."}
    with connect() as conn:
        a = _approval(conn, approval_id)
        if not a:
            return {"error": f"No approval {approval_id}."}
        if a["status"] != "pending":
            return {"error": f"Approval {approval_id} is already {a['status']}."}
        new = "approved" if decision == "approve" else "rejected"
        conn.execute("UPDATE approvals SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
                     (new, human_name.strip(), _now(), approval_id))
        return {"approval_id": approval_id, "status": new, "decided_by": human_name.strip()}


# --------------------------------------------------------------------------- money: pay


@mcp.tool
def pay_approved_request(approval_id: int, account: str = "checking") -> dict:
    """Pay an invoice, rent or purchase order that a HUMAN has already approved.

    Refused unless the approval status is 'approved' with a named human decider.
    Refused if the account balance is lower than the amount (no negative balances).
    On success, in one transaction: inserts a payments row (approved_by = the human),
    lowers cash_accounts.balance, and marks the invoice paid / moves the lease's
    next_due forward one month / records the PO arrival date.
    Writes: payments, cash_accounts, invoices, leases, approvals.
    """
    with connect() as conn:
        a = _approval(conn, approval_id)
        if not a:
            return {"error": f"No approval {approval_id}."}
        if a["kind"] == "discount":
            return {"error": "Discounts are approvals only; there is nothing to pay."}
        if a["status"] != "approved" or not a["decided_by"]:
            return {"error": f"Refused: approval {approval_id} is '{a['status']}'. A human must approve it first."}
        acct = one(conn, "SELECT name, balance FROM cash_accounts WHERE name = ?", (account,))
        if not acct:
            return {"error": f"No cash account '{account}'."}
        if acct["balance"] < a["amount"]:
            return {"error": f"Refused: {account} has ${acct['balance']:.2f}, payment is ${a['amount']:.2f}. "
                             "No negative balances.", "shortfall": round(a["amount"] - acct["balance"], 2)}
        t = today(conn)
        effects = {}
        if a["kind"] == "invoice":
            inv = one(conn, "SELECT status FROM invoices WHERE id = ?", (a["ref_id"],))
            if not inv or inv["status"] != "open":
                return {"error": f"Invoice {a['ref_id']} is not open."}
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (a["ref_id"],))
            effects["invoice"] = {"id": a["ref_id"], "status": "paid"}
        elif a["kind"] == "rent":
            lease = one(conn, "SELECT next_due FROM leases WHERE id = ?", (a["ref_id"],))
            nxt = add_month(lease["next_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (nxt, a["ref_id"]))
            effects["lease"] = {"id": a["ref_id"], "paid_period_due": lease["next_due"], "next_due": nxt}
        elif a["kind"] == "purchase_order":
            d = a["details"]
            if _open_invoices(conn, d["vendor_id"]):
                return {"error": "Refused: vendor has an open unpaid invoice again; pay that first."}
            d["ordered_on"] = t
            d["expected_arrival"] = add_days(t, d["lead_days"])
            conn.execute("UPDATE approvals SET details = ? WHERE id = ?", (json.dumps(d), approval_id))
            effects["purchase_order"] = {"expected_arrival": d["expected_arrival"]}
        new_bal = round(acct["balance"] - a["amount"], 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_bal, t, account))
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (a["kind"], a["ref_id"] if a["ref_id"] is not None else approval_id, a["amount"], account, t, a["decided_by"]),
        )
        conn.execute("UPDATE approvals SET status = 'paid' WHERE id = ?", (approval_id,))
        return {"payment_id": cur.lastrowid, "approval_id": approval_id, "paid": a["amount"], "payee": a["payee"],
                "approved_by": a["decided_by"], "account": account, "balance_after": new_bal, "effects": effects}


# --------------------------------------------------------------------------- customer drafts


@mcp.tool
def save_customer_draft(ticket_id: int, to_name: str, subject: str, body: str, drafted_by: str) -> dict:
    """Save a message to a customer as a DRAFT on the board. It is never emailed or sent;
    a human reviews it. Writes: customer_drafts. Reads: tickets.
    """
    with connect() as conn:
        if not one(conn, "SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)):
            return {"error": f"No ticket {ticket_id}."}
        cur = conn.execute(
            """INSERT INTO customer_drafts (ticket_id, to_name, subject, body, drafted_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticket_id, to_name, subject, body, drafted_by, _now()),
        )
        return {"draft_id": cur.lastrowid, "status": "draft", "sent": False,
                "note": "Saved to the board only. Nothing was emailed."}


@mcp.tool
def list_customer_drafts(ticket_id: int | None = None) -> dict:
    """List saved customer message drafts. Reads: customer_drafts."""
    with connect() as conn:
        if ticket_id is None:
            return {"drafts": rows(conn, "SELECT * FROM customer_drafts ORDER BY id")}
        return {"drafts": rows(conn, "SELECT * FROM customer_drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))}


if __name__ == "__main__":
    mcp.run()
