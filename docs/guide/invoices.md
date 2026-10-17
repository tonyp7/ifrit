# Invoices

Users with the **billing** role turn a project's logged hours into invoices. Invoices are listed
under the **Invoices** icon in the navigation bar. An invoice starts as a **draft**, which can be
prepared, saved, duplicated and deleted. **Issuing** gives it a number and freezes it; an issued
invoice that turns out wrong is **voided**, never deleted.

Invoices can be started for **Active** projects of type **Time & Material** or **Capped T&M**.
Capped T&M is invoiced exactly like Time & Material: the cap is not checked.

## The list

The list shows the invoices, newest first, 50 per page. Void invoices are hidden unless you tick
**Void** in the **Status** filter.

| Column | Shows |
|---|---|
| Number | The invoice number; empty for a draft |
| Project | The project the invoice is for |
| Client | The Bill To name on the invoice |
| Billed for | The period whose hours were billed, for example `1–30 Sep 2026` |
| Status | Draft, Issued or Void |
| Total | In the invoice currency |
| Created | When the draft was created |
| Issued | The invoice date; hover it for the exact time it was issued |
| Due | The due date. On a draft with a payment terms preset, the preset's name, greyed out, until it is issued |

Click a column header to sort, and use **Project** to show one project's invoices. Click a row to
open the invoice. The row menu offers **Open**, **Duplicate** and, for a draft, **Delete**.

## Creating an invoice

Choose **+ New**. The form has five steps.

1. **Project.** Pick an Active Time & Material or Capped T&M project. Its currency and type are
   shown next to it; the invoice is always in the project's currency. Changing the project of an
   invoice that already has lines asks first, because the lines are cleared.
2. **Parties.** **Bill From** is filled in from the project's vendor and **Bill To** from its
   client: the trading name (or legal name) and an address. Bill From prefers the registered
   address, Bill To the billing address. When the company has several addresses, a dropdown lets
   you copy another one in. Every field stays editable, and changing the companies later never
   changes the invoice.
   - **Payee account**: the bank account the client should pay into. The vendor's primary account
     in the invoice currency is copied in, or its only account in that currency. Pick another one
     from the dropdown, edit the details, or clear them. The details are a copy: editing or
     deleting the vendor's account afterwards does not change the invoice.
   - **References**: the project's purchase orders, contract and other references are copied in.
     When the project has several values of one kind (several purchase orders, for example), pick
     the one this invoice is for. You can edit, remove and add references without changing the
     project.
   - **Payment terms**: pick a preset, a fixed date, or neither (see below).
3. **What to bill.** Tick the service lines to bill (all of them by default) and choose the period:
   **This month**, **Last month** (the default), **This week**, **Last week**, or any range in the
   calendar. Weeks run Monday to Sunday, like the timesheet.
4. **Generate.** **Generate line items** builds the lines from the hours logged in the period.
   Generating again replaces the lines, after asking.
5. **Line items.** Edit the lines, add more, and save with **Save draft**.

## How lines are generated

For each ticked service line, one line:

- **Description**: the service line's name and the period, for example
  `Senior developer — 1–30 Sep 2026`.
- **Quantity**: every hour logged on the line in the period, locked or not, by anyone, including
  consultants who have since left. Lines billed in **days** divide the hours by the
  **Standard Workday Length** an administrator sets under Configuration → General (8 hours by
  default), with up to 5 decimals. Lines billed **each** come out with quantity 0 for you to fill in.
- **Unit and unit price**: the service line's.

Lines with no hours in the period are left out, and a note says which. Generating never locks or
unlocks any hours. A generated line is a plain line: editing or removing the service line later
does not change the invoice.

## Editing lines

- Change the description, quantity, unit or unit price directly in the table. A quantity can have
  up to 5 decimals and a unit price up to 4.
- A **negative unit price** is how a discount or a correction is written.
- **+ Add line** adds a blank line, for expenses or a one-off fee.
- Reorder lines by dragging the grip at the start of each row, with the mouse, a long press on a
  touch screen, or the keyboard (focus the grip, press Space, move with the arrow keys, press Space
  again). The new order is saved with the draft.

Each line's amount is its quantity times its unit price, rounded to the currency's decimals. The
**Subtotal** and **Total** follow every change.

## Payment terms

| Preset | Due date |
|---|---|
| Due on Receipt | The invoice date |
| Net 7, 15, 30, 60 or 90 | The invoice date plus that many days |
| End of Month | The last day of the invoice date's month |
| End of Month + 15, 30, 60 or 90 | That last day plus that many days |

Days are calendar days. The invoice date is the day the invoice is issued, so on a draft the due
date of a preset is an estimate: the form shows the date it would be if the invoice were issued
today. A date picked in the calendar is a fixed date instead. An invoice has a preset or a fixed
date, never both.

## Warnings

Warnings never stop you from saving:

- **Unlocked hours**: some days in the period still have hours a manager has not locked, so the
  amounts could still change.
- **Zero-quantity line**: a line has quantity 0.
- **No payee account**: the invoice does not say which account to pay into.
- **Payee account currency**: the payee account is not in the invoice currency.
- **Inactive company**: the project's vendor or client has been deactivated.

## Issuing

**Issue** turns a draft into an invoice. Any unsaved changes are saved first, then a confirmation
shows:

- the **invoice date**: today, in the server's time zone (see
  [Time zone](../configuration.md#time-zone));
- the **due date**: worked out from the payment terms preset, or the fixed date you picked;
- the **number** it should receive, from the numbering an administrator set under
  Configuration → Invoices. It is the likely number: if someone else issues an invoice first, the
  next one is used;
- every warning, including a due date that would already be past.

Issuing needs at least one line, and the project must be **Active**. While a draft's project is
closed, back to draft or deleted, the draft shows a red banner and cannot be issued; it can still
be edited, saved, duplicated and deleted, and becomes issuable again once the project is Active.

Once issued, the invoice is **read-only** and keeps showing exactly what was sent, whatever
changes later: the parties' names and addresses, the vendor's and client's VAT, legal registration
and Peppol identifiers as they stood that day, the payee account details, the references, the
lines and amounts, the dates, and the document name (such as "Tax Invoice"). The due date reads
for example `13 Nov 2026 (Net 30)`.

If the number would already be in use, for example after the numbering format was changed,
issuing is refused and nothing changes; an administrator sets the next number under
Configuration → Invoices.

## Voiding

**Void** cancels an issued invoice, after a confirmation where you can give a reason. A void
invoice keeps its number and stays in the list, marked void, with who voided it, when and why. It
cannot be changed or deleted, and voiding cannot be undone. Voiding is not a credit note: to bill
again, create a new invoice, for example by duplicating the void one.

## Duplicate and delete

**Duplicate**, on any invoice, creates a new draft with everything the source has: project,
parties, period, lines, references, payment terms and payee account details. The copy has no
number and no invoice date, and takes the payment terms preset rather than the due date it gave.
It works even if the project is no longer Active.

**Delete** removes a draft for good, after a confirmation. Issued and void invoices are never
deleted.

A draft stays editable if its project is closed or deleted afterwards.
