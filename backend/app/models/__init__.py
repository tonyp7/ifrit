from app.models import triggers
from app.models.company import Address, Company, PartyIdentifier
from app.models.currency import Currency
from app.models.file import (
    File,
    FileTag,
    ProjectFile,
    ProjectFileTag,
    SettingFile,
    StoredFile,
)
from app.models.project import Project, ServiceLine
from app.models.time_entry import TimeEntry
from app.models.user import Role, User

triggers.attach()

__all__ = [
    "Address",
    "Company",
    "Currency",
    "File",
    "FileTag",
    "PartyIdentifier",
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
