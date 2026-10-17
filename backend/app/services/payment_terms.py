import calendar
from datetime import date, timedelta

from app.models.invoice import PaymentTerms


def apply_payment_terms(preset: PaymentTerms, invoice_date: date) -> date:
    """The due date a payment terms preset gives for an invoice dated `invoice_date`, in
    calendar days with no weekend or holiday adjustment: `net_<n>` adds n days, `eom` is the
    last day of the invoice date's month and `eom_<n>` adds n days to it. The form shows the
    same rule as an estimate while the invoice is a draft."""
    if preset == "due_on_receipt":
        return invoice_date
    base, _, days = preset.partition("_")
    offset = timedelta(days=int(days or 0))
    if base == "net":
        return invoice_date + offset
    last_day = calendar.monthrange(invoice_date.year, invoice_date.month)[1]
    return invoice_date.replace(day=last_day) + offset
