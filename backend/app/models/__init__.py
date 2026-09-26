from app.models import triggers
from app.models.company import Address, Company, PartyIdentifier
from app.models.currency import Currency
from app.models.project import Project, ServiceLine
from app.models.time_entry import TimeEntry
from app.models.user import Role, User

triggers.attach()

__all__ = [
    "Address",
    "Company",
    "Currency",
    "PartyIdentifier",
    "Project",
    "Role",
    "ServiceLine",
    "TimeEntry",
    "User",
]
