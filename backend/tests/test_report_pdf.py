import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fpdf.enums import TableBorderStyle
from fpdf.table import Row

from app.schemas.time_entry import TimeEntryOut, TimesheetReportRowOut
from app.services import report_export_service as svc

# --- heatmap ---------------------------------------------------------------------


def _luminance(color: tuple[int, int, int]) -> float:
    red, green, blue = color
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def test_one_hour_is_tinted_but_not_white():
    color = svc._heat_color(Decimal(1))

    assert color == svc._HEAT_PALE
    assert color != (255, 255, 255)


def test_tint_deepens_with_hours_up_to_eight():
    colors = [svc._heat_color(Decimal(h)) for h in (1, 2, 3, 4, 5, 6, 7, 8)]

    luminances = [_luminance(c) for c in colors]
    assert luminances == sorted(luminances, reverse=True)
    assert len(set(colors)) == len(colors)
    assert colors[-1] == svc._HEAT_STRONG


def test_tint_is_the_same_beyond_eight_hours():
    assert (
        svc._heat_color(Decimal(12)) == svc._heat_color(Decimal(8)) == svc._HEAT_STRONG
    )


@pytest.mark.parametrize("hours", ["0.25", "0.5", "0.99"])
def test_less_than_an_hour_gets_the_pale_tint(hours):
    assert svc._heat_color(Decimal(hours)) == svc._HEAT_PALE


def test_a_half_hour_step_changes_the_tint_between_one_and_eight():
    assert svc._heat_color(Decimal("4.5")) != svc._heat_color(Decimal(4))


# --- table borders ---------------------------------------------------------------

# A table with a header row, three data rows and a Total row, six columns.
_HEADING_ROWS = 1
_ROWS = 5
_COLS = 6


def _style(row: int, col: int):
    return svc._TimesheetBordersLayout().cell_style_getter(
        row_idx=row,
        col_idx=col,
        col_pos=col,
        num_heading_rows=_HEADING_ROWS,
        num_rows=_ROWS,
        num_col_idx=_COLS,
        num_col_pos=_COLS,
    )


def _drawn(edge) -> bool:
    return isinstance(edge, TableBorderStyle) or bool(edge)


def test_no_cell_has_a_right_border_and_only_the_total_column_has_a_left_one():
    for row in range(_ROWS):
        for col in range(_COLS):
            style = _style(row, col)
            assert not _drawn(style.right)
            assert _drawn(style.left) == (col == _COLS - 1)


def test_the_header_row_has_no_borders_of_its_own():
    for col in range(_COLS):
        style = _style(0, col)
        assert not _drawn(style.top)
        assert not _drawn(style.bottom)


def test_the_rule_under_the_header_is_the_strong_top_of_the_first_data_row():
    top = _style(1, 0).top

    assert isinstance(top, TableBorderStyle)
    assert top.thickness == svc._RULE_THICKNESS_MM
    assert top.color == svc._COLOR_TEXT


def test_later_data_rows_are_separated_by_hairlines():
    for row in (2, 3):
        top = _style(row, 0).top
        assert isinstance(top, TableBorderStyle)
        assert top.thickness == svc._HAIRLINE_THICKNESS_MM
        assert top.color == svc._COLOR_HAIRLINE
        assert not _drawn(_style(row, 0).bottom)


def test_the_total_row_has_a_strong_rule_above_it():
    top = _style(_ROWS - 1, 0).top

    assert isinstance(top, TableBorderStyle)
    assert top.thickness == svc._RULE_THICKNESS_MM


def test_a_report_with_no_data_rows_still_gets_the_rule_above_the_total_row():
    layout = svc._TimesheetBordersLayout()

    style = layout.cell_style_getter(
        row_idx=1,
        col_idx=0,
        col_pos=0,
        num_heading_rows=1,
        num_rows=2,
        num_col_idx=_COLS,
        num_col_pos=_COLS,
    )

    assert isinstance(style.top, TableBorderStyle)
    assert style.top.thickness == svc._RULE_THICKNESS_MM


# --- building the PDF ------------------------------------------------------------


def _days(start: date, count: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(count)]


def _row(
    project: str = "Meridian Web App",
    service_line: str | None = "Design Sprint",
    consultant: str = "Jane Doe",
    hours: dict[date, str] | None = None,
) -> TimesheetReportRowOut:
    project_id, service_line_id = uuid.uuid4(), uuid.uuid4()
    return TimesheetReportRowOut(
        user_id=uuid.uuid4(),
        full_name=consultant,
        project_id=project_id,
        project_name=project,
        project_status="active",
        service_line_id=service_line_id,
        service_line_name=service_line,
        entries=[
            TimeEntryOut(
                id=uuid.uuid4(),
                service_line_id=service_line_id,
                service_line_name=service_line,
                project_id=project_id,
                project_name=project,
                date=day,
                hours=Decimal(amount),
                is_locked=False,
            )
            for day, amount in (hours or {}).items()
        ],
        is_assigned=True,
    )


def _page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![a-z])", pdf))


MONTH = _days(date(2026, 8, 1), 31)
WEEK = _days(date(2026, 8, 31), 7)


@pytest.mark.parametrize(
    ("days", "row_count"),
    [(WEEK, 0), (WEEK, 4), (MONTH, 0), (MONTH, 5)],
)
def test_reports_that_fit_one_page_build_a_one_page_pdf(days, row_count):
    rows = [_row(hours={days[0]: "8", days[2]: "1.5"}) for _ in range(row_count)]

    pdf = svc._build_pdf(rows, days, "August 2026")

    assert pdf.startswith(b"%PDF")
    assert _page_count(pdf) == 1


def test_a_long_report_continues_over_further_pages_with_a_footer_on_each(monkeypatch):
    footers: list[str] = []
    real_cell = svc._ReportPdf.cell

    def recording_cell(self, *args, **kwargs):
        text = (
            kwargs.get("text")
            if "text" in kwargs
            else (args[2] if len(args) > 2 else None)
        )
        if isinstance(text, str) and text.startswith("Page "):
            footers.append(text)
        return real_cell(self, *args, **kwargs)

    monkeypatch.setattr(svc._ReportPdf, "cell", recording_cell)
    rows = [_row(hours={MONTH[1]: "8", MONTH[5]: "4"}) for _ in range(30)]

    pdf = svc._build_pdf(rows, MONTH, "August 2026")

    pages = _page_count(pdf)
    assert pages == 3
    # "{nb}" is the total-pages placeholder, filled in when the document is finished.
    assert footers == [f"Page {n} / {{nb}}" for n in range(1, pages + 1)]


def _record_table(monkeypatch):
    """Records what _build_pdf puts in its table: the column widths and every cell's text."""
    recorded: dict = {"col_widths": None, "cells": []}
    real_table = svc._ReportPdf.table
    real_cell = Row.cell

    def table(self, *args, **kwargs):
        recorded["col_widths"] = kwargs["col_widths"]
        return real_table(self, *args, **kwargs)

    def cell(self, text="", *args, **kwargs):
        recorded["cells"].append(text)
        return real_cell(self, text, *args, **kwargs)

    monkeypatch.setattr(svc._ReportPdf, "table", table)
    monkeypatch.setattr(Row, "cell", cell)
    return recorded


def test_the_table_content_is_unchanged(monkeypatch):
    recorded = _record_table(monkeypatch)
    long_name = "Harbour Logistics Platform Migration Programme"
    rows = [
        _row(
            project=long_name,
            service_line="Audit and Compliance Review of Legacy Settlement Platform",
            consultant="Alexandre Montgomery-Featherstonehaugh",
            hours={WEEK[0]: "8", WEEK[1]: "2.5"},
        )
    ]

    svc._build_pdf(rows, WEEK, "2026 Week 36")

    cells = recorded["cells"]
    # Header: first column, one weekday letter over the day number per day, then Total.
    assert cells[:9] == [
        "Timesheet",
        "M\n31",
        "T\n1",
        "W\n2",
        "T\n3",
        "F\n4",
        "S\n5",
        "S\n6",
        "Total",
    ]
    # Data row: project in bold, service line and consultant beneath, each cut to 28
    # characters with an ellipsis.
    assert cells[9] == (
        f"**{long_name[:27]}…**\n"
        "Audit and Compliance Review…\n"
        "Alexandre Montgomery-Feathe…"
    )
    # Blank where nothing is logged, then the row total, which always shows.
    assert cells[10:17] == ["8", "2.5", "", "", "", "", ""]
    assert cells[17] == "10.5h"
    # Bottom Total row.
    assert cells[18:] == ["Total", "8", "2.5", "0", "0", "0", "0", "0", "10.5h"]


@pytest.mark.parametrize("days", [WEEK, MONTH])
def test_day_columns_share_the_page_width_so_a_month_fits(monkeypatch, days):
    recorded = _record_table(monkeypatch)

    svc._build_pdf([_row()], days, "August 2026")

    widths = recorded["col_widths"]
    assert len(widths) == len(days) + 2
    # A4 landscape is 297 mm wide with 8 mm margins.
    assert sum(widths) == pytest.approx(297 - 16)
    day_widths = widths[1:-1]
    assert max(day_widths) == pytest.approx(min(day_widths))
    assert min(day_widths) > 5  # still legible for a 31-day month


def test_no_leftover_square_corner_masking_code():
    assert not hasattr(svc, "_round_table_corners")
    assert not hasattr(svc, "_TABLE_CORNER_RADIUS")
