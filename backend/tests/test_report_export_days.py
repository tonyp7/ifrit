"""The Reporting export in days: the same report with every value divided by the Standard
Workday Length, in each of the three formats."""

import io
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import openpyxl
import pytest
from fpdf.table import Row

from app.models.app_setting import AppSetting
from app.schemas.time_entry import TimeEntryOut, TimesheetReportRowOut
from app.services import app_settings
from app.services import report_export_service as svc
from tests.factories import create_user

EXPORT_URL = "/api/time-entries/report/export"
PARAMS = {"period_type": "month", "start_date": "2026-08-01", "end_date": "2026-08-31"}


def _days(start: date, count: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(count)]


WEEK = _days(date(2026, 8, 31), 7)
MONTH = _days(date(2026, 8, 1), 31)
EIGHT = svc._days_unit(Decimal(8))
SEVEN = svc._days_unit(Decimal(7))


def _row(hours: dict[date, str]) -> TimesheetReportRowOut:
    project_id, service_line_id = uuid.uuid4(), uuid.uuid4()
    return TimesheetReportRowOut(
        user_id=uuid.uuid4(),
        full_name="Jane Doe",
        project_id=project_id,
        project_name="Meridian Web App",
        project_status="active",
        service_line_id=service_line_id,
        service_line_name="Design Sprint",
        entries=[
            TimeEntryOut(
                id=uuid.uuid4(),
                service_line_id=service_line_id,
                service_line_name="Design Sprint",
                project_id=project_id,
                project_name="Meridian Web App",
                date=day,
                hours=Decimal(amount),
                is_locked=False,
            )
            for day, amount in hours.items()
        ],
        is_assigned=True,
    )


def _record_cells(monkeypatch) -> list[tuple[str, float | None]]:
    """Every table cell _build_pdf adds, as (text, font size in points)."""
    cells: list[tuple[str, float | None]] = []
    real_cell = Row.cell

    def cell(self, text="", *args, **kwargs):
        style = kwargs.get("style")
        cells.append((text, style.size_pt if style is not None else None))
        return real_cell(self, text, *args, **kwargs)

    monkeypatch.setattr(Row, "cell", cell)
    return cells


# --- PDF: how a value reads -------------------------------------------------------


@pytest.mark.parametrize(
    ("hours", "unit", "shown"),
    [
        ("8", EIGHT, "1"),
        ("4", EIGHT, "0.5"),
        ("5", EIGHT, "0.625"),
        ("1", EIGHT, "0.125"),
        ("1", SEVEN, "0.143"),
        ("2", SEVEN, "0.286"),
        ("99", EIGHT, "12.375"),
        ("80", EIGHT, "10"),
        ("0", EIGHT, ""),
    ],
)
def test_a_value_in_days_shows_no_decimal_it_does_not_need(hours, unit, shown):
    assert svc._format_days(Decimal(hours), unit) == shown


def test_a_half_rounds_away_from_zero():
    # 1 / 16 = 0.0625, exactly halfway between 0.062 and 0.063.
    assert svc._format_days(Decimal(1), svc._days_unit(Decimal(16))) == "0.063"


def test_the_pdf_in_days_shows_days_and_a_d_suffix(monkeypatch):
    cells = _record_cells(monkeypatch)
    row = _row({WEEK[0]: "8", WEEK[1]: "4", WEEK[2]: "5"})

    svc._build_pdf([row], WEEK, "2026 Week 36", None, EIGHT)

    texts = [text for text, _size in cells]
    assert texts[10:17] == ["1", "0.5", "0.625", "", "", "", ""]
    assert texts[17] == "2.125d"
    assert texts[18:] == ["Total", "1", "0.5", "0.625", "0", "0", "0", "0", "2.125d"]


def test_a_total_is_converted_from_exact_hours_not_summed_from_rounded_cells(
    monkeypatch,
):
    cells = _record_cells(monkeypatch)
    row = _row({day: "1" for day in WEEK[:6]})

    svc._build_pdf([row], WEEK, "2026 Week 36", None, SEVEN)

    texts = [text for text, _size in cells]
    # Six cells of 0.143 add up to 0.858, but 6 / 7 is 0.857.
    assert texts[10:16] == ["0.143"] * 6
    assert texts[17] == "0.857d"
    assert texts[-1] == "0.857d"


def test_the_pdf_in_hours_is_unchanged_and_never_resizes_a_font(monkeypatch):
    cells = _record_cells(monkeypatch)
    row = _row({WEEK[0]: "8", WEEK[1]: "2.5"})

    svc._build_pdf([row], WEEK, "2026 Week 36")

    texts = [text for text, _size in cells]
    assert texts[10:18] == ["8", "2.5", "", "", "", "", "", "10.5h"]
    assert texts[-1] == "10.5h"
    value_sizes = {size for text, size in cells[10:] if "\n" not in text}
    assert value_sizes <= {7, 8}


# --- PDF: fitting a value into its cell ---------------------------------------------


def test_a_value_too_wide_for_its_cell_is_drawn_smaller(monkeypatch):
    cells = _record_cells(monkeypatch)
    # 99 hours of an 8-hour day is 12.375 days, wider than a 31-day month's 7.2 mm column.
    row = _row({MONTH[0]: "99", MONTH[1]: "1", MONTH[2]: "4"})

    svc._build_pdf([row], MONTH, "August 2026", None, EIGHT)

    sizes = {text: size or 0.0 for text, size in cells[34:37]}
    # A cell keeps 1 mm free at each side, so only about 5 mm of a 7.2 mm column is usable:
    # 0.125 is already too wide at 7 pt, and 12.375 needs a smaller font still.
    assert svc._MIN_FIT_FONT_PT <= sizes["12.375"] < sizes["0.125"] < 7
    assert sizes["0.5"] == 7


def test_a_fitted_value_never_wraps_onto_a_second_line(monkeypatch):
    """What fits by the font metrics must also fit by fpdf2's own wrapping rule."""
    pdf = svc._ReportPdf(orientation="L", unit="mm", format="A4")
    pdf.add_font(
        "LiberationSans", "", svc._liberation_font_path("LiberationSans-Regular.ttf")
    )
    pdf.add_font(
        "LiberationSans", "B", svc._liberation_font_path("LiberationSans-Bold.ttf")
    )
    pdf.add_page()
    day_w = (297 - 16 - 45 - 14) / 31

    for text in ["0.125", "0.625", "107.5", "12.375", "1234.5"]:
        size = svc._fit_font_size(pdf, text, bold=True, size_pt=7, width_mm=day_w)
        # fpdf2 annotates the size as `int`, but it takes any number of points.
        # pyrefly: ignore [bad-argument-type]
        pdf.set_font("LiberationSans", style="B", size=size)
        assert pdf.get_string_width(text) + 2 * pdf.c_margin <= day_w or (
            size == svc._MIN_FIT_FONT_PT
        ), text


def test_a_wide_total_is_drawn_smaller_but_not_below_the_minimum(monkeypatch):
    cells = _record_cells(monkeypatch)
    row = _row({MONTH[0]: "24"})

    # A 30-minute workday turns 24 hours into 48 days a day; the grand total is longer still.
    svc._build_pdf([row], MONTH, "August 2026", None, svc._days_unit(Decimal("0.5")))

    sizes = [size for _text, size in cells if size is not None]
    assert min(sizes) >= svc._MIN_FIT_FONT_PT


def test_the_fit_never_grows_a_font_past_its_normal_size():
    pdf = svc._ReportPdf(orientation="L", unit="mm", format="A4")
    pdf.add_font(
        "LiberationSans", "", svc._liberation_font_path("LiberationSans-Regular.ttf")
    )
    pdf.add_font(
        "LiberationSans", "B", svc._liberation_font_path("LiberationSans-Bold.ttf")
    )
    pdf.add_page()

    assert svc._fit_font_size(pdf, "1", bold=False, size_pt=7, width_mm=50) == 7


# --- Excel ------------------------------------------------------------------------


def _workbook(unit: svc._ExportUnit) -> openpyxl.Workbook:
    rows = [_row({WEEK[0]: "1", WEEK[1]: "4"})]
    return openpyxl.load_workbook(io.BytesIO(svc._build_xlsx(rows, WEEK, unit)))


def test_excel_in_days_holds_exact_values_shown_to_three_places():
    workbook = _workbook(SEVEN)

    details = workbook["Details"]
    assert details["E1"].value == "Days"
    assert details["E2"].value == pytest.approx(1 / 7, rel=1e-12)
    assert details["E2"].number_format == "0.0##"
    report = workbook["Report"]
    # Project, Service Line, Consultant, then the first day, then the last (Total) column.
    assert report["D2"].value == pytest.approx(1 / 7, rel=1e-12)
    assert report["D2"].number_format == "0.0##"
    assert report["K2"].value == pytest.approx(5 / 7, rel=1e-12)
    assert report["K3"].value == pytest.approx(5 / 7, rel=1e-12)


def test_excel_in_hours_is_unchanged():
    workbook = _workbook(svc._HOURS)

    details = workbook["Details"]
    assert details["E1"].value == "Hours"
    assert details["E2"].value == 1.0
    assert details["E2"].number_format == "0.0"
    assert workbook["Report"]["D2"].number_format == "0.0"
    assert workbook["Report"]["K2"].value == 5.0


# --- CSV --------------------------------------------------------------------------


def test_csv_in_days_has_a_days_header_and_five_places():
    rows = [_row({WEEK[0]: "1", WEEK[1]: "4"})]

    lines = svc._build_csv(rows, SEVEN).decode().splitlines()

    assert lines[0] == "Project Name,Service Line,Consultant,Date,Days"
    assert lines[1].endswith(",2026-08-31,0.14286")
    assert lines[2].endswith(",2026-09-01,0.57143")


def test_csv_in_days_of_a_whole_number_keeps_the_five_places():
    rows = [_row({WEEK[0]: "4"})]

    lines = svc._build_csv(rows, EIGHT).decode().splitlines()

    assert lines[1].endswith(",2026-08-31,0.50000")


def test_csv_in_hours_is_unchanged():
    rows = [_row({WEEK[0]: "4"})]

    lines = svc._build_csv(rows).decode().splitlines()

    assert lines[0] == "Project Name,Service Line,Consultant,Date,Hours"
    assert lines[1].endswith(",2026-08-31,4.0")


# --- Endpoint ---------------------------------------------------------------------


async def _manager(client, db_session) -> None:
    await create_user(
        db_session, name_id="pm@example.com", password="pw", role_name="manager"
    )
    response = await client.post(
        "/api/auth/login", json={"email": "pm@example.com", "password": "pw"}
    )
    assert response.status_code == 200


def _serve_rows(monkeypatch, rows: list[TimesheetReportRowOut]) -> None:
    async def fake_report(*_args: Any, **_kwargs: Any) -> list[TimesheetReportRowOut]:
        return rows

    monkeypatch.setattr(svc, "list_time_entries_report", fake_report)


async def test_an_unknown_unit_is_rejected(client, db_session) -> None:
    await _manager(client, db_session)

    response = await client.get(
        EXPORT_URL, params={**PARAMS, "format": "csv", "unit": "weeks"}
    )

    assert response.status_code == 422


async def test_leaving_the_unit_out_is_the_same_as_hours(
    client, db_session, monkeypatch
) -> None:
    await _manager(client, db_session)
    _serve_rows(monkeypatch, [_row({MONTH[4]: "3"})])

    plain = await client.get(EXPORT_URL, params={**PARAMS, "format": "csv"})
    hours = await client.get(
        EXPORT_URL, params={**PARAMS, "format": "csv", "unit": "hours"}
    )

    assert plain.status_code == hours.status_code == 200
    assert plain.content == hours.content
    assert b",3.0" in plain.content


async def test_a_days_export_uses_the_saved_workday_length(
    client, db_session, monkeypatch
) -> None:
    await _manager(client, db_session)
    _serve_rows(monkeypatch, [_row({MONTH[4]: "7"})])
    params = {**PARAMS, "format": "csv", "unit": "days"}

    default = await client.get(EXPORT_URL, params=params)
    db_session.add(
        AppSetting(group_name="general", key="standard_workday_seconds", value=25200)
    )
    await db_session.commit()
    seven_hours = await client.get(EXPORT_URL, params=params)

    assert default.content.decode().splitlines()[1].endswith(",2026-08-05,0.87500")
    assert seven_hours.content.decode().splitlines()[1].endswith(",2026-08-05,1.00000")


@pytest.mark.parametrize("export_format", ["pdf", "xlsx", "csv"])
async def test_an_export_in_hours_never_reads_the_workday_length(
    client, db_session, monkeypatch, export_format
) -> None:
    await _manager(client, db_session)
    _serve_rows(monkeypatch, [_row({MONTH[4]: "7"})])
    groups: list[str] = []
    real_get_group = app_settings.get_group

    async def recording_get_group(db, group):
        groups.append(group)
        return await real_get_group(db, group)

    monkeypatch.setattr(app_settings, "get_group", recording_get_group)

    response = await client.get(EXPORT_URL, params={**PARAMS, "format": export_format})

    assert response.status_code == 200
    assert "general" not in groups


@pytest.mark.parametrize("export_format", ["pdf", "xlsx", "csv"])
async def test_every_format_can_be_exported_in_days(
    client, db_session, monkeypatch, export_format
) -> None:
    await _manager(client, db_session)
    _serve_rows(monkeypatch, [_row({MONTH[4]: "7"})])

    response = await client.get(
        EXPORT_URL, params={**PARAMS, "format": export_format, "unit": "days"}
    )

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith("attachment")
