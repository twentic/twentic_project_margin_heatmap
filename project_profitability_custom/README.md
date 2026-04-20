# Project Profitability (`project_profitability_custom`)

> Odoo 18 · TwenTIC · LGPL-3

---

## What this module adds to the Odoo circuit

```
Sale Orders ──────────────┐
                          │  Revenue
                          ▼
                 ┌─────────────────────┐
Vendor Bills ───►│  project.project    │
                 │  (new fields)       │──► profitability_margin (%)
Purchase Orders ►│                     │──► profitability_level
                 │                     │──► profitability_margin_display
Timesheets ──────►│  (hr.analytic.line) │
                 └─────────────────────┘
```

The module **extends `project.project`** with three computed, stored fields
that consolidate financial data from four different Odoo sub-systems and
produce a single, colour-coded profitability indicator per project.

---

## Technical overview

### New fields on `project.project`

| Field | Type | Description |
|---|---|---|
| `profitability_margin` | Float (2 dp) | `(Revenue − Costs) / Revenue × 100` |
| `profitability_level` | Selection | Colour category (`negative / low / medium / good`) |
| `profitability_margin_display` | Char | Human-readable value e.g. `"42.3 %"` |

All three fields are `store=True` so they are queryable in filters and
group-bys without triggering a full recomputation on every read.

### Revenue calculation

```
Revenue = SUM(sale.order.amount_untaxed)
          WHERE order.project_id = this project
            AND order.state IN ('sale', 'done')
```

Requires: `sale_project` module (links `sale.order` to `project.project`).

### Cost calculation

Three independent cost components are summed:

#### 1. Vendor Bills cost
```
Vendor Bill cost = -SUM(account.move.amount_untaxed_signed)
                   WHERE move.move_type IN ('in_invoice', 'in_refund')
                     AND move.state = 'posted'
                     AND any move line has analytic_distribution[project_analytic_id]
```
`in_refund` (credit notes) automatically reduce the cost because
`amount_untaxed_signed` carries the correct accounting sign.

#### 2. Purchase Orders cost
```
PO cost = SUM(purchase.order.line.price_subtotal)
          WHERE order.state IN ('purchase', 'done')
            AND line.display_type = False
            AND line.analytic_distribution[project_analytic_id]
```

> **Note:** If a Purchase Order has already been invoiced (Vendor Bill
> exists for the same analytic account), both the PO and the Bill will be
> counted. This is by design — the PO represents committed spend and the
> Bill represents realised spend. Use filters or the recompute button to
> monitor the transition.

#### 3. Timesheet cost
```
Timesheet cost = SUM(line.unit_amount × line.employee_id.timesheet_cost)
                 WHERE line.project_id = this project
```

Uses `account.analytic.line` (timesheet entries) and
`hr.employee.timesheet_cost` from the `hr_timesheet` module.

### Margin formula

```python
if revenue > 0:
    margin = (revenue - total_costs) / revenue * 100
elif total_costs > 0:
    margin = -100.0   # costs with no revenue
else:
    margin = 0.0      # empty project
```

### Level categorisation

| Level | Colour | Range |
|---|---|---|
| `negative` | Grey / muted | margin < 0 % |
| `low` | Red / danger | 0 % ≤ margin < 20 % |
| `medium` | Yellow / warning | 20 % ≤ margin < 50 % |
| `good` | Green / success | margin ≥ 50 % |

### Automatic recomputation triggers (`@api.depends`)

The compute method is triggered automatically when:
- `analytic_account_id` changes on the project
- Any timesheet line is added, modified or deleted (`timesheet_ids`,
  `unit_amount`, `employee_id`, `employee_id.timesheet_cost`)

For Sale Orders, Vendor Bills and Purchase Orders there is no direct
ORM relation that allows an efficient `@api.depends` path. Use the
**Recompute** button (see User Manual) after modifying those records.

### Dependencies (`__manifest__.py`)

```python
'depends': ['project', 'sale_project', 'purchase', 'hr_timesheet']
```

---

## Installation

1. Copy the `project_profitability_custom` folder into your Odoo addons path.
2. Go to **Settings → Apps**, click **Update App List**.
3. Search for `Project Profitability` and click **Install**.

---

## User Manual

### Accessing the Profitability view

Navigate to:

```
Project  →  Reporting  →  Project Profitability
```

You will see a **list view** with all active projects and their
profitability data.

Use the **kanban toggle** (top-right icon) to switch to the kanban view,
which shows a colour ribbon on each project card.

---

### List view — understanding the columns

| Column | Description |
|---|---|
| **Project** | Project name (click to open the project form). |
| **Customer** | Partner linked to the project. |
| **Project Manager** | Responsible user. |
| **Stage** | Current project stage. |
| **Margin (%)** | Profitability margin. Positive = profitable. |
| **Profitability Level** | Colour badge summarising the margin category. |
| **Recompute** | Button to manually refresh the profitability for that row. |

Row colours follow the level:
- **Green** — Good (> 50 %)
- **Yellow** — Medium (20 – 50 %)
- **Red** — Low (0 – 20 %)
- **Grey** — Negative (< 0 %)

---

### Kanban view — ribbon colours

Each project card shows:
- A **coloured ribbon** in the top-right corner labelled with the level
  name (Good / Medium / Low / Negative).
- The **margin percentage** inside the card, coloured to match the level.
- Customer and Project Manager.

---

### Filtering projects by profitability

Use the **search bar** drop-down to filter:

| Filter | Shows |
|---|---|
| Good | Projects with margin ≥ 50 % |
| Medium | Projects with margin between 20 % and 50 % |
| Low | Projects with margin between 0 % and 20 % |
| Negative | Projects with negative margin |

---

### Grouping by Profitability Level

1. Click the search bar.
2. Open **Group By**.
3. Select **Profitability Level**.

Projects are now grouped into four buckets. The group totals visible in
the list view allow quick financial comparison across categories.

This **Group By** option is also available in the standard project list
(via `Project → All Projects`) because the module adds it to the base
project search view.

---

### Recomputing profitability

Profitability is **not** automatically refreshed when a Sale Order,
Vendor Bill or Purchase Order changes (only timesheet mutations trigger
automatic recomputation).

**To refresh manually:**

- **Single project** — click the `⟳ Recompute` button on the list row or
  open the project and call the action from the action menu.
- **Multiple projects** — tick the checkboxes in the list view, then
  click `⟳ Recompute` from the **Action** drop-down.

A green notification confirms how many projects were updated.

---

### Typical workflow

```
1. Create / confirm Sale Orders and link them to the project.
2. Record timesheet entries (costs update automatically).
3. Post Vendor Bills with the project's analytic account on the lines.
4. Confirm Purchase Orders with the project's analytic account on the lines.
5. Click Recompute to refresh the margin after steps 1, 3 or 4.
6. Monitor the Profitability Level badge — aim for Green (Good).
```

---

## Translations

The module ships with translations for:

| Language | File |
|---|---|
| Spanish | `i18n/es.po` |
| Catalan | `i18n/ca.po` |
| German | `i18n/de.po` |
| French | `i18n/fr.po` |
| Portuguese | `i18n/pt.po` |
| Italian | `i18n/it.po` |

To activate a translation go to **Settings → Translations → Languages**
and install the desired language. Odoo loads `.po` files automatically
on module installation/update.

---

## Known limitations

1. **Double-counting POs and Bills** — if a Purchase Order is fully billed
   the same amount will appear in both cost components. Consider disabling
   the PO cost component (override `_get_purchase_order_cost`) if your
   workflow always produces vendor bills.
2. **No real-time update for SO/Bills/POs** — changes to those documents
   require a manual recompute.
3. **Multi-currency** — the module sums monetary amounts without currency
   conversion. All documents should be in the company currency for accurate
   results.
4. **Analytic account required** — Vendor Bill and Purchase Order costs are
   only picked up if the project has an `analytic_account_id` assigned and
   the document lines carry that account in their `analytic_distribution`.
