"""Reporting screen's export: GET /time-entries/report/export. Three formats: pdf,
xlsx, csv."""

import io
import os
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from fpdf import FPDF
from fpdf.drawing_primitives import DeviceRGB
from fpdf.enums import TableBordersLayout
from fpdf.fonts import FontFace
from fpdf.util import Padding
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User
from app.schemas.time_entry import TimesheetReportRowOut
from app.services.time_entry_service import _pm_project_ids, list_time_entries_report

SUPPORTED_FORMATS = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text


def _period_label_and_slug_source(period_type: str, start_date: date) -> tuple[str, str]:
    """Returns (display label, the raw string to slugify for the filename): the
    same value for a month ("August 2026"), but a week's filename/title need the
    ISO year leading ("2026 Week 36") since "Week 36" alone is meaningless once
    it's a standalone document with no surrounding app context to supply the
    year."""
    if period_type == "month":
        label = start_date.strftime("%B %Y")
        return label, label
    iso_year, iso_week, _ = start_date.isocalendar()
    label = f"{iso_year} Week {iso_week}"
    return label, label


async def _build_export_filename(
    db: AsyncSession,
    project_manager: User,
    period_type: str,
    start_date: date,
    project_ids: list[uuid.UUID] | None,
    consultant_ids: list[uuid.UUID] | None,
    extension: str,
) -> str:
    _label, slug_source = _period_label_and_slug_source(period_type, start_date)
    parts = [slugify(slug_source)]

    # "Single Project selected" means the filter itself, not the query's actual
    # result rows, but still checked against the caller's own scope, so a
    # tampered/out-of-scope id can't leak a project name into the filename.
    if project_ids and len(project_ids) == 1:
        pm_project_ids = await _pm_project_ids(db, project_manager.id)
        if project_ids[0] in pm_project_ids:
            project = await db.get(Project, project_ids[0])
            if project is not None:
                parts.append(slugify(project.name)[:30])

    if consultant_ids and len(consultant_ids) == 1:
        user = await db.get(User, consultant_ids[0])
        if user is not None:
            parts.append(slugify(user.full_name)[:20])

    return f"{'_'.join(parts)}.{extension}"


# fonts-liberation installs to a different parent directory depending on distro,
# Debian/Ubuntu (this app's actual container) vs. Arch and others (local dev
# machines), check both rather than hardcoding one.
_LIBERATION_SANS_DIRS = [
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/liberation",
]


def _liberation_font_path(filename: str) -> str:
    for directory in _LIBERATION_SANS_DIRS:
        candidate = os.path.join(directory, filename)
        if os.path.exists(candidate):
            return candidate
    raise RuntimeError(
        f"Liberation Sans font file {filename!r} not found in any of {_LIBERATION_SANS_DIRS}"
        ": install the fonts-liberation (Debian/Ubuntu) or ttf-liberation (Arch) package."
    )


# "#446" (CSS 3-digit shorthand, each hex digit doubled) -> #444466, used for
# borders and the subtitle text only now (revised: no longer used as a cell fill
# see _WEEKEND_FILL below).
_ACCENT_COLOR = (0x44, 0x44, 0x66)
_HEADER_FILL = (0xF0, 0xFF, 0xFF)  # Azure: header row and the bottom Total row
_ROW_FILL_EVEN = (0xFF, 0xFF, 0xFF)  # white
_ROW_FILL_ODD = (0xF8, 0xF8, 0xFF)  # GhostWhite
_WEEKEND_FILL = (0xDC, 0xDC, 0xDC)  # Gainsboro: Saturday/Sunday override, data rows only
_BLACK_TEXT = (0x00, 0x00, 0x00)
_PAGE_BACKGROUND = (0xFF, 0xFF, 0xFF)
_TABLE_CORNER_RADIUS = 1.5  # mm: small enough to stay inside a cell's own padding

_WEEKDAY_LETTERS = ["M", "T", "W", "T", "F", "S", "S"]  # Monday-first, per this app's ISO-8601 rule
_WEEKEND_INDICES = {5, 6}  # Saturday, Sunday, per _WEEKDAY_LETTERS' Monday-first ordering


def _build_pdf(rows: list[TimesheetReportRowOut], days: list[date], period_label: str) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_margins(left=8, top=8, right=8)
    pdf.set_auto_page_break(auto=True, margin=8)
    pdf.add_font("LiberationSans", "", _liberation_font_path("LiberationSans-Regular.ttf"))
    pdf.add_font("LiberationSans", "B", _liberation_font_path("LiberationSans-Bold.ttf"))
    pdf.add_page()

    pdf.set_font("LiberationSans", style="B", size=25)
    pdf.set_text_color(*_BLACK_TEXT)
    pdf.cell(0, 12, "Timesheet Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("LiberationSans", size=13)
    pdf.set_text_color(*_ACCENT_COLOR)
    pdf.cell(0, 8, period_label, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(*_BLACK_TEXT)
    pdf.set_draw_color(*_ACCENT_COLOR)
    pdf.set_line_width(0.1)

    label_w = 45.0
    total_w = 14.0
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    # Split evenly across however many days this period actually has: a Week
    # export gets roomy columns, only a 31-day month hits the tightest (~7.2mm)
    # case the font size below was chosen for.
    day_w = (usable_w - label_w - total_w) / len(days)
    col_widths = [label_w, *([day_w] * len(days)), total_w]

    # fpdf2's table() defaults line_height to 2x the font size, which produced a
    # very wide gap between a day header's weekday letter and day number, and
    # between the label column's three stacked lines: set explicitly, from the
    # larger of the two font sizes in play (8pt), for single-line spacing on both.
    line_height = 8 * 1.1 / pdf.k
    # Half a line of top/bottom breathing room per cell, so rows don't look
    # cramped against their own borders: left/right stay flush, only requested
    # for top/bottom.
    cell_padding = Padding(top=line_height / 2, right=0, bottom=line_height / 2, left=0)

    def font(size_pt: float, *, bold: bool = False, fill: tuple[int, int, int] | None = None) -> FontFace:
        return FontFace(
            family="LiberationSans",
            size_pt=size_pt,
            emphasis="B" if bold else None,
            fill_color=fill,
        )

    entries_by_row = _entries_by_row(rows)

    table_start_page = pdf.page_no()
    table_start_y = pdf.get_y()

    with pdf.table(
        col_widths=col_widths,
        borders_layout=TableBordersLayout.ALL,
        first_row_as_headings=True,
        text_align="CENTER",
        markdown=True,
        line_height=line_height,
        padding=cell_padding,
    ) as table:
        header_row = table.row()
        header_row.cell("Timesheet", style=font(7, fill=_HEADER_FILL), align="LEFT")
        for day in days:
            weekday_letter = _WEEKDAY_LETTERS[day.weekday()]
            header_row.cell(f"{weekday_letter}\n{day.day}", style=font(7, fill=_HEADER_FILL))
        header_row.cell("Total", style=font(7, fill=_HEADER_FILL))

        day_totals = {day: Decimal(0) for day in days}
        grand_total = Decimal(0)

        for row_index, row in enumerate(rows):
            data_row = table.row()
            row_fill = _ROW_FILL_EVEN if row_index % 2 == 0 else _ROW_FILL_ODD
            # Truncate each line to roughly what the 45mm label column can hold at
            # 8pt, the same idea as the live grid's CSS truncate, done by hand
            # since fpdf2 has no text-overflow equivalent.
            project_name = _truncate(row.project_name, 28)
            service_line_name = _truncate(row.service_line_name or "", 28)
            consultant_name = _truncate(row.full_name, 28)
            label_text = f"**{project_name}**\n{service_line_name}\n{consultant_name}"
            data_row.cell(label_text, style=font(8, fill=row_fill), align="LEFT")

            entries = entries_by_row.get((row.user_id, row.service_line_id), {})
            period_total = Decimal(0)
            for day in days:
                hours = entries.get(day)
                # Saturday/Sunday always override the row's own banding, on data
                # rows only: never the header/Total rows, which keep their Azure
                # fill regardless of which weekday a column falls on. Gainsboro is
                # light enough that text stays plain black, unlike the earlier
                # dark #446 version this replaced.
                is_weekend = day.weekday() in _WEEKEND_INDICES
                cell_style = FontFace(
                    family="LiberationSans",
                    size_pt=7,
                    fill_color=_WEEKEND_FILL if is_weekend else row_fill,
                    color=_BLACK_TEXT,
                )
                data_row.cell(
                    _format_hours(hours) if hours is not None else "", style=cell_style
                )
                if hours is not None:
                    period_total += hours
                    day_totals[day] += hours
                    grand_total += hours
            # Unlike a mid-grid cell (blank when there's nothing logged, matching
            # the live grid), the Total column always shows a value, "0h"
            # included: same `formatHours(x) || "0"` convention the live grid's
            # own total cells already use.
            data_row.cell(f"{_format_hours(period_total) or '0'}h", style=font(7, fill=row_fill))

        # Bottom Total row: per-day sums across every row shown, plus a grand
        # total: same as the live grid's own bottom row. Same LightSteelBlue
        # fill as the header, on every column, weekend columns included.
        total_row = table.row()
        total_row.cell("Total", style=font(7, bold=True, fill=_HEADER_FILL), align="LEFT")
        for day in days:
            total_row.cell(
                _format_hours(day_totals[day]) or "0",
                style=font(7, bold=True, fill=_HEADER_FILL),
            )
        total_row.cell(
            f"{_format_hours(grand_total) or '0'}h",
            style=font(7, bold=True, fill=_HEADER_FILL),
        )

    # Rounded corners, matching the live grid's own rounded container: fpdf2's
    # table() always draws a square grid, so the outer frame above is a plain
    # ALL-bordered rectangle on every page (always correct, including across a
    # page break). On top of that, when the whole table fits on one page, paint
    # small white squares over its 4 corner intersections (erasing the square
    # artifact) and stroke a rounded rectangle over the same bounding box: the
    # straight edges land exactly on the grid's own already-correct border, only
    # the corners actually change appearance. Skipped for a table spanning
    # multiple pages: there's no single closed rectangle to round in that case
    # (see reporting.md's own note on this).
    if pdf.page_no() == table_start_page:
        _round_table_corners(
            pdf,
            x=pdf.l_margin,
            y=table_start_y,
            w=usable_w,
            h=pdf.get_y() - table_start_y,
        )

    return bytes(pdf.output())


def _round_table_corners(pdf: FPDF, *, x: float, y: float, w: float, h: float) -> None:
    r = _TABLE_CORNER_RADIUS
    # Each corner's "sliver", the bit of the old square corner that falls
    # outside the rounded curve, is traced as its own single closed vector
    # path (corner point -> tangent point -> the real rounding arc, same
    # radius `r` the visible stroke below uses -> other tangent point ->
    # close) and filled with the page background. This only ever touches
    # that sliver, never the curve's interior, important because the
    # interior can hold cell text close enough to the corner to matter (e.g.
    # the bottom row's "Total" label, right at the bottom-left corner): any
    # flat-color mask shaped as a plain square or circle instead of this
    # exact sliver either leaves the old square corner poking out past the
    # curve, or paints over content, fill or text, that the rounded corner
    # should never have touched. The straight legs extend a touch past the
    # table's nominal box (into the page margin, harmless) so the mask also
    # swallows the table border's own stroke-width bleed past (x, y, w, h)
    # fpdf2 centers stroke width on the path.
    pad = 0.15
    background = DeviceRGB(*(c / 255 for c in _PAGE_BACKGROUND))
    # (corner point, inward-x sign, inward-y sign): the sign pair points
    # from the corner into the table, and the sliver's two straight legs and
    # arc are all derived from it.
    corners = (
        (x, y, 1, 1),  # top-left
        (x + w, y, -1, 1),  # top-right
        (x, y + h, 1, -1),  # bottom-left
        (x + w, y + h, -1, -1),  # bottom-right
    )
    for px, py, dx, dy in corners:
        outer_x, outer_y = px - dx * pad, py - dy * pad
        tangent1 = (px + dx * r, py)
        tangent2 = (px, py + dy * r)
        # The arc's sweep direction has to flip between diagonally-opposite
        # corner pairs (top-left/bottom-right vs. top-right/bottom-left):
        # mirroring the corner mirrors which of the two same-radius arcs
        # between the tangent points bulges toward the true corner, which is
        # the one that traces the actual sliver instead of a small stray
        # lens near the middle of the curve.
        with pdf.new_path() as path:
            path.style.fill_color = background
            path.style.stroke_color = None
            path.move_to(outer_x, outer_y)
            path.line_to(tangent1[0], outer_y)
            path.line_to(*tangent1)
            path.arc_to(
                r, r, 0, large_arc=False, positive_sweep=dx * dy < 0, x=tangent2[0], y=tangent2[1]
            )
            path.line_to(outer_x, tangent2[1])
            path.close()
    pdf.set_draw_color(*_ACCENT_COLOR)
    pdf.set_line_width(0.1)
    pdf.rect(x, y, w, h, style="D", round_corners=True, corner_radius=r)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _format_hours(value: Decimal) -> str:
    if value == 0:
        return ""
    normalized = value.normalize()
    # Decimal.normalize() can produce exponential notation for a whole number
    # (e.g. Decimal("8.00").normalize() == Decimal("8E+0")): str() on that isn't
    # the plain "8" this needs, so go through a float for display formatting only.
    return f"{float(normalized):g}"


def _entries_by_row(
    rows: list[TimesheetReportRowOut],
) -> dict[tuple[uuid.UUID, uuid.UUID], dict[date, Decimal]]:
    return {
        (row.user_id, row.service_line_id): {entry.date: entry.hours for entry in row.entries}
        for row in rows
    }


_DETAILS_COLUMNS = ["Project Name", "Service Line", "Consultant", "Date", "Hours"]


def _build_details_dataframe(rows: list[TimesheetReportRowOut]) -> pd.DataFrame:
    """Flattens each row's `entries` sub-array: a row with no entries in the
    requested period contributes nothing (see reporting.md's Details section)."""
    records = [
        {
            "Project Name": row.project_name,
            "Service Line": row.service_line_name or "",
            "Consultant": row.full_name,
            "Date": entry.date,
            "Hours": float(entry.hours),
        }
        for row in rows
        for entry in row.entries
    ]
    return pd.DataFrame.from_records(records, columns=_DETAILS_COLUMNS)


def _build_csv(rows: list[TimesheetReportRowOut]) -> bytes:
    details_df = _build_details_dataframe(rows)
    # Plain UTF-8, no BOM: matches this app's other text responses rather than
    # special-casing this one download (see reporting.md's CSV Export section).
    return details_df.to_csv(index=False, float_format="%.1f").encode("utf-8")


_REPORT_LABEL_COLUMNS = ["Project", "Service Line", "Consultant"]
_XLSX_HEADER_FILL = "F0FFFF"  # Azure: header row and the bottom Total row
_XLSX_ROW_FILL_EVEN = "FFFFFF"  # white
_XLSX_ROW_FILL_ODD = "F8F8FF"  # GhostWhite
_XLSX_WEEKEND_FILL = "DCDCDC"  # Gainsboro: Saturday/Sunday override, data rows only
_XLSX_WEEKEND_INDICES = {5, 6}  # Saturday, Sunday


def _fill(hex_color: str) -> PatternFill:
    return PatternFill(fill_type="solid", start_color=hex_color, end_color=hex_color)


def _build_report_dataframe(
    rows: list[TimesheetReportRowOut], days: list[date], day_headers: list[str]
) -> tuple[pd.DataFrame, list[str]]:
    """A natural Excel layout, separate Project/Service Line/Consultant columns,
    not the PDF's single merged 3-line label column, since Excel has no printed
    page-width constraint forcing that (see reporting.md's XLSX Export section).
    Carries over only the PDF's *color* formatting rules, applied separately by
    _style_report_sheet, this just builds the row data, including the bottom
    Total row."""
    columns = [*_REPORT_LABEL_COLUMNS, *day_headers, "Total"]
    entries_by_row = _entries_by_row(rows)

    day_totals = {day: Decimal(0) for day in days}
    grand_total = Decimal(0)
    records = []
    for row in rows:
        entries = entries_by_row.get((row.user_id, row.service_line_id), {})
        record: dict[str, object] = {
            "Project": row.project_name,
            "Service Line": row.service_line_name or "",
            "Consultant": row.full_name,
        }
        period_total = Decimal(0)
        for day, header in zip(days, day_headers, strict=True):
            hours = entries.get(day)
            # Blank for a gap or an explicit zero entry, same as the PDF's
            # _format_hours convention, but still counted into the totals below.
            record[header] = float(hours) if hours else float("nan")
            if hours is not None:
                period_total += hours
                day_totals[day] += hours
                grand_total += hours
        record["Total"] = float(period_total)
        records.append(record)

    total_record: dict[str, object] = {"Project": "Total", "Service Line": "", "Consultant": ""}
    for day, header in zip(days, day_headers, strict=True):
        total_record[header] = float(day_totals[day])
    total_record["Total"] = float(grand_total)
    records.append(total_record)

    return pd.DataFrame.from_records(records, columns=columns), columns


def _style_report_sheet(
    ws: Worksheet, columns: list[str], num_data_rows: int, days: list[date]
) -> None:
    header_row = 1
    total_row = num_data_rows + 2
    day_column_start = len(_REPORT_LABEL_COLUMNS) + 1  # 1-indexed

    for col_index in range(1, len(columns) + 1):
        ws.cell(row=header_row, column=col_index).fill = _fill(_XLSX_HEADER_FILL)
        ws.cell(row=total_row, column=col_index).fill = _fill(_XLSX_HEADER_FILL)

    for data_offset in range(num_data_rows):
        excel_row = header_row + 1 + data_offset
        row_fill = _XLSX_ROW_FILL_EVEN if data_offset % 2 == 0 else _XLSX_ROW_FILL_ODD
        for col_index in range(1, len(columns) + 1):
            day_index = col_index - day_column_start
            is_weekend = 0 <= day_index < len(days) and days[day_index].weekday() in (
                _XLSX_WEEKEND_INDICES
            )
            ws.cell(row=excel_row, column=col_index).fill = _fill(
                _XLSX_WEEKEND_FILL if is_weekend else row_fill
            )

    # One decimal place throughout the day/Total columns, data and Total rows:
    # matches hours' existing 0.5-increment convention (see reporting.md).
    for excel_row in [*range(header_row + 1, total_row), total_row]:
        for col_index in range(day_column_start, len(columns) + 1):
            ws.cell(row=excel_row, column=col_index).number_format = "0.0"


def _autofit_columns(ws: Worksheet) -> None:
    for col_index, column_cells in enumerate(ws.columns, start=1):
        length = max(
            (len(str(cell.value)) for cell in column_cells if cell.value is not None), default=0
        )
        ws.column_dimensions[get_column_letter(col_index)].width = length + 2


def _build_xlsx(rows: list[TimesheetReportRowOut], days: list[date]) -> bytes:
    day_headers = [day.strftime("%a %d") for day in days]
    report_df, report_columns = _build_report_dataframe(rows, days, day_headers)
    details_df = _build_details_dataframe(rows)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        report_df.to_excel(writer, sheet_name="Report", index=False)
        details_df.to_excel(writer, sheet_name="Details", index=False)

        _style_report_sheet(writer.sheets["Report"], report_columns, len(rows), days)
        _autofit_columns(writer.sheets["Report"])

        hours_column = _DETAILS_COLUMNS.index("Hours") + 1
        for excel_row in range(2, len(details_df) + 2):
            writer.sheets["Details"].cell(row=excel_row, column=hours_column).number_format = (
                "0.0"
            )
        _autofit_columns(writer.sheets["Details"])

    return buffer.getvalue()


async def build_report_export(
    db: AsyncSession,
    project_manager: User,
    *,
    export_format: str,
    period_type: str,
    start_date: date,
    end_date: date,
    project_ids: list[uuid.UUID] | None,
    service_line_ids: list[uuid.UUID] | None,
    consultant_ids: list[uuid.UUID] | None,
    statuses: list[str] | None,
) -> tuple[bytes, str, str]:
    """Returns (file bytes, filename, content type). Always re-queries the
    database fresh via list_time_entries_report, never a client-supplied
    payload of already-rendered rows, so an unblurred, not-yet-saved cell edit
    in the browser can never appear in an export."""
    rows = await list_time_entries_report(
        db,
        project_manager,
        start_date,
        end_date,
        project_ids,
        service_line_ids,
        consultant_ids,
        statuses,
    )
    day_count = (end_date - start_date).days
    days = [start_date + timedelta(days=i) for i in range(day_count + 1)]

    period_label, _slug_source = _period_label_and_slug_source(period_type, start_date)
    filename = await _build_export_filename(
        db, project_manager, period_type, start_date, project_ids, consultant_ids, export_format
    )

    if export_format == "pdf":
        file_bytes = _build_pdf(rows, days, period_label)
    elif export_format == "xlsx":
        file_bytes = _build_xlsx(rows, days)
    else:
        file_bytes = _build_csv(rows)
    return file_bytes, filename, SUPPORTED_FORMATS[export_format]
