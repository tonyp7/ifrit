from app.models import triggers
from app.models.app_setting import AppSetting
from app.models.company import Address, Company, PartyIdentifier, PayeeAccount
from app.models.currency import Currency
from app.models.file import (
    File,
    FileTag,
    ProjectFile,
    ProjectFileTag,
    SettingFile,
    StoredFile,
)
from app.models.invoice import Invoice, InvoiceLine, InvoiceReference
from app.models.invoice_numbering import InvoiceNumberCounter, InvoiceNumberingFormat
from app.models.project import BillingMilestone, Project, ServiceLine
from app.models.time_entry import TimeEntry
from app.models.user import Role, User

triggers.attach()

__all__ = [
    "Address",
    "AppSetting",
    "BillingMilestone",
    "Company",
    "Currency",
    "File",
    "FileTag",
    "Invoice",
    "InvoiceLine",
    "InvoiceNumberCounter",
    "InvoiceNumberingFormat",
    "InvoiceReference",
    "PartyIdentifier",
    "PayeeAccount",
    "Project",
    "ProjectFile",
    "ProjectFileTag",
    "Role",
    "ServiceLine",
    "SettingFile",
    "StoredFile",
    "TimeEntry",
    "User",
]
