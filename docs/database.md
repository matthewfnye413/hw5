# Campus Customs database: tables, fields, and the three open tickets

- **Source:** `data/campus_customs.db` is the original. Never write to it; it is the reset point.
- **Working copy:** `data/campus_customs_new.db`, a byte-for-byte copy (SHA-256 `23686a90…f360a` matches). The MCP server and the backend use only this file.
- **Reset:** copy `campus_customs.db` over `campus_customs_new.db` before every full run.

The database is small: 9 tables and 24 rows. **Today is 2026-08-31** (from `desk.date_today`).

## Tables and fields

### `desk`: the shop's clock (1 row)

| Field | Type | Value / meaning |
|---|---|---|
| `date_today` | TEXT | `2026-08-31`. This is "today" for every overdue or due-soon check. Never use the computer's clock. |
| `notes` | TEXT | Empty. A place for desk-level notes. |

### `tickets`: the work board (3 rows, all `open`)

| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Ticket number (101–103) |
| `type` | TEXT | `customer_order`, `rent_notice` or `price_override`. Tells the Boss which agent should handle it. |
| `requester` | TEXT | Who asked: a customer, the landlord, or a student org |
| `subject` | TEXT | Short title |
| `sku`, `size`, `qty` | TEXT/TEXT/INT | The product request. Links to `inventory` (sku+size) and `pricing` (sku). |
| `lease_id` | INTEGER FK → `leases.id` | Set on rent tickets |
| `invoice_id` | INTEGER FK → `invoices.id` | Set when a vendor bill blocks the ticket |
| `status` | TEXT | `open` now. The tools change it as tickets get resolved. |
| `notes` | TEXT | The request in the requester's words |
| `created_at` | TEXT | ISO timestamp with the -04:00 (Eastern) offset |

### `inventory`: stock by SKU and size (10 rows, PK = `sku`+`size`)

| SKU | Name | Size → qty | Location |
|---|---|---|---|
| `CC-HOOD-NAVY` | Basic Hoodie Big Yale | S 4 · M 8 · L 14 · XL 6 (32 total) | Aisle A |
| `CC-TEE-WHITE` | Classic Bulldog Tee | **S 0** · M 5 · L 3 · XL 2 | Aisle B |
| `CC-HAT-BLUE` | Yale Cap | OS 40 | Aisle C |
| `CC-MUG-CREST` | Crest Mug | **OS 0** | Aisle D |

`OS` means one size. Stock is per size: having 32 hoodies doesn't mean there are 20 in size M.

### `pricing`: cost and list price per SKU (4 rows)

| SKU | `unit_cost` | `list_price` | Margin per unit | Margin % |
|---|---|---|---|---|
| `CC-HOOD-NAVY` | $22.00 | $58.00 | $36.00 | 62% |
| `CC-TEE-WHITE` | $8.00 | $28.00 | $20.00 | 71% |
| `CC-HAT-BLUE` | $6.00 | $22.00 | $16.00 | 73% |
| `CC-MUG-CREST` | $3.50 | $14.00 | $10.50 | 75% |

Accounting uses this to check margin on discounts and to cost purchase orders.

### `vendors`: who can restock, and how fast (3 rows)

| id | Name | Specialty | `lead_days` |
|---|---|---|---|
| 1 | Bulldog Print Co | apparel reprint | 5 |
| 2 | Elm City Gifts | mugs and small goods | 3 |
| 3 | QuickShip CT | local courier | 1 |

Lead time comes from here: arrival date = date the order is placed (after any blocking invoice is paid) + `lead_days`. Apparel such as tees and hoodies maps to vendor 1, and the mug to vendor 2. QuickShip is a courier, not a product source.

### `invoices`: bills the shop owes (1 row)

| id | Vendor | Amount | `due_date` | `status` | Description |
|---|---|---|---|---|---|
| 501 | 1 Bulldog Print Co | $840.00 | 2026-08-28 | `open` | Rush reprint CC-TEE-WHITE S |

**Invoice 501 is 3 days overdue.** Shop rule: a vendor won't ship while it has an open unpaid invoice, so Bulldog Print Co is blocked until 501 is paid.

### `leases`: the shop space (1 row)

| id | Space | Landlord | `monthly_rent` | `next_due` |
|---|---|---|---|---|
| 1 | Chapel Street shop | Elm City Properties | $2,400.00 | 2026-09-02 (2 days from today) |

### `cash_accounts`: money available (1 row)

| name | balance | date |
|---|---|---|
| `checking` | **$3,400.00** | 2026-08-31 |

Cash only goes out in this homework. The pay tool must refuse any payment that would make the balance negative.

### `payments`: the payment ledger (0 rows)

| Field | Meaning |
|---|---|
| `id` | Payment number |
| `kind` | What was paid, e.g. `invoice`, `rent` or `purchase_order` |
| `ref_id` | The row it pays: an `invoices.id` or a `leases.id` (generic, no FK) |
| `amount`, `account` | How much, and from which `cash_accounts.name` |
| `paid_at` | Date paid (use `desk.date_today`) |
| `approved_by` | **NOT NULL: the human who approved it.** The schema itself requires human approval. |

A real payment touches three tables at once: it inserts into `payments`, lowers `cash_accounts.balance`, and marks the invoice `paid` (or moves `leases.next_due` forward a month).

## How the three open tickets link to other tables

```
101 customer_order ─ sku+size ─▶ inventory (TEE S = 0) ─▶ pricing
        └─ invoice_id 501 ─▶ invoices ─ vendor_id 1 ─▶ vendors (Bulldog Print Co, 5 days)
102 rent_notice ─ lease_id 1 ─▶ leases ($2,400 due 09-02) ─▶ cash_accounts ─▶ payments
103 price_override ─ sku+size ─▶ inventory (HOOD M = 8) ─▶ pricing (cost $22 / list $58)
        └─ restock (apparel) ─▶ vendors 1 ─▶ blocked by invoice 501
```

### Ticket 101: Tauhid Zaman needs one Bulldog Tee, size S

- **Inventory:** `CC-TEE-WHITE` size S has **0** in stock, so this can't be filled from the shelf.
- **Restock:** Bulldog Print Co (apparel, 5-day lead).
- **Blocked:** the ticket already links to **invoice 501** ($840, overdue since 08-28), which is the bill for the rush reprint of this exact tee. Bulldog won't ship until it's paid.
- **Path:** Accounting prepares the $840 payment → a human approves it → pay → Bulldog ships. The tee arrives around **2026-09-05** if paid today. Customer Service drafts a message to Tauhid with that date.
- **Agents:** Boss → Inventory → Accounting (+ human approval) → Customer Service.

### Ticket 102: Elm City Properties, rent due

- **Lease 1:** $2,400 due **2026-09-02**, 2 days from today. Not overdue yet, but due soon.
- **Path:** Facilities confirms the amount and due date → Accounting checks cash and prepares the payment → a human approves it → pay. The pay step inserts into `payments`, lowers checking, and moves `next_due` to 2026-10-02.
- **Agents:** Boss → Facilities → Accounting (+ human approval).

### Ticket 103: Yale AI Club wants 20 hoodies in size M at a bulk discount

- **Inventory:** `CC-HOOD-NAVY` size M has **8**, so **12 are short**. There are 32 hoodies across all sizes, but sizes can't be swapped.
- **Pricing:** list $58 vs cost $22. The full order at list price is $1,160. Any discount has to keep margin above cost; for example, 20% off is $46.40 per unit, still $24.40 of margin per unit.
- **Restock:** 12 more from Bulldog Print Co ≈ 12 × $22 = **$264 purchase order**, but Bulldog is blocked by invoice 501 too.
- **Path:** Inventory finds the shortfall → Accounting checks margin and suggests a discount the Boss approves → PO for 12 (after 501 is cleared) → Customer Service drafts the reply (8 now, 12 in about 5 days, or the full order on one date).
- **Agents:** Boss → Inventory → Accounting → Boss (final call on the discount) → Customer Service.

## The cash problem the agents must notice

| Outflow | Amount | Running checking |
|---|---|---|
| Start | | $3,400.00 |
| Invoice 501 (unblocks tickets 101 and 103) | −$840.00 | $2,560.00 |
| Rent, lease 1 (ticket 102) | −$2,400.00 | $160.00 |
| PO for 12 hoodies (ticket 103) | −$264.00 | **−$104.00 ✗** |

**Not everything can be paid.** Invoice 501 plus rent fits, with only $160 left. Adding the hoodie PO would overdraw the account, so the pay tool must refuse it, and no revenue comes in during this homework. The Boss has to choose. Rent is due 09-02 and the invoice is already overdue, so the likely plan is to pay both, leave the PO unpaid or partly filled, and tell the AI Club honestly.

## Notes for building the tools

- **Foreign keys** are declared but `PRAGMA foreign_keys` is **off** (0). The tools must check that a lease or invoice exists themselves, or turn the pragma on per connection.
- `inventory.sku` and `pricing.sku` have no FK between them; join on the `sku` text.
- Dates are ISO text strings, so they compare correctly as strings: `due_date < date_today` means overdue.
- `payments.approved_by` is NOT NULL, so a payment can't be written without a named approver. That enforces the human-approval rule.
