"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-05

Single-file schema for the whole app. This project hasn't launched yet, there's no
deployed database whose migration history needs to be preserved step-by-step, so what
was previously five incremental revisions (0001 initial, 0002 currencies, 0003 projects,
0004 service_line_name, 0005 time_entries) is squashed into one. Tracking a growing chain
of migrations only starts to matter once a real environment has applied some prefix of
them and needs to move forward from wherever it is; until then it's just noise. When this
app has a first real deployment, start incrementing revisions normally from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.models import triggers

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (alpha_code, numeric_code, name, minor_unit, symbol). Covers ISO 4217's active national
# currencies plus the precious-metal codes (XAU/XAG/XPD/XPT, minor_unit NULL: bullion has
# no minor unit). Symbol is only populated for widely-recognized currencies; NULL elsewhere
# is fine (see the model/table's `symbol` column). Truly obscure
# bond-market/testing codes (XDR, XTS, XXX, XBA-XBD, XSU, XUA) are intentionally not seeded.
_CURRENCIES: list[tuple[str, str, str, int | None, str | None]] = [
    ("AED", "784", "UAE Dirham", 2, None),
    ("AFN", "971", "Afghani", 2, None),
    ("ALL", "008", "Lek", 2, None),
    ("AMD", "051", "Armenian Dram", 2, None),
    ("ANG", "532", "Netherlands Antillean Guilder", 2, None),
    ("AOA", "973", "Kwanza", 2, None),
    ("ARS", "032", "Argentine Peso", 2, "$"),
    ("AUD", "036", "Australian Dollar", 2, "$"),
    ("AWG", "533", "Aruban Florin", 2, None),
    ("AZN", "944", "Azerbaijan Manat", 2, None),
    ("BAM", "977", "Convertible Mark", 2, None),
    ("BBD", "052", "Barbados Dollar", 2, None),
    ("BDT", "050", "Taka", 2, None),
    ("BGN", "975", "Bulgarian Lev", 2, None),
    ("BHD", "048", "Bahraini Dinar", 3, None),
    ("BIF", "108", "Burundi Franc", 0, None),
    ("BMD", "060", "Bermudian Dollar", 2, None),
    ("BND", "096", "Brunei Dollar", 2, None),
    ("BOB", "068", "Boliviano", 2, None),
    ("BRL", "986", "Brazilian Real", 2, "R$"),
    ("BSD", "044", "Bahamian Dollar", 2, None),
    ("BTN", "064", "Ngultrum", 2, None),
    ("BWP", "072", "Pula", 2, None),
    ("BYN", "933", "Belarusian Ruble", 2, None),
    ("BZD", "084", "Belize Dollar", 2, None),
    ("CAD", "124", "Canadian Dollar", 2, "$"),
    ("CDF", "976", "Congolese Franc", 2, None),
    ("CHF", "756", "Swiss Franc", 2, "CHF"),
    ("CLP", "152", "Chilean Peso", 0, "$"),
    ("CNY", "156", "Yuan Renminbi", 2, "¥"),
    ("COP", "170", "Colombian Peso", 2, "$"),
    ("CRC", "188", "Costa Rican Colon", 2, None),
    ("CUP", "192", "Cuban Peso", 2, None),
    ("CVE", "132", "Cabo Verde Escudo", 2, None),
    ("CZK", "203", "Czech Koruna", 2, "Kč"),
    ("DJF", "262", "Djibouti Franc", 0, None),
    ("DKK", "208", "Danish Krone", 2, "kr"),
    ("DOP", "214", "Dominican Peso", 2, None),
    ("DZD", "012", "Algerian Dinar", 2, None),
    ("EGP", "818", "Egyptian Pound", 2, None),
    ("ERN", "232", "Nakfa", 2, None),
    ("ETB", "230", "Ethiopian Birr", 2, None),
    ("EUR", "978", "Euro", 2, "€"),
    ("FJD", "242", "Fiji Dollar", 2, None),
    ("FKP", "238", "Falkland Islands Pound", 2, None),
    ("GBP", "826", "Pound Sterling", 2, "£"),
    ("GEL", "981", "Lari", 2, None),
    ("GHS", "936", "Ghana Cedi", 2, None),
    ("GIP", "292", "Gibraltar Pound", 2, None),
    ("GMD", "270", "Dalasi", 2, None),
    ("GNF", "324", "Guinean Franc", 0, None),
    ("GTQ", "320", "Quetzal", 2, None),
    ("GYD", "328", "Guyana Dollar", 2, None),
    ("HKD", "344", "Hong Kong Dollar", 2, "$"),
    ("HNL", "340", "Lempira", 2, None),
    ("HTG", "332", "Gourde", 2, None),
    ("HUF", "348", "Forint", 2, "Ft"),
    ("IDR", "360", "Rupiah", 2, "Rp"),
    ("ILS", "376", "New Israeli Sheqel", 2, "₪"),
    ("INR", "356", "Indian Rupee", 2, "₹"),
    ("IQD", "368", "Iraqi Dinar", 3, None),
    ("IRR", "364", "Iranian Rial", 2, None),
    ("ISK", "352", "Iceland Krona", 0, None),
    ("JMD", "388", "Jamaican Dollar", 2, None),
    ("JOD", "400", "Jordanian Dinar", 3, None),
    ("JPY", "392", "Yen", 0, "¥"),
    ("KES", "404", "Kenyan Shilling", 2, None),
    ("KGS", "417", "Som", 2, None),
    ("KHR", "116", "Riel", 2, None),
    ("KMF", "174", "Comorian Franc", 0, None),
    ("KPW", "408", "North Korean Won", 2, None),
    ("KRW", "410", "Won", 0, "₩"),
    ("KWD", "414", "Kuwaiti Dinar", 3, None),
    ("KYD", "136", "Cayman Islands Dollar", 2, None),
    ("KZT", "398", "Tenge", 2, None),
    ("LAK", "418", "Lao Kip", 2, None),
    ("LBP", "422", "Lebanese Pound", 2, None),
    ("LKR", "144", "Sri Lanka Rupee", 2, None),
    ("LRD", "430", "Liberian Dollar", 2, None),
    ("LSL", "426", "Loti", 2, None),
    ("LYD", "434", "Libyan Dinar", 3, None),
    ("MAD", "504", "Moroccan Dirham", 2, None),
    ("MDL", "498", "Moldovan Leu", 2, None),
    ("MGA", "969", "Malagasy Ariary", 2, None),
    ("MKD", "807", "Denar", 2, None),
    ("MMK", "104", "Kyat", 2, None),
    ("MNT", "496", "Tugrik", 2, None),
    ("MOP", "446", "Pataca", 2, None),
    ("MRU", "929", "Ouguiya", 2, None),
    ("MUR", "480", "Mauritius Rupee", 2, None),
    ("MVR", "462", "Rufiyaa", 2, None),
    ("MWK", "454", "Malawi Kwacha", 2, None),
    ("MXN", "484", "Mexican Peso", 2, "$"),
    ("MYR", "458", "Malaysian Ringgit", 2, "RM"),
    ("MZN", "943", "Mozambique Metical", 2, None),
    ("NAD", "516", "Namibia Dollar", 2, None),
    ("NGN", "566", "Naira", 2, "₦"),
    ("NIO", "558", "Cordoba Oro", 2, None),
    ("NOK", "578", "Norwegian Krone", 2, "kr"),
    ("NPR", "524", "Nepalese Rupee", 2, None),
    ("NZD", "554", "New Zealand Dollar", 2, "$"),
    ("OMR", "512", "Rial Omani", 3, None),
    ("PAB", "590", "Balboa", 2, None),
    ("PEN", "604", "Sol", 2, None),
    ("PGK", "598", "Kina", 2, None),
    ("PHP", "608", "Philippine Peso", 2, "₱"),
    ("PKR", "586", "Pakistan Rupee", 2, None),
    ("PLN", "985", "Zloty", 2, "zł"),
    ("PYG", "600", "Guarani", 0, None),
    ("QAR", "634", "Qatari Rial", 2, None),
    ("RON", "946", "Romanian Leu", 2, None),
    ("RSD", "941", "Serbian Dinar", 2, None),
    ("RUB", "643", "Russian Ruble", 2, "₽"),
    ("RWF", "646", "Rwanda Franc", 0, None),
    ("SAR", "682", "Saudi Riyal", 2, None),
    ("SBD", "090", "Solomon Islands Dollar", 2, None),
    ("SCR", "690", "Seychelles Rupee", 2, None),
    ("SDG", "938", "Sudanese Pound", 2, None),
    ("SEK", "752", "Swedish Krona", 2, "kr"),
    ("SGD", "702", "Singapore Dollar", 2, "$"),
    ("SHP", "654", "Saint Helena Pound", 2, None),
    ("SLE", "925", "Leone", 2, None),
    ("SOS", "706", "Somali Shilling", 2, None),
    ("SRD", "968", "Surinam Dollar", 2, None),
    ("SSP", "728", "South Sudanese Pound", 2, None),
    ("STN", "930", "Dobra", 2, None),
    ("SYP", "760", "Syrian Pound", 2, None),
    ("SZL", "748", "Lilangeni", 2, None),
    ("THB", "764", "Baht", 2, "฿"),
    ("TJS", "972", "Somoni", 2, None),
    ("TMT", "934", "Turkmenistan New Manat", 2, None),
    ("TND", "788", "Tunisian Dinar", 3, None),
    ("TOP", "776", "Pa'anga", 2, None),
    ("TRY", "949", "Turkish Lira", 2, "₺"),
    ("TTD", "780", "Trinidad and Tobago Dollar", 2, None),
    ("TWD", "901", "New Taiwan Dollar", 2, "NT$"),
    ("TZS", "834", "Tanzanian Shilling", 2, None),
    ("UAH", "980", "Hryvnia", 2, "₴"),
    ("UGX", "800", "Uganda Shilling", 0, None),
    ("USD", "840", "US Dollar", 2, "$"),
    ("UYU", "858", "Peso Uruguayo", 2, None),
    ("UZS", "860", "Uzbekistan Sum", 2, None),
    ("VES", "928", "Bolivar Soberano", 2, None),
    ("VND", "704", "Dong", 0, "₫"),
    ("VUV", "548", "Vatu", 0, None),
    ("WST", "882", "Tala", 2, None),
    ("XAF", "950", "CFA Franc BEAC", 0, None),
    ("XAG", "961", "Silver", None, None),
    ("XAU", "959", "Gold", None, None),
    ("XCD", "951", "East Caribbean Dollar", 2, None),
    ("XOF", "952", "CFA Franc BCEAO", 0, None),
    ("XPD", "964", "Palladium", None, None),
    ("XPF", "953", "CFP Franc", 0, None),
    ("XPT", "962", "Platinum", None, None),
    ("YER", "886", "Yemeni Rial", 2, None),
    ("ZAR", "710", "Rand", 2, "R"),
    ("ZMW", "967", "Zambian Kwacha", 2, None),
    ("ZWL", "932", "Zimbabwe Dollar", 2, None),
]

# Restricts the full ISO 4217 list down to the subset actually selectable when
# creating a project: the rest of the table exists for reference/lookup only.
_ENABLED = {"USD", "EUR", "JPY", "GBP", "CNY", "AUD", "CAD", "CHF", "HKD", "SGD"}


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Local user: their email. SSO user: the IdP's SAML NameID: not
        # typed/validated as an email since that isn't guaranteed.
        sa.Column("name_id", sa.String(length=255), nullable=False),
        # Null for SSO users, who have no local password.
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("is_sso", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        # Light/dark/system, set from the profile menu.
        sa.Column(
            "theme_preference",
            sa.String(length=10),
            nullable=False,
            server_default="system",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Bumped on logout / password reset to invalidate every token issued so far.
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "theme_preference IN ('light', 'dark', 'system')",
            name="ck_users_theme_preference",
        ),
    )

    # Unique among active users only: a deactivated user keeps their name_id (history)
    # and a new user may reuse it. See app/models/user.py.
    op.create_index(
        "uq_users_name_id_active",
        "users",
        ["name_id"],
        unique=True,
        postgresql_where=sa.text("is_active IS true"),
    )

    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("name", sa.String),
        ),
        [
            {"id": "00000000-0000-0000-0000-000000000001", "name": "administrator"},
            # Renamed from "manager" specifically to avoid confusion with
            # "project_manager" below, a distinct role added at the same time
            # (`Reporting`/timesheet-locking authority, scoped per-project) that
            # is easily conflated with this one (`projects`-screen access) by name alone.
            {"id": "00000000-0000-0000-0000-000000000002", "name": "project_admin"},
            {"id": "00000000-0000-0000-0000-000000000003", "name": "consultant"},
            {"id": "00000000-0000-0000-0000-000000000004", "name": "project_manager"},
        ],
    )

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("is_vendor", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("trading_name", sa.String(length=255), nullable=True),
        sa.Column("legal_form", sa.String(length=50), nullable=True),
        sa.Column("country_of_registration", sa.String(length=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "party_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("id_type", sa.String(length=20), nullable=False),
        sa.Column("scheme_id", sa.String(length=10), nullable=True),
        sa.Column("id_value", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "id_type IN ('legal_registration', 'vat', 'peppol_participant', 'duns', "
            "'gln', 'internal')",
            name="ck_party_identifiers_id_type",
        ),
    )
    op.create_index(
        "ix_party_identifiers_company_id", "party_identifiers", ["company_id"]
    )
    # COALESCE scheme_id to '': a plain unique index on nullable scheme_id wouldn't catch
    # duplicates, since SQL treats NULL as distinct from NULL (scheme_id is NULL for most
    # id_types, e.g. `vat`).
    op.create_index(
        "uq_party_identifiers",
        "party_identifiers",
        ["company_id", "id_type", sa.text("COALESCE(scheme_id, '')"), "id_value"],
        unique=True,
    )

    op.create_table(
        "addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("address_type", sa.String(length=15), nullable=False),
        sa.Column("line1", sa.String(length=255), nullable=False),
        sa.Column("line2", sa.String(length=255), nullable=True),
        sa.Column("line3", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("postal_zone", sa.String(length=20), nullable=True),
        sa.Column("country_subdivision", sa.String(length=100), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "address_type IN ('registered', 'bill_to', 'ship_to', 'postal')",
            name="ck_addresses_address_type",
        ),
    )
    op.create_index("ix_addresses_company_id", "addresses", ["company_id"])
    # At most one primary address per (company_id, address_type).
    op.create_index(
        "uq_addresses_primary_per_type",
        "addresses",
        ["company_id", "address_type"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    op.create_table(
        "currencies",
        sa.Column("alpha_code", sa.String(length=3), primary_key=True),
        sa.Column("numeric_code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("minor_unit", sa.SmallInteger(), nullable=True),
        sa.Column("symbol", sa.String(length=10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("numeric_code", name="uq_currencies_numeric_code"),
    )

    op.bulk_insert(
        sa.table(
            "currencies",
            sa.column("alpha_code", sa.String),
            sa.column("numeric_code", sa.String),
            sa.column("name", sa.String),
            sa.column("minor_unit", sa.SmallInteger),
            sa.column("symbol", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("is_enabled", sa.Boolean),
        ),
        [
            {
                "alpha_code": alpha,
                "numeric_code": numeric,
                "name": name,
                "minor_unit": minor_unit,
                "symbol": symbol,
                "is_active": True,
                "is_enabled": alpha in _ENABLED,
            }
            for alpha, numeric, name, minor_unit, symbol in _CURRENCIES
        ],
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "vendor_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id"),
            nullable=True,
        ),
        sa.Column(
            "client_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id"),
            nullable=True,
        ),
        sa.Column(
            "invoicing_currency",
            sa.String(length=3),
            sa.ForeignKey("currencies.alpha_code"),
            nullable=False,
        ),
        sa.Column("project_type", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=10), nullable=False, server_default="draft"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "project_type IN ('time_and_material', 'fixed_price', 'capped_tm')",
            name="ck_projects_project_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'closed')", name="ck_projects_status"
        ),
    )
    op.create_index("ix_projects_vendor_company_id", "projects", ["vendor_company_id"])
    op.create_index("ix_projects_client_company_id", "projects", ["client_company_id"])

    # Users (holding the project_manager role) assigned to review/lock a project's
    # timesheets. Same shape as service_line_consultants below: a plain
    # composite-PK join table, no extra columns: this only ever reflects
    # *current* assignment, not history.
    op.create_table(
        "project_managers",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    for statement in triggers.USERS_TRIGGER_STATEMENTS:
        op.execute(statement)
    for statement in triggers.PROJECT_MANAGERS_TRIGGER_STATEMENTS:
        op.execute(statement)

    op.create_table(
        "service_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Free text, no uniqueness constraint, may be empty: exists purely so a
        # consultant assigned to more than one service line on the same project
        # can tell them apart when picking which one to log time against.
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=5), nullable=False),
        sa.Column("uom", sa.String(length=10), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "uom IN ('hours', 'days', 'ea')", name="ck_service_lines_uom"
        ),
    )
    # Partial index: every query listing a project's service lines filters to
    # is_active = true.
    op.create_index(
        "ix_service_lines_project_id_active",
        "service_lines",
        ["project_id"],
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "service_line_consultants",
        sa.Column(
            "service_line_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_lines.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "time_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_line_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_lines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        # Deliberately INTERVAL, not TIME: TIME's natural 24:00:00 ceiling looked like it
        # enforced the domain constraint for free, but asyncpg binds/decodes TIME
        # exclusively via datetime.time (hour capped at 23) and can neither write nor
        # read back 24:00:00: confirmed against a live connection. The CHECK constraint
        # below does that job explicitly instead.
        sa.Column("time_entry", postgresql.INTERVAL(), nullable=False),
        # Unused in the current UI: deliberate scope-fencing for a later iteration.
        sa.Column("comment", sa.Text(), nullable=True),
        # Deliberately not CASCADE, unlike user_id/service_line_id above: this just
        # records who last touched the row (e.g. a manager's lock/unlock), not whose
        # data it is.
        sa.Column(
            "last_updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint(
            "user_id",
            "service_line_id",
            "date",
            name="uq_time_entries_user_service_line_date",
        ),
        sa.CheckConstraint(
            "time_entry >= interval '0' AND time_entry <= interval '24:00:00'",
            name="ck_time_entries_time_entry_range",
        ),
    )
    op.create_index("ix_time_entries_user_id_date", "time_entries", ["user_id", "date"])

    # --- File storage ---------------------------------------------------------------
    # The bytes and the facts about them: one row per distinct stored content.
    op.create_table(
        "stored_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # SHA-256 of the bytes as stored (after image re-encoding), the dedup key.
        sa.Column("checksum_sha256", sa.Text(), nullable=False, unique=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("detected_content_type", sa.Text(), nullable=False),
        sa.Column("bucket_key", sa.Text(), nullable=False, unique=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'scanning', 'processing', 'ready', 'rejected',"
            " 'failed')",
            name="ck_stored_files_status",
        ),
    )
    # One row per upload: a named attachment of stored content to exactly one object.
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # RESTRICT: stored content is only removed by a cleanup job once nothing refers
        # to it, never as a side effect of deleting an attachment.
        sa.Column(
            "stored_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stored_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("id", "kind", name="uq_files_id_kind"),
        sa.CheckConstraint("kind IN ('setting', 'project')", name="ck_files_kind"),
    )
    # Instance-wide slots named in code (so there is no row to reference): the CHECK on
    # setting_key is what rules out an unknown slot.
    op.create_table(
        "setting_files",
        sa.Column("file_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False, server_default="setting"),
        sa.Column("setting_key", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["file_id", "kind"],
            ["files.id", "files.kind"],
            ondelete="CASCADE",
            name="fk_setting_files_file_id_kind",
        ),
        sa.CheckConstraint("kind = 'setting'", name="ck_setting_files_kind"),
        sa.CheckConstraint("setting_key IN ('org_logo')", name="ck_setting_files_key"),
    )
    op.create_index(
        "setting_files_single_slot",
        "setting_files",
        ["setting_key"],
        unique=True,
        postgresql_where=sa.text("setting_key IN ('org_logo')"),
    )
    for statement in triggers.SETTING_FILES_TRIGGER_STATEMENTS:
        op.execute(statement)

    # Instance-wide scalar settings, one row per (group, key). The registry in code decides
    # which keys exist, so adding a setting needs no migration. The seed rows hold the code
    # defaults; a missing row would read as the default anyway.
    op.create_table(
        "app_settings",
        sa.Column("group_name", sa.String(length=100), primary_key=True),
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(value) IN ('boolean', 'number', 'string')",
            name="ck_app_settings_scalar_value",
        ),
    )
    op.execute(
        """
        INSERT INTO app_settings (group_name, key, value) VALUES
          ('pdf-export', 'export_logo',    'true'::jsonb),
          ('pdf-export', 'logo_height_mm', '20'::jsonb)
        ON CONFLICT (group_name, key) DO NOTHING
        """
    )

    # Files attached to a project.
    op.create_table(
        "project_files",
        sa.Column("file_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False, server_default="project"),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["file_id", "kind"],
            ["files.id", "files.kind"],
            ondelete="CASCADE",
            name="fk_project_files_file_id_kind",
        ),
        sa.CheckConstraint("kind = 'project'", name="ck_project_files_kind"),
    )
    op.create_index("ix_project_files_project_id", "project_files", ["project_id"])
    for statement in triggers.PROJECT_FILES_TRIGGER_STATEMENTS:
        op.execute(statement)

    # The fixed vocabulary a project file can be tagged with. Stored trimmed, lowercase and
    # single-spaced, which the CHECK enforces for every writer.
    op.create_table(
        "file_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.CheckConstraint(
            r"name <> '' AND name = btrim(lower(regexp_replace(name, '\s+', ' ', 'g')))",
            name="ck_file_tags_name_normalized",
        ),
    )
    op.create_table(
        "project_file_tags",
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_files.file_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("file_tags.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )
    op.create_index("ix_project_file_tags_tag_id", "project_file_tags", ["tag_id"])
    # Literal copy of the vocabulary, deliberately not imported from the models.
    for name in (
        "contract",
        "purchase order",
        "statement of work",
        "proposal",
        "master service agreement",
        "non-disclosure agreement",
        "invoice",
        "addendum",
    ):
        op.execute(
            sa.text("INSERT INTO file_tags (id, name) VALUES (gen_random_uuid(), :name)")
            .bindparams(name=name)
        )


def downgrade() -> None:
    for statement in triggers.DROP_STATEMENTS:
        op.execute(statement)
    op.drop_table("app_settings")
    op.drop_table("project_file_tags")
    op.drop_table("file_tags")
    op.drop_table("project_files")
    op.drop_table("setting_files")
    op.drop_table("files")
    op.drop_table("stored_files")
    op.drop_table("time_entries")
    op.drop_table("service_line_consultants")
    op.drop_table("service_lines")
    op.drop_table("project_managers")
    op.drop_table("projects")
    op.drop_table("currencies")
    op.drop_table("addresses")
    op.drop_table("party_identifiers")
    op.drop_table("companies")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
