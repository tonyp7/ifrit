from sqlalchemy import SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Currency(Base):
    __tablename__ = "currencies"

    # Natural key (ISO 4217 alpha code), not a surrogate UUID — see
    # docs/architecture/database.md#currencies.
    alpha_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    numeric_code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    minor_unit: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Restricts the full ISO 4217 list down to the subset selectable in the app (see
    # docs/requirements/project.md#currency).
    is_enabled: Mapped[bool] = mapped_column(default=False)
