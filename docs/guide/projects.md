# Projects

Projects are managed by users with the **manager** role, from the **Projects** icon in the
navigation bar. Administrators who are not also managers do not see this screen.

A project ties together a vendor, a client, the work to be done (service lines), the people who do
it (consultants) and the people who oversee it (project managers).

## Before you start

- The **vendor** and **client** are [companies](administration.md#companies). They must exist first,
  and the vendor must be flagged as a vendor. Ask an administrator to create them if needed.
- **Consultants** and **project managers** are [users](administration.md#users) holding the
  consultant and manager role respectively.

## The project list

The list shows active projects, 50 per page, with **Previous** and **Next** controls and the columns
Name, Status, Client, Project Type and Creation Date. Use **New** to create a project, and each row's
**Actions** menu to edit, duplicate or delete it.

The **Only see my projects** switch next to the search box is **on** every time you open the
screen: the list then shows only the projects you are listed on as a project manager, whatever
their status. Turn it off to see every project. A project you create does not appear in your
projects until you add yourself as one of its project managers.

## Project fields

| Field | Notes |
|---|---|
| **Name** | Required. Not required to be unique. |
| **Vendor** | An active company flagged as a vendor. |
| **Client** | Any active company. It can be the same company as the vendor. |
| **Invoicing currency** | Chosen from the enabled currencies. |
| **Type** | Time & Material, Fixed Price or Capped T&M. It does not change how hours are tracked. Only Fixed Price projects have [billing milestones](#billing-milestones). |
| **Status** | Draft, Active or Closed. |

### Status

| Status | Effect |
|---|---|
| **Draft** | Being prepared. Its service lines are not offered to consultants on their timesheet. |
| **Active** | Consultants can add its service lines and log hours. |
| **Closed** | Read-only: header, references, managers, service lines and documents cannot be changed. Hours remain visible and reportable. Only the status can be changed, so you can reopen it. |

You can move between any two statuses.

## Project references

Below the header fields, the **Project References** section keeps the values a buyer expects to see
on an invoice for this project, such as a purchase order number or a contract ID, so nobody has to
look them up again. It works like [billing milestones](#billing-milestones), and is available on
every project type.

- **Add** opens a dialog. Choose the **type**, which starts as **Purchase order**, and enter the
  **value**. For the type **Custom**, give the reference a name of your own as well.
- The table lists each reference by its **Reference Name** (the type, or the name you gave a
  custom one) and its **Value**.
- Each row's **Actions** menu lets you **edit**, **duplicate** (the copy is added at the end) or
  **delete** a reference. Deleting asks for confirmation and removes the reference for good.
- **Reorder** references by dragging the handle at the start of a row. On a phone, press and hold
  the handle first. With a keyboard, focus the handle, press Space, move with the arrow keys and
  press Space again. The order is saved immediately.
- Changes to a reference are saved as soon as you confirm them. They do not wait for **Save** at
  the bottom of the form.
- On a new project that has not been saved yet, **Add** first checks the required fields and saves
  the project, then opens the dialog.

| Type | Use it for |
|---|---|
| **Purchase order** | The buyer's order number. |
| **Sales order** | Your own order number. |
| **Contract** | A contract or agreement number. |
| **Buyer reference** | A reference the buyer asks to see, for example a department or a person. |
| **Accounting reference** | Where the buyer books the cost, such as a cost center or a ledger account. |
| **Project reference** | The buyer's own project code. |
| **Document reference** | A pointer to a supporting document, such as its number or a link. |
| **Custom** | Anything else, with a name of your own. |

- A project can have **several references of the same type**, for example several purchase
  orders.
- The same type with the same value cannot be listed twice. Capital letters are ignored, so
  `PO-17` and `po-17` count as one reference.
- A project can have up to 50 references.
- A **Closed** project lists its references, but they cannot be changed until it is reopened.

## Project managers

Below the header fields, pick the users who manage this project. They are chosen from users who
hold the manager role; selections appear as chips and are saved together with the project. Being
listed grants nothing extra, since every manager can work on every project: it decides which
projects **Only see my projects** shows, on this screen and in [Reporting](reporting.md). A project
may have none.

## Service lines

A service line is a unit of work on a project. Each has:

- an optional **name** (not required to be unique),
- a **quantity** greater than zero, a **unit** (Hours, Days or Each) and a **unit price** of zero or
  more in the project's currency,
- the **consultants** assigned to it.

The table shows each line's value as quantity times unit price, and the project's total.

**Assignment** decides who can log hours: a consultant sees and can add a service line on their
timesheet only when they are assigned to it and its project is Active. Removing a consultant from a
line removes the assignment only; the hours they logged stay.

### Editing and deleting a line

| Project status | Add and edit | Delete |
|---|---|---|
| Draft | Free | A line with no logged time is removed; one with logged time is deactivated (hidden, history kept). |
| Active | Free | Allowed only while no time has been logged on it (a locked zero-hour placeholder counts as logged). |
| Closed | Not allowed | Not allowed |

## Supporting documents

Under the service lines, the **Supporting Documents** section keeps files related to the project.
Only users with the manager role can list, upload, tag, download and delete them.

- **Upload** with the Upload File button. The file must be within the size limit set for the
  installation (10 MiB by default) and of an accepted type; other files are rejected.
- **Tag** a document from the fixed list: contract, purchase order, statement of work, proposal,
  master service agreement, non-disclosure agreement, invoice, addendum.
- A closed project's documents stay downloadable but cannot be changed.

## Billing milestones

A **Fixed Price** project is billed in agreed installments, for example 30% at kick-off and 40% at
delivery. Record them in the **Billing Milestones** section, which appears below the supporting
documents only when the project type is Fixed Price.

Each milestone has:

- a **description**,
- an optional **due date**, picked from a calendar and removable with **Clear date**,
- a **value** in the project's currency.

The table also shows each milestone's **%**: its share of the contract value, which is the
project's total from its service lines. Only the value is saved. If the service lines change, the
% shown changes and the value stays the same. Below the table, a **total** adds up the values.
When that total differs from the contract value, a warning says so. It is only a reminder and
never stops you saving.

- **Add** opens a dialog. Type either a **%**, and the value is worked out from the contract value
  and rounded to the currency (for example to whole yen), or a **value**, and the % follows. The %
  field is unavailable while the project has no service lines.
- Each row's **Actions** menu lets you **edit**, **duplicate** (the copy is added at the end) or
  **delete** a milestone. Deleting asks for confirmation and removes the milestone for good.
- **Reorder** milestones by dragging the handle at the start of a row. On a phone, press and hold
  the handle first. With a keyboard, focus the handle, press Space, move with the arrow keys and
  press Space again. The order is saved immediately.
- On a **Closed** project the milestones are shown but cannot be changed.

Changing the type of a project that has milestones away from Fixed Price asks you to confirm,
because the milestones are **removed when you next save the project**. Until you save, nothing is
lost: close the form without saving, or switch the type back to Fixed Price, and they are still
there.

Changing the project's **currency** keeps the values as they were. They are shown with the new
currency's decimals. Correct any milestone that no longer fits by editing it.

## Duplicate and delete

- **Duplicate** creates a new project in **Draft** status from an existing one (even a closed one),
  copying the name, vendor, client, currency, type, project references in their order, project
  managers, every active service line with its assigned consultants, and every billing milestone
  in its order. Supporting documents
  and their tags are not copied.
- **Delete** asks for confirmation and deactivates the project. It disappears from the list and
  cannot be restored from the application.
