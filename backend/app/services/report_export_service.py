"""Reporting screen's export: GET /time-entries/report/export. Three formats: pdf,
xlsx, csv."""

import asyncio
import io
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from fpdf import FPDF
from fpdf.enums import TableBordersLayout, TableBorderStyle, TableCellStyle
from fpdf.fonts import FontFace
from fpdf.util import Padding
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User
from app.schemas.time_entry import TimesheetReportRowOut
from app.services import file_storage_service
from app.services.time_entry_service import _pm_project_ids, list_time_entries_report

logger = logging.getLogger(__name__)

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


# PDF palette: slate for text and surfaces, one indigo accent (title bar and the hours heatmap).
_COLOR_TEXT = (0x0F, 0x17, 0x2A)  # primary text, title, and the strong table rules
_COLOR_TEXT_LABEL = (0x33, 0x41, 0x55)  # label column: project in bold, detail lines regular
_COLOR_TEXT_SECONDARY = (0x47, 0x55, 0x69)  # subtitle
_COLOR_TEXT_MUTED = (0x94, 0xA3, 0xB8)  # header weekday letters, footer
_COLOR_HAIRLINE = (0xE2, 0xE8, 0xF0)  # separators between data rows, left edge of Total column
_COLOR_SURFACE = (0xF8, 0xFA, 0xFC)  # header and Total rows
_COLOR_WEEKEND = (0xF1, 0xF5, 0xF9)  # Saturday/Sunday cells of data rows without hours
_COLOR_ACCENT = (0x4F, 0x46, 0xE5)  # indigo
_COLOR_PAGE = (0xFF, 0xFF, 0xFF)  # cells without a tint
_HEAT_PALE = (0xEE, 0xF2, 0xFF)  # tint of a day with 1 hour logged
_HEAT_STRONG = (0xA5, 0xB4, 0xFC)  # tint of a day with 8 hours or more
_HEAT_MIN_HOURS = Decimal(1)
_HEAT_MAX_HOURS = Decimal(8)

_RULE_THICKNESS_MM = 0.3  # under the header row and above the Total row
_HAIRLINE_THICKNESS_MM = 0.1


def _heat_color(hours: Decimal) -> tuple[int, int, int]:
    """Background tint for a day with logged hours: pale at 1 hour, deepening linearly to
    its strongest at 8 hours, and flat beyond that (so a very long day does not wash out
    the dark text). Anything under 1 hour gets the pale tint, since a day with any hours
    must still be visibly tinted."""
    span = _HEAT_MAX_HOURS - _HEAT_MIN_HOURS
    amount = min(max((hours - _HEAT_MIN_HOURS) / span, Decimal(0)), Decimal(1))
    red, green, blue = (
        round(pale + (strong - pale) * float(amount))
        for pale, strong in zip(_HEAT_PALE, _HEAT_STRONG, strict=True)
    )
    return red, green, blue


_LOGO_MAX_WIDTH_MM = 112.5
_LOGO_MAX_HEIGHT_MM = 40.0
# The title block, from the top of the accent bar to the bottom of the subtitle: the 3 mm
# between bar and title, the title line and the subtitle line of _build_pdf. A logo taller than
# this pushes the block down by the difference (a test pins this to the real layout).
_TITLE_BLOCK_HEIGHT_MM = 3.0 + 11.0 + 7.0
# Long edge of the logo as embedded: about 270 dpi across the full 112.5 mm box width, crisp in
# print, while a 25-megapixel upload would otherwise be embedded whole in every export.
_LOGO_MAX_EDGE_PX = 1200


@dataclass(frozen=True)
class _PreparedLogo:
    """A logo ready to embed in the PDF, with its pixel size (which placement needs)."""

    data: bytes
    width_px: int
    height_px: int


def _prepare_logo(data: bytes) -> _PreparedLogo:
    """Shrinks the stored logo to what the PDF needs: long edge at most 1200 px (never
    enlarged, aspect ratio kept). A JPEG stays a JPEG (no transparency to lose, and
    photographs stay small); anything else, WebP included, becomes a PNG, which keeps
    transparency and is read by fpdf2 without any extra format support.

    Raises Pillow's decode errors (UnidentifiedImageError, OSError, ...) for bytes that are
    not a readable image; the caller decides what that means for the export.
    """
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        keep_jpeg = source.format == "JPEG"
        image: Image.Image = source
        # Palette and bilevel images resize badly (nearest-neighbour), so go to a true-colour
        # mode first, keeping transparency where the image has it.
        if image.mode not in ("RGB", "RGBA", "L", "LA"):
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            image = image.convert("RGBA" if has_alpha else "RGB")
        image = image.copy()
    image.thumbnail((_LOGO_MAX_EDGE_PX, _LOGO_MAX_EDGE_PX), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    if keep_jpeg:
        image.convert("RGB").save(buffer, format="JPEG", quality=90)
    else:
        image.save(buffer, format="PNG", optimize=True)
    return _PreparedLogo(buffer.getvalue(), image.width, image.height)


class _TimesheetBordersLayout(TableBordersLayout):
    """No vertical lines and no outer frame: a hairline above each data row, a heavier rule
    under the header (the top of the first data row) and above the Total row, and a faint
    left edge on the last (Total) column.

    Every separator is a cell's *top* border rather than the previous row's bottom one:
    rows are filled as they are drawn, so a bottom border would have its lower half painted
    over by the next row's fill, while a top border is drawn after the row above it.
    """

    def cell_style_getter(
        self,
        row_idx: int,
        col_idx: int,
        col_pos: int,
        num_heading_rows: int,
        num_rows: int,
        num_col_idx: int,
        num_col_pos: int,
    ) -> TableCellStyle:
        rule = TableBorderStyle(thickness=_RULE_THICKNESS_MM, color=_COLOR_TEXT)
        hairline = TableBorderStyle(thickness=_HAIRLINE_THICKNESS_MM, color=_COLOR_HAIRLINE)
        is_total_row = row_idx == num_rows - 1
        is_first_body_row = row_idx == num_heading_rows

        top: bool | TableBorderStyle = False
        if is_total_row or is_first_body_row:
            top = rule
        elif row_idx > num_heading_rows:
            top = hairline
        return TableCellStyle(
            left=hairline if col_idx == num_col_idx - 1 and col_idx > 0 else False,
            bottom=rule if is_total_row else False,
            right=False,
            top=top,
        )


class _ReportPdf(FPDF):
    def footer(self) -> None:
        self.set_y(-7)
        self.set_font("LiberationSans", size=7)
        self.set_text_color(*_COLOR_TEXT_MUTED)
        # "{nb}" is replaced with the total page count when the document is finished.
        self.cell(0, 4, f"Page {self.page_no()} / {{nb}}", align="C")


_WEEKDAY_LETTERS = ["M", "T", "W", "T", "F", "S", "S"]  # Monday-first, per this app's ISO-8601 rule
_WEEKEND_INDICES = {5, 6}  # Saturday, Sunday, per _WEEKDAY_LETTERS' Monday-first ordering

_CELL_PADDING_MM = 1.8  # top and bottom of every cell, for breathing room between rows


def _logo_size_mm(logo: _PreparedLogo) -> tuple[float, float]:
    """The logo's size on the page: as large as fits the 112.5 x 40 mm box at its own aspect
    ratio (never stretched or cropped)."""
    width = min(_LOGO_MAX_WIDTH_MM, _LOGO_MAX_HEIGHT_MM * logo.width_px / logo.height_px)
    return width, width * logo.height_px / logo.width_px


def _build_pdf(
    rows: list[TimesheetReportRowOut],
    days: list[date],
    period_label: str,
    logo: _PreparedLogo | None = None,
) -> bytes:
    pdf = _ReportPdf(orientation="L", unit="mm", format="A4")
    pdf.set_margins(left=8, top=8, right=8)
    # The bottom margin leaves room for the page footer, which sits inside it.
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.alias_nb_pages()
    pdf.add_font("LiberationSans", "", _liberation_font_path("LiberationSans-Regular.ttf"))
    pdf.add_font("LiberationSans", "B", _liberation_font_path("LiberationSans-Bold.ttf"))
    pdf.add_page()

    page_top = pdf.get_y()
    # How far the title block moves down: a logo taller than the block would otherwise leave a
    # wide gap between the title and the table, so the block's bottom is lined up with the
    # logo's and the table (a fixed distance below the subtitle) follows the logo.
    title_block_shift = 0.0
    if logo is not None:
        # First page only, drawn here rather than from a page header so later pages keep their
        # full height. Flush right at the margin (not centred in its box, which would leave a
        # narrow logo floating inside it), with its top where the accent bar's top is without a
        # logo.
        logo_w, logo_h = _logo_size_mm(logo)
        pdf.image(
            io.BytesIO(logo.data),
            x=pdf.w - pdf.r_margin - logo_w,
            y=page_top + 1,
            w=logo_w,
            h=logo_h,
        )
        title_block_shift = max(0.0, logo_h - _TITLE_BLOCK_HEIGHT_MM)
    pdf.set_y(page_top + title_block_shift)

    # A short accent bar above the title, the one splash of the accent colour outside the
    # hours heatmap.
    pdf.set_fill_color(*_COLOR_ACCENT)
    pdf.rect(pdf.l_margin, pdf.get_y() + 1, 10, 1.2, style="F")
    # Back to white: a table cell that sets no fill of its own would inherit the accent.
    pdf.set_fill_color(*_COLOR_PAGE)
    pdf.set_y(pdf.get_y() + 4)

    pdf.set_font("LiberationSans", style="B", size=22)
    pdf.set_text_color(*_COLOR_TEXT)
    pdf.cell(0, 11, "Timesheet Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("LiberationSans", size=11)
    pdf.set_text_color(*_COLOR_TEXT_SECONDARY)
    pdf.cell(0, 7, period_label, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_text_color(*_COLOR_TEXT)

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
    cell_padding = Padding(
        top=_CELL_PADDING_MM, right=0, bottom=_CELL_PADDING_MM, left=0
    )

    def font(
        size_pt: float,
        *,
        bold: bool = False,
        color: tuple[int, int, int] = _COLOR_TEXT,
        fill: tuple[int, int, int] = _COLOR_PAGE,
    ) -> FontFace:
        return FontFace(
            family="LiberationSans",
            size_pt=size_pt,
            emphasis="B" if bold else "",
            color=color,
            fill_color=fill,
        )

    entries_by_row = _entries_by_row(rows)

    with pdf.table(
        col_widths=col_widths,
        borders_layout=_TimesheetBordersLayout(),
        first_row_as_headings=True,
        text_align="CENTER",
        markdown=True,
        line_height=line_height,
        padding=cell_padding,
    ) as table:
        header_style = font(7, bold=True, color=_COLOR_TEXT_SECONDARY, fill=_COLOR_SURFACE)
        header_row = table.row()
        header_row.cell("Timesheet", style=header_style, align="LEFT")
        for day in days:
            weekday_letter = _WEEKDAY_LETTERS[day.weekday()]
            header_row.cell(f"{weekday_letter}\n{day.day}", style=header_style)
        header_row.cell("Total", style=header_style)

        day_totals = {day: Decimal(0) for day in days}
        grand_total = Decimal(0)

        for row in rows:
            data_row = table.row()
            # Truncate each line to roughly what the 45mm label column can hold at
            # 8pt, the same idea as the live grid's CSS truncate, done by hand
            # since fpdf2 has no text-overflow equivalent.
            project_name = _truncate(row.project_name, 28)
            service_line_name = _truncate(row.service_line_name or "", 28)
            consultant_name = _truncate(row.full_name, 28)
            label_text = f"**{project_name}**\n{service_line_name}\n{consultant_name}"
            # One text colour per cell is all fpdf2 allows, so only the project name stands
            # out (bold), against the regular detail lines.
            data_row.cell(label_text, style=font(8, color=_COLOR_TEXT_LABEL), align="LEFT")

            entries = entries_by_row.get((row.user_id, row.service_line_id), {})
            period_total = Decimal(0)
            for day in days:
                hours = entries.get(day)
                # Logged hours get the heatmap tint. A weekend day without any is tinted
                # grey, on data rows only: the header and Total rows never are.
                if hours is not None and hours > 0:
                    fill = _heat_color(hours)
                elif day.weekday() in _WEEKEND_INDICES:
                    fill = _COLOR_WEEKEND
                else:
                    fill = _COLOR_PAGE
                data_row.cell(
                    _format_hours(hours) if hours is not None else "", style=font(7, fill=fill)
                )
                if hours is not None:
                    period_total += hours
                    day_totals[day] += hours
                    grand_total += hours
            # Unlike a mid-grid cell (blank when there's nothing logged, matching
            # the live grid), the Total column always shows a value, "0h"
            # included: same `formatHours(x) || "0"` convention the live grid's
            # own total cells already use.
            data_row.cell(f"{_format_hours(period_total) or '0'}h", style=font(7, bold=True))

        # Bottom Total row: per-day sums across every row shown, plus a grand
        # total: same as the live grid's own bottom row. Same light fill as the
        # header, on every column, weekend columns included.
        total_style = font(7, bold=True, fill=_COLOR_SURFACE)
        total_row = table.row()
        total_row.cell("Total", style=total_style, align="LEFT")
        for day in days:
            total_row.cell(_format_hours(day_totals[day]) or "0", style=total_style)
        total_row.cell(f"{_format_hours(grand_total) or '0'}h", style=total_style)

    return bytes(pdf.output())


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


# CSV/Excel formula injection (CWE-1236): a cell whose text starts with one of
# these opens it as a formula in Excel/LibreOffice rather than literal text
# (e.g. a project/service-line/consultant name of `=HYPERLINK(...)`). None of
# project_name/service_line_name/full_name have a character restriction, and
# all three are written verbatim into cells below, so every one of them has to
# go through _escape_formula_prefix first, in both the XLSX and CSV builders.
_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _escape_formula_prefix(text: str) -> str:
    # A leading apostrophe forces Excel/LibreOffice to treat the rest of the
    # cell as literal text, never a formula, and the apostrophe itself is
    # never displayed or exported back out, unlike quoting the whole value.
    if text.startswith(_FORMULA_TRIGGER_CHARS):
        return "'" + text
    return text


_DETAILS_COLUMNS = ["Project Name", "Service Line", "Consultant", "Date", "Hours"]


def _build_details_dataframe(rows: list[TimesheetReportRowOut]) -> pd.DataFrame:
    """Flattens each row's `entries` sub-array: a row with no entries in the
    requested period contributes nothing."""
    records = [
        {
            "Project Name": _escape_formula_prefix(row.project_name),
            "Service Line": _escape_formula_prefix(row.service_line_name or ""),
            "Consultant": _escape_formula_prefix(row.full_name),
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
    # special-casing this one download. No semicolon delimiter either: hours already
    # use `.` as the decimal separator, so there's no comma clash to work around.
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
    page-width constraint forcing that.
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
            "Project": _escape_formula_prefix(row.project_name),
            "Service Line": _escape_formula_prefix(row.service_line_name or ""),
            "Consultant": _escape_formula_prefix(row.full_name),
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
    # matches hours' 0.5-increment convention.
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


async def _load_logo(db: AsyncSession) -> _PreparedLogo | None:
    """The organization logo, ready to embed, or None when there is none or it cannot be used.

    The logo is optional decoration, so unlike the font (a wrong font silently changes the
    report) a logo that is recorded but unreadable never fails an export: it is logged and the
    PDF is produced without it. Read as the system, not as the requesting user, so every
    project manager who can export gets it, administrator or not.
    """
    try:
        data = await file_storage_service.read_setting_file_bytes(db, "org_logo")
        if data is None:
            return None
        return await asyncio.to_thread(_prepare_logo, data)
    except (
        OSError,  # missing or unreadable disk file; also Pillow's UnidentifiedImageError
        ValueError,
        SyntaxError,  # Pillow's error for some corrupt PNGs
        Image.DecompressionBombError,
        UnidentifiedImageError,
        file_storage_service.StoragePathError,
    ) as err:
        # The error type only: no file name or content, and the message of an OSError can
        # carry the storage path.
        logger.warning("Organization logo left out of the PDF export: %s", type(err).__name__)
        return None


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
        file_bytes = _build_pdf(rows, days, period_label, await _load_logo(db))
    elif export_format == "xlsx":
        file_bytes = _build_xlsx(rows, days)
    else:
        file_bytes = _build_csv(rows)
    return file_bytes, filename, SUPPORTED_FORMATS[export_format]
