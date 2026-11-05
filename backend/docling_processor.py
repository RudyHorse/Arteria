"""Docling-based extraction.

Docling (IBM) parses PDFs into structured markdown + dataframes using
layout and table-structure models, with RapidOCR for scanned pages.
We parse the exported markdown pipe-tables (with `## section` tracking)
and fall back to the raw dataframes.
"""

import html
import json
import re

_converter = None
_error = None


def _get_converter():
    global _converter, _error
    if _converter is not None or _error is not None:
        return _converter
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.ocr_options = RapidOcrOptions(lang=["cyrillic"])
        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
    except Exception as e:
        _error = e
    return _converter


def is_available() -> bool:
    try:
        import docling  # noqa: F401
        return True
    except ImportError:
        return False


_SEPARATOR_RE = re.compile(r"^:?-+:?$")
_HEADER_CELL_RE = re.compile(
    r"название|показатель|результат|референс|reference|result|test",
    re.IGNORECASE)


def _is_separator(cells):
    return all(_SEPARATOR_RE.match(c.replace(" ", "")) for c in cells if c)


def _resolve_name(name, section):
    if not name or not section:
        return name
    try:
        from knowledge_base import is_generic_row_name
    except ImportError:
        return name
    return section if is_generic_row_name(name) else name


def _grid_from_md_rows(rows):
    """rows: list of (cells, section). Returns a grid or None."""
    header_idx = None
    for i, (cells, _sec) in enumerate(rows):
        joined = " ".join(cells)
        if _HEADER_CELL_RE.search(joined):
            header_idx = i
            break
    if header_idx is None:
        return None

    header = rows[header_idx][0]
    grid = [list(header)]
    for cells, section in rows[header_idx + 1:]:
        if not cells or not cells[0]:
            continue
        name = _resolve_name(cells[0], section)
        row = [name]
        row.extend(cells[1:4] if len(cells) > 1 else [])
        while len(row) < 4:
            row.append("")
        grid.append(row)
    return grid


def _parse_markdown_grids(md: str):
    grids = []
    section = None
    in_table = False
    rows = []

    def flush():
        nonlocal in_table, rows
        if in_table and rows:
            g = _grid_from_md_rows(rows)
            if g:
                grids.append(g)
        in_table = False
        rows = []

    for raw in md.splitlines():
        l = raw.strip()
        if l.startswith("#"):
            flush()
            section = l.lstrip("#").strip()
            continue
        if l.startswith("|"):
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            if _is_separator(cells):
                continue
            if not in_table:
                in_table = True
                rows = []
            if cells and cells[0]:
                rows.append((cells, section))
            elif rows:
                # continuation line of a wrapped cell
                prev_cells, prev_section = rows[-1]
                merged = []
                for i in range(len(prev_cells)):
                    part = cells[i] if i < len(cells) else ""
                    merged.append((prev_cells[i] + " " + part).strip())
                rows[-1] = (merged, prev_section)
            continue
        flush()
    flush()
    return grids


def _dataframe_grids(tables, only_noheader=False):
    grids = []
    for table in tables:
        try:
            df = table.export_to_dataframe()
        except Exception:
            continue
        cols = [str(c) for c in df.columns]
        has_header = bool(_HEADER_CELL_RE.search(" ".join(cols)))
        if only_noheader and has_header:
            continue
        if not has_header:
            cols = ["Название/показатель", "Результат",
                    "Референсные значения **", "Комментарий"][:len(cols)]
        grid = [cols]
        for row in df.itertuples(index=False, name=None):
            grid.append(["" if v is None else str(v) for v in row])
        if grid:
            grids.append(grid)
    return grids


def extract_docling_payload(pdf_path: str) -> dict:
    converter = _get_converter()
    if converter is None:
        raise RuntimeError(f"Docling unavailable: {_error}")

    result = converter.convert(pdf_path)
    md = html.unescape(result.document.export_to_markdown())

    lines = []
    for raw in md.splitlines():
        l = raw.strip()
        if l.startswith("|") or l.startswith("<!--") or not l:
            continue
        lines.append(l.lstrip("#").strip())

    from ocr_processor import _grids_from_lines_list

    grids = _parse_markdown_grids(md)
    # docling sometimes exports tables as plain text lines - reuse the
    # line-triplet parser on the markdown text (resolves section names)
    grids += _grids_from_lines_list(lines)

    # dataframe coverage only for tables/rows the markdown parsing missed
    covered = set()
    for g in grids:
        for row in g[1:]:
            covered.add((
                row[1].strip() if len(row) > 1 else "",
                row[2].strip() if len(row) > 2 else "",
            ))
    for g in _dataframe_grids(result.document.tables):
        kept = [g[0]]
        for row in g[1:]:
            key = (
                row[1].strip() if len(row) > 1 else "",
                row[2].strip() if len(row) > 2 else "",
            )
            if key in covered:
                continue
            kept.append(row)
        if len(kept) > 1:
            grids.append(kept)

    return {"mode": "docling", "lines": lines, "tables": grids}


def extract_text_from_pdf(pdf_path: str) -> str:
    """Same contract as ocr_processor.extract_text_from_pdf."""
    payload = extract_docling_payload(pdf_path)
    return json.dumps(payload, ensure_ascii=False)
