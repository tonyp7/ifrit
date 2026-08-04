"""currencies: full ISO 4217 list, is_enabled subset selectable in the app

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (alpha_code, numeric_code, name, minor_unit, symbol). Covers ISO 4217's active national
# currencies plus the precious-metal codes (XAU/XAG/XPD/XPT, minor_unit NULL — see
# docs/architecture/database.md#currencies). Symbol is only populated for widely-recognized
# currencies; NULL elsewhere is fine (see the model/table's `symbol` column). Truly obscure
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

# See docs/requirements/project.md#currency / docs/architecture/database.md#currencies.
_ENABLED = {"USD", "EUR", "JPY", "GBP", "CNY", "AUD", "CAD", "CHF", "HKD", "SGD"}


def upgrade() -> None:
    op.create_table(
        "currencies",
        sa.Column("alpha_code", sa.String(length=3), primary_key=True),
        sa.Column("numeric_code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("minor_unit", sa.SmallInteger(), nullable=True),
        sa.Column("symbol", sa.String(length=10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
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


def downgrade() -> None:
    op.drop_table("currencies")
