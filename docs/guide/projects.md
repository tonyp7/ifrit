# Projects

Projects are managed by users with the **project admin** role, from the **Projects** icon in the
navigation bar. Administrators who are not also project admins do not see this screen.

A project ties together a vendor, a client, the work to be done (service lines), the people who do
it (consultants) and the people who oversee it (project managers).

## Before you start

- The **vendor** and **client** are [companies](administration.md#companies). They must exist first,
  and the vendor must be flagged as a vendor. Ask an administrator to create them if needed.
- **Consultants** and **project managers** are [users](administration.md#users) holding the
  corresponding role.

## The project list

The list shows active projects, 50 per page, with **Previous** and **Next** controls and the columns
Name, Status, Client, Project Type and Creation Date. Use **New** to create a project, and each row's
**Actions** menu to edit, duplicate or delete it.

## Project fields

| Field | Notes |
|---|---|
| **Name** | Required. Not required to be unique. |
| **Vendor** | An active company flagged as a vendor. |
| **Client** | Any active company. It can be the same company as the vendor. |
| **Invoicing currency** | Chosen from the enabled currencies. |
| **Type** | Time & Material, Fixed Price or Capped T&M. It is recorded with the project and does not change how hours are tracked. |
| **Status** | Draft, Active or Closed. |

### Status

| Status | Effect |
|---|---|
| **Draft** | Being prepared. Its service lines are not offered to consultants on their timesheet. |
| **Active** | Consultants can add its service lines and log hours. |
| **Closed** | Read-only: header, managers, service lines and documents cannot be changed. Hours remain visible and reportable. Only the status can be changed, so you can reopen it. |

You can move between any two statuses.

## Project managers

Below the header fields, pick the users who manage this project. They are chosen from users who
hold the project manager role; selections appear as chips and are saved together with the
project. A project may have none, but then nobody sees its hours in Reporting.

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
Only users with the project admin role can list, upload, tag, download and delete them.

- **Upload** with the Upload File button. The file must be within the size limit set for the
  installation (10 MiB by default) and of an accepted type; other files are rejected.
- **Tag** a document from the fixed list: contract, purchase order, statement of work, proposal,
  master service agreement, non-disclosure agreement, invoice, addendum.
- A closed project's documents stay downloadable but cannot be changed.

## Duplicate and delete

- **Duplicate** creates a new project in **Draft** status from an existing one (even a closed one),
  copying the name, vendor, client, currency, type, project managers and every active service line
  with its assigned consultants. Supporting documents and their tags are not copied.
- **Delete** asks for confirmation and deactivates the project. It disappears from the list and
  cannot be restored from the application.
