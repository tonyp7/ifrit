# Administration

Administrators manage the people, companies and global settings that everything else builds on.
Everything is under the **Configuration** icon in the navigation bar, which has four tabs:
**General**, **Companies**, **Users** and **Invoices**.

Removing a user or a company *deactivates* it: it disappears from lists and can no longer be used,
but everything recorded against it is kept. Deactivation cannot be undone from the application.

## General

### Organization logo

Upload a JPEG, PNG or WebP image with **Browse**. Only one logo exists: uploading a new one replaces
the current one, and a failed upload leaves the current one unchanged. The logo can also be removed.

### PDF report export

The **PDF Report Export** card controls the logo in exported PDF reports:

- a switch, **Insert organization logo in exported PDF** (on by default),
- a slider, **Logo height, in mm**, from 1 to 60 (20 by default).

The slider keeps its value while the switch is off.

### Standard workday length

The **Standard Workday Length** card sets how long a working day is, from 00:30:00 to 24:00:00
(8 hours by default). Invoices use it to turn the hours logged on a service line billed in days
into a number of days: 20 hours with an 8-hour day is 2.5 days. Timesheets are always entered in
hours.

Enter the length in the **Hours**, **Minutes** and **Seconds** fields. It is saved when you leave
the fields or press Enter. A value outside the allowed range is brought to the nearest limit
before it is saved, and the fields show what was saved. Changing the length only affects invoice
lines generated afterwards.

## Invoices

### Document name

The **Document Name** card sets the title that invoices carry, "Invoice" by default. Some
jurisdictions require another title, such as "Tax Invoice". The name can be up to 60 characters
and cannot be empty. It is saved when you leave the field or press Enter.

### Invoice numbering

The **Invoice Numbering** card decides how issued invoices are numbered. A draft has no number: it
gets the next one when it is issued, so numbers have no gaps from drafts that were deleted. A
new installation numbers invoices `INV-2026-0001`, `INV-2026-0002` and so on, starting again at
`0001` every year.

Build the format from:

- **Presets**: `INV-00001`, `2026-0001` and `202610-001`, the usual starting points. Pick one, then
  adjust it.
- **Tiles**: **Year**, **Month** and **Day** (of the day the invoice is issued), **Sequence #**, the
  counter, and **Label**. A format has exactly one sequence.
- **Label** is text that stays the same on every invoice, such as `INV-` or `/`. Letters, digits,
  `-`, `/` and `_` are allowed. A format can have as many labels as you like.

Click a tile to add it at the end of the format. A new label takes the cursor, so type its text
straight away; a label left empty disappears when you click elsewhere. Drag the parts by their
handle to reorder them, or select one and press **Alt** with the left or right arrow. Every part,
a label too, has its own remove button. **Undo**, **Redo** and **Reset to default** are below the
format.

The format is not saved as you edit it. Choose the red **Apply** button, after **Reset to
default**, to apply it: it stays greyed out until the format differs from the saved one and has no
error. Red because the new format numbers every invoice issued from then on.

Click the sequence to set:

- **Digits**: how many digits the counter has, padded with zeros (5 digits gives `00001`). A
  counter that outgrows its digits is written in full, never cut.
- **Start at**: the first value.
- **Restart**: **Never**, **Yearly** (every 1 January), **Monthly** (the 1st of each month) or
  **Daily**.

The **Preview** shows the next three numbers. The card warns, without blocking, when a counter
restarts but the format lacks the date that tells the periods apart, for example a monthly counter
with no month, which would give two invoices the same number. A format with no sequence, or that
could produce a number longer than 100 characters, cannot be saved.

**Changing the format later**: once invoices have been issued, applying asks you to confirm. The new
format only applies to invoices issued from then on; issued invoices keep their numbers.

**Next number**: set the counter's next value, for example to continue from another system. A value
whose number already exists is refused. It applies to the current period: a yearly counter still
starts again next year.

Invoice dates and the dates in numbers follow the server's time zone, see
[Time zone](../configuration.md#time-zone).

### Invoice template

The **Invoice Template** card chooses the layout invoice PDFs are made from. It shows whether the
default template or one you uploaded is in use, lets you **Download** the one in use, **Upload** a
new one (you see a sample PDF and any warnings first, and confirm before it is used), and **Reset
to default**. Changing it affects previews and invoices issued from then on, never invoices that
were already issued. See [The invoice template](invoice-template.md) for how to edit one.

## Companies

Companies are the vendors and clients that projects refer to. Both administrators and managers
can see the list (managers need it to pick a project's vendor and client), but only administrators
can create or change companies.

### Fields

| Field | Notes |
|---|---|
| **Legal name** | Required. |
| **Trading name** | Optional. |
| **Legal form** | Optional. |
| **Country** | The country of registration, picked from the country list (see below). |
| **Vendor** | Off by default. Only a company flagged as a vendor can be a project's vendor. Any active company can be a client. |

A company can also hold several **identifiers** (such as a tax or registration number),
**addresses** and **payee accounts**. Add, edit, duplicate and delete them from the company's
form. These are removed for good rather than deactivated.

Wherever a company form asks for a country (the country of registration, an address, a bank
address), pick it from a list showing each country's flag and name: type part of the name, or its
two-letter code, to narrow the list. The country is stored as its two-letter ISO code. A company
saved before this list existed may hold a code that is not a country (for example `ZZ`): it is
shown as typed, with a globe instead of a flag, and stays as it is until you pick a country.

### Payee accounts

Payee accounts are the bank accounts a company is paid into: what an invoice tells the buyer
when it says where to pay. They are kept so that invoices can carry them later, including
electronic invoices. The section sits below Addresses and is available on every company, but
it only matters for the companies that send invoices.

| Field | Notes |
|---|---|
| **Payment means** | *Wire transfer* (an international payment over SWIFT), *Bank transfer* (a payment over local rails such as ACH or Faster Payments) or *SEPA credit transfer*. The invoice shows the same words. |
| **Scheme** | *IBAN*, or *Other* for a national account number. A SEPA credit transfer always uses an IBAN. |
| **IBAN** / **Account number** | Required. An IBAN can be typed with or without spaces; it is checked (a single wrong digit is caught) and shown in groups of four. A national account number is kept exactly as typed. |
| **Account name** | Optional. The account holder, if it differs from the company's name. |
| **Currency** | Required. One of the currencies enabled for the app. |
| **BIC** | Optional. The bank's 8 or 11 character code. |
| **Bank name** and **Bank address** | Optional. If you start the address, line 1, city and country are required. |
| **Primary for this currency** | At most one account per currency can be primary. To make another account primary, untick the current one first. |

The same account number can't be entered twice on one company. Duplicating a company copies its
payee accounts too.

### Actions

- **New**, **Edit** and **Duplicate** use the same form. Duplicate starts a new company from an
  existing one.
- **Delete** asks for confirmation and deactivates the company. Projects that already refer to it
  stay readable.

## Users

### Create a user

Choose **New**, then fill in:

- the full name,
- the login identity, which is the user's email address,
- one or more roles (`consultant` is preselected), see [Roles](roles.md),
- an initial password.

Login identities must be unique among active users. A person cannot sign up on their own; every
account starts here.

### Passwords

A password must be 12 to 255 characters and may contain letters, digits, spaces and symbols but no
control characters. A strength indicator under the field updates as you type.

To help someone who forgot their password, open their record in the users list and set a new one.
Doing so ends all of that user's current sessions.

### Edit, duplicate, deactivate

- **Edit** changes name, login identity and roles.
- **Duplicate** pre-fills a new user from an existing one, for example to create a colleague with
  the same roles.
- **Delete** asks for confirmation and deactivates the account. The user can no longer sign in
  and loses any open session, is removed as project manager from every project, and keeps their
  logged history. Their login email can be used again for a new account.

You cannot deactivate your own account or remove your own `administrator` role, even if other
administrators exist.

### A leaver on a project

A deactivated consultant stays on the service lines they were assigned to, so a manager can
still review and lock their final timesheet in [Reporting](reporting.md).
