import io
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fpdf.enums import TableBorderStyle
from fpdf.table import Row
from PIL import Image, UnidentifiedImageError

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


# --- logo preparation ------------------------------------------------------------


def _png(size: tuple[int, int], mode: str = "RGB", color=(30, 60, 160)) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_a_wide_logo_is_shrunk_to_the_long_edge_limit_keeping_its_ratio():
    prepared = svc._prepare_logo(_png((3000, 1000)))

    assert (prepared.width_px, prepared.height_px) == (1200, 400)
    assert _open(prepared.data).size == (1200, 400)


def test_a_tall_logo_is_shrunk_to_the_long_edge_limit_keeping_its_ratio():
    prepared = svc._prepare_logo(_png((100, 2000)))

    assert (prepared.width_px, prepared.height_px) == (60, 1200)


def test_a_small_logo_is_never_enlarged():
    prepared = svc._prepare_logo(_png((120, 40)))

    assert (prepared.width_px, prepared.height_px) == (120, 40)


def test_transparency_survives_the_shrink():
    data = _png((2000, 1000), "RGBA", (255, 0, 0, 0))

    prepared = svc._prepare_logo(data)

    image = _open(prepared.data)
    assert image.format == "PNG"
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0


def test_a_palette_png_with_transparency_keeps_it():
    source = Image.new("P", (900, 300), 0)
    source.putpalette([0, 0, 0, 255, 0, 0])
    buffer = io.BytesIO()
    source.save(buffer, format="PNG", transparency=0)

    prepared = svc._prepare_logo(buffer.getvalue())

    image = _open(prepared.data)
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0


def test_a_webp_logo_becomes_a_png():
    buffer = io.BytesIO()
    Image.new("RGB", (2400, 1200), (10, 200, 10)).save(buffer, format="WEBP")

    prepared = svc._prepare_logo(buffer.getvalue())

    assert _open(prepared.data).format == "PNG"
    assert (prepared.width_px, prepared.height_px) == (1200, 600)


def test_a_jpeg_logo_stays_a_jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (2400, 1200), (200, 30, 30)).save(buffer, format="JPEG")

    prepared = svc._prepare_logo(buffer.getvalue())

    assert _open(prepared.data).format == "JPEG"
    assert (prepared.width_px, prepared.height_px) == (1200, 600)


def test_bytes_that_are_not_an_image_raise_a_decode_error():
    with pytest.raises((UnidentifiedImageError, OSError)):
        svc._prepare_logo(b"definitely not an image")


# --- logo placement --------------------------------------------------------------

PAGE_TOP = 8.0  # the top margin: where the title block starts without a logo
TABLE_START_WITHOUT_LOGO = 33.0


def _logo(width_px: int, height_px: int) -> svc._PreparedLogo:
    return svc._prepare_logo(_png((width_px, height_px), "RGBA", (30, 60, 160, 255)))


def _record_pdf_calls(monkeypatch):
    """Records the image, rect and cell calls _build_pdf makes (with the y position each is
    made at), and where the table starts."""
    calls: dict[str, list] = {"image": [], "rect": [], "cell": [], "table_y": []}
    real = {
        name: getattr(svc._ReportPdf, name)
        for name in ("image", "rect", "cell", "table")
    }

    def image(self, name, *args, **kwargs):
        calls["image"].append(kwargs)
        return real["image"](self, name, *args, **kwargs)

    def rect(self, *args, **kwargs):
        calls["rect"].append((args, tuple(sorted(kwargs.items()))))
        return real["rect"](self, *args, **kwargs)

    def cell(self, *args, **kwargs):
        calls["cell"].append(
            {"page": self.page_no(), "y": self.get_y(), "args": args, "kwargs": kwargs}
        )
        return real["cell"](self, *args, **kwargs)

    def table(self, *args, **kwargs):
        calls["table_y"].append(self.get_y())
        return real["table"](self, *args, **kwargs)

    for name, wrapper in (
        ("image", image),
        ("rect", rect),
        ("cell", cell),
        ("table", table),
    ):
        monkeypatch.setattr(svc._ReportPdf, name, wrapper)
    return calls


def _image_objects(pdf: bytes) -> int:
    return len(re.findall(rb"/Subtype\s*/Image", pdf))


def _title_cells(calls) -> dict[str, dict]:
    """The title and subtitle cells of page 1, by their text."""
    return {
        c["args"][2]: c
        for c in calls["cell"]
        if c["page"] == 1
        and len(c["args"]) > 2
        and c["args"][2] in ("Timesheet Report", "2026 Week 36")
    }


@pytest.mark.parametrize("size", [(600, 200), (30, 600), (200, 200), (225, 80)])
def test_the_logo_is_flush_right_at_the_content_top_and_fits_the_box(monkeypatch, size):
    calls = _record_pdf_calls(monkeypatch)
    logo = _logo(*size)

    svc._build_pdf([_row()], WEEK, "2026 Week 36", logo)

    (placed,) = calls["image"]
    width, height = placed["w"], placed["h"]
    assert placed["x"] + width == pytest.approx(
        297 - 8
    )  # right edge at the right margin
    assert placed["y"] == pytest.approx(
        PAGE_TOP + 1
    )  # where the accent bar's top is with no logo
    assert width <= 112.5 + 1e-9
    assert height <= 40 + 1e-9
    assert width / height == pytest.approx(logo.width_px / logo.height_px)
    # It fills the box along the limiting axis.
    assert width == pytest.approx(112.5) or height == pytest.approx(40)


def test_a_logo_is_drawn_once_even_when_the_report_has_three_pages(monkeypatch):
    calls = _record_pdf_calls(monkeypatch)
    rows = [_row(hours={MONTH[1]: "8"}) for _ in range(30)]

    pdf = svc._build_pdf(rows, MONTH, "August 2026", _logo(600, 200))

    assert _page_count(pdf) == 3
    assert len(calls["image"]) == 1
    # Embedded once in the file too (the alpha channel is a second image object).
    assert 1 <= _image_objects(pdf) <= 2


def test_a_pdf_has_an_image_with_a_logo_and_none_without():
    with_logo = svc._build_pdf([_row()], WEEK, "2026 Week 36", _logo(600, 200))
    without = svc._build_pdf([_row()], WEEK, "2026 Week 36")

    assert _image_objects(with_logo) >= 1
    assert _image_objects(without) == 0


def test_the_title_block_height_constant_matches_the_real_layout(monkeypatch):
    calls = _record_pdf_calls(monkeypatch)

    svc._build_pdf([_row()], WEEK, "2026 Week 36")

    bar_top = calls["rect"][0][0][1]
    subtitle = _title_cells(calls)["2026 Week 36"]
    subtitle_bottom = subtitle["y"] + subtitle["args"][1]
    assert subtitle_bottom - bar_top == pytest.approx(svc._TITLE_BLOCK_HEIGHT_MM)
    assert calls["table_y"][0] == pytest.approx(TABLE_START_WITHOUT_LOGO)
    assert calls["table_y"][0] - subtitle_bottom == pytest.approx(
        3
    )  # fixed gap below the subtitle


def test_a_full_height_logo_pulls_the_title_block_down_to_its_bottom(monkeypatch):
    calls = _record_pdf_calls(monkeypatch)

    svc._build_pdf([_row()], WEEK, "2026 Week 36", _logo(225, 80))  # 112.5 x 40 mm

    placed = calls["image"][0]
    logo_bottom = placed["y"] + placed["h"]
    assert logo_bottom == pytest.approx(PAGE_TOP + 1 + 40)
    subtitle = _title_cells(calls)["2026 Week 36"]
    # The subtitle ends level with the logo's bottom, and the table keeps its usual distance
    # below the subtitle (so 3 mm below the logo).
    assert subtitle["y"] + subtitle["args"][1] == pytest.approx(logo_bottom)
    assert calls["table_y"][0] == pytest.approx(logo_bottom + 3)


def test_the_title_block_keeps_its_shape_when_it_moves(monkeypatch):
    plain = _record_pdf_calls(monkeypatch)
    svc._build_pdf([_row()], WEEK, "2026 Week 36")
    plain_titles = _title_cells(plain)
    plain_bar = plain["rect"][0]

    moved = _record_pdf_calls(monkeypatch)
    svc._build_pdf([_row()], WEEK, "2026 Week 36", _logo(225, 80))
    moved_titles = _title_cells(moved)
    shift = moved["table_y"][0] - plain["table_y"][0]

    assert shift == pytest.approx(40 - svc._TITLE_BLOCK_HEIGHT_MM)
    for text, cell in plain_titles.items():
        assert moved_titles[text]["y"] == pytest.approx(cell["y"] + shift)
        assert moved_titles[text]["args"] == cell["args"]
    assert moved["rect"][0][0][1] == pytest.approx(plain_bar[0][1] + shift)


@pytest.mark.parametrize("size", [(600, 50), (400, 60), (1100, 200)])
def test_a_logo_no_taller_than_the_title_block_changes_nothing_else(monkeypatch, size):
    logo = _logo(*size)
    assert svc._logo_size_mm(logo)[1] <= svc._TITLE_BLOCK_HEIGHT_MM
    plain = _record_pdf_calls(monkeypatch)
    svc._build_pdf([_row()], WEEK, "2026 Week 36")
    plain_state = {k: list(v) for k, v in plain.items()}
    for value in plain.values():
        value.clear()

    svc._build_pdf([_row()], WEEK, "2026 Week 36", logo)

    assert plain["table_y"] == plain_state["table_y"] == [pytest.approx(33)]
    assert plain["rect"] == plain_state["rect"]
    assert plain["cell"] == plain_state["cell"]
