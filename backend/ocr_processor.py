import os
import re
import json
import threading
from html.parser import HTMLParser
from typing import List, Optional

import fitz

from schemas import OCRResult, ResultBase


# ------------------------------------------------------------
# Lazy PaddleOCR engines (heavy init, created on first use)
# ------------------------------------------------------------
_paddle_lock = threading.Lock()
_ocr_engine = None
_table_engine = None
_paddle_error = None

_MIN_TEXT_LAYER_WORDS = 30

_OCR_DIGIT_MAP = str.maketrans({
    "з": "3", "З": "3", "о": "0", "О": "0", "б": "6",
    "l": "1", "I": "1", "|": "1", "S": "5", "s": "5",
})

_KEY_MAP = str.maketrans({
    "с": "c", "С": "C", "о": "o", "О": "O", "е": "e", "Е": "E",
    "а": "a", "А": "A", "р": "r", "Р": "R", "х": "x", "Х": "X",
    "у": "u", "У": "U", "м": "m", "М": "M", "н": "n", "Н": "N",
    "к": "k", "К": "K", "т": "t", "Т": "T", "в": "v", "В": "V",
    "и": "i", "И": "I", "h": "n", "H": "n", "ь": "", "ъ": "",
    "б": "b", "Б": "B", "г": "g", "Г": "G", "д": "d", "Д": "D",
    "ж": "j", "Ж": "J", "з": "z", "З": "Z", "й": "y", "Й": "Y",
    "л": "l", "Л": "L", "п": "p", "П": "P", "ф": "f", "Ф": "F",
    "ц": "c", "Ц": "C", "ч": "c", "Ч": "C", "ш": "s", "Ш": "S",
    "щ": "s", "Щ": "S", "э": "e", "Э": "E", "ю": "yu", "Ю": "Yu",
    "я": "ya", "Я": "Ya", "ы": "y", "Ы": "Y", "ё": "e", "Ё": "E",
})


def _norm_key(s: str) -> str:
    return s.lower().translate(_KEY_MAP)


_NAME_KWS = ["issledovan", "naimenovanie", "pokazatel", "test"]
_RESULT_KWS = ["rezultat", "znacenie", "znachenie", "result"]
_REF_KWS = ["min", "max", "maks", "makc", "referens", "referenc", "norm", "diapazon", "range"]
_COMMENT_KWS = ["kommentar", "ommentar", "primechan", "comment"]
_HEADER_ROW_KWS = [
    "laboratornie", "rezultat", "naimenovanie", "pokazatel",
    "reference", "result", "test",
]


def _get_ocr_engine():
    global _ocr_engine, _paddle_error
    if _ocr_engine is not None or _paddle_error is not None:
        return _ocr_engine
    with _paddle_lock:
        if _ocr_engine is None and _paddle_error is None:
            try:
                from paddleocr import PaddleOCR
                _ocr_engine = PaddleOCR(lang="cyrillic", show_log=False)
            except Exception as e:
                _paddle_error = e
    if _ocr_engine is None:
        raise RuntimeError(f"PaddleOCR unavailable: {_paddle_error}")
    return _ocr_engine


def _get_table_engine():
    global _table_engine, _paddle_error
    if _table_engine is not None or _paddle_error is not None:
        return _table_engine
    with _paddle_lock:
        if _table_engine is None and _paddle_error is None:
            try:
                from paddleocr import PPStructure
                _table_engine = PPStructure(
                    show_log=False, table=True, layout=False, ocr=False, lang="en"
                )
            except Exception as e:
                _paddle_error = e
    if _table_engine is None:
        raise RuntimeError(f"PaddleOCR unavailable: {_paddle_error}")
    return _table_engine


# ------------------------------------------------------------
# Main public functions
# ------------------------------------------------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract content from PDF.

    If the PDF has an embedded text layer, use it directly (exact),
    structured with PyMuPDF table finder. Otherwise run PaddleOCR
    (PP-OCRv3 cyrillic) with anchor-based table reconstruction.
    Returns a JSON payload consumed by parse_blood_analysis.
    """
    doc = fitz.open(pdf_path)
    try:
        words, lines = _extract_text_layer(doc)
        if len(words) >= _MIN_TEXT_LAYER_WORDS:
            tables = _grids_from_text_lines(doc)
            if not tables:
                tables = _grids_from_find_tables(doc, words)
            if not tables:
                tables = _grids_from_anchors_per_page(words)
            payload = {"mode": "textlayer", "lines": lines, "tables": tables}
        else:
            payload = _paddle_ocr_pages(doc, lines)
        return json.dumps(payload, ensure_ascii=False)
    finally:
        doc.close()


def parse_blood_analysis(json_text: str) -> OCRResult:
    """Parse the extraction payload into OCRResult."""
    payload = json.loads(json_text)

    lines = [str(l) for l in payload.get("lines", [])]

    patient_name = extract_patient_name(lines)
    analysis_date = extract_date(lines)
    study_type = extract_study_type(lines)
    conclusion = extract_conclusion(lines)

    results = _results_from_grids(payload.get("tables", []))
    results = _apply_knowledge(results)
    results = _dedup_results(results)

    return OCRResult(
        patient_name=patient_name or "Unknown",
        analysis_date=analysis_date or "2000-01-01",
        study_type=study_type or "General Blood Analysis",
        conclusion=conclusion,
        results=results,
    )


def _dedup_results(results: list) -> list:
    seen = set()
    unique = []
    for r in results:
        key = (_norm_key(r.test_name), r.result_value, r.result_text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def _apply_knowledge(results: list) -> list:
    try:
        from knowledge_base import resolve_parameter
    except ImportError:
        return results
    for r in results:
        canonical, unit = resolve_parameter(r.test_name)
        if canonical:
            r.test_name = canonical
        if unit and not r.unit:
            r.unit = unit
    return results


# ------------------------------------------------------------
# Text layer extraction (digital PDFs)
# ------------------------------------------------------------
def _extract_text_layer(doc) -> tuple:
    words = []
    lines = []
    for page_num, page in enumerate(doc):
        for w in page.get_text("words"):
            x0, y0, x1, y1, txt = w[0], w[1], w[2], w[3], w[4]
            if txt.strip():
                words.append({
                    "page": page_num,
                    "left": x0, "top": y0,
                    "width": x1 - x0, "height": y1 - y0,
                    "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2,
                    "text": txt,
                })
        for line in page.get_text("text").splitlines():
            line = line.strip()
            if line:
                lines.append(line)
    return words, lines


_HEADER_ROW_RE = re.compile(r"^Название/показатель$", re.IGNORECASE)
_METHOD_RE = re.compile(r"^Метод", re.IGNORECASE)
_STOP_RE = re.compile(
    r"^\**\s*Время|^\**\s*Референсные|^Отчет создан|^Страница|^Метод|^Комментарий|"
    r"^Подтверждение|^Заказ|^Образец|^Вид материала|^Регистрация|^Валидация|"
    r"^Контингент|^Заказчик|^Место|^Адрес|^Название/показатель",
    re.IGNORECASE)


def _grids_from_text_lines(doc) -> list:
    """Parse the common Russian lab-report line format from a PDF's
    text layer (see _grids_from_lines_list)."""
    grids = []
    for page in doc:
        lines = [l.strip() for l in page.get_text("text").splitlines()]
        grids.extend(_grids_from_lines_list(lines))
    return grids


def _grids_from_lines_list(lines: list) -> list:
    """Parse [section / method / header / name-result-ref triples] line format.

    Used by the local parser (PDF text layer) and by the docling parser
    (exported markdown, where some tables come out as plain text lines).
    """
    grids = []
    current_rows = []
    pending_section = None
    section = None
    in_table = False

    def flush():
        nonlocal current_rows
        if current_rows:
            grids.append([[
                "Название/показатель", "Результат",
                "Референсные значения **", "Комментарий",
            ]] + current_rows)
        current_rows = []

    i = 0
    skip_labels = 0
    while i < len(lines):
        l = lines[i]
        if not l:
            i += 1
            continue
        if i + 1 < len(lines) and _METHOD_RE.match(lines[i + 1]):
            pending_section = l
        if _HEADER_ROW_RE.match(l):
            if in_table:
                flush()
            section = pending_section
            in_table = True
            current_rows = []
            skip_labels = 2
            i += 1
            continue
        if in_table:
            if skip_labels > 0 and (
                    l == "Результат" or re.match(r"^\**\s*Референсные", l)):
                skip_labels -= 1
                i += 1
                continue
            if _STOP_RE.match(l):
                flush()
                in_table = False
                i += 1
                continue
            row, consumed = _parse_text_row(l, lines[i + 1:i + 5], section)
            if row:
                current_rows.append(row)
                i += consumed
                continue
            flush()
            in_table = False
            i += 1
            continue
        i += 1
    if in_table:
        flush()
    return grids


def _parse_text_row(name: str, nxt: list, section: str):
    """Try to read [name, result, reference] from text lines."""
    from knowledge_base import is_generic_row_name, is_text_result

    nxt = [n for n in nxt if n]
    if not nxt:
        return None, 1
    if _METHOD_RE.match(nxt[0]) or _STOP_RE.match(nxt[0]):
        return None, 1

    resolved = name
    if is_generic_row_name(name) and section:
        resolved = section

    # text result (serology): "HCV, антитела" / "ОТРИЦАТЕЛЬНЫЙ" / "отрицательный"
    if is_text_result(nxt[0]):
        result_raw = nxt[0]
        consumed = 2
        ref_raw = nxt[1] if len(nxt) > 1 and is_text_result(nxt[1]) else ""
        if ref_raw:
            consumed = 3
        return [resolved, result_raw, ref_raw, ""], consumed

    # numeric result directly after the name
    if re.search(r"\d", nxt[0]):
        result_raw = nxt[0]
        consumed = 2
        ref_raw = ""
        if len(nxt) > 1 and not _STOP_RE.match(nxt[1]) and (
                re.search(r"\d", nxt[1]) or is_text_result(nxt[1])):
            ref_raw = nxt[1]
            consumed = 3
        return [resolved, result_raw, ref_raw, ""], consumed

    # note line (e.g. "(расчетный показатель)") then numeric result
    if len(nxt) > 1 and re.search(r"\d", nxt[1]) and not _STOP_RE.match(nxt[1]):
        result_raw = nxt[1]
        consumed = 3
        ref_raw = ""
        if len(nxt) > 2 and not _STOP_RE.match(nxt[2]) and (
                re.search(r"\d", nxt[2]) or is_text_result(nxt[2])):
            ref_raw = nxt[2]
            consumed = 4
        return [resolved, result_raw, ref_raw, ""], consumed

    return None, 1


def _grids_from_find_tables(doc, words: list) -> list:
    grids = []
    for page_num, page in enumerate(doc):
        try:
            ft = page.find_tables()
        except Exception:
            continue
        page_words = [w for w in words if w["page"] == page_num]
        for t in ft.tables:
            grid = _grid_from_table_cells(t, page_words)
            if grid:
                grids.append(grid)
    return grids


def _grid_from_table_cells(table, page_words: list) -> list:
    row_count, col_count = table.row_count, table.col_count
    if row_count < 2 or col_count < 2:
        return []
    grid = [[""] * col_count for _ in range(row_count)]
    cells = table.cells
    for idx, cell in enumerate(cells):
        bbox = cell.bbox if hasattr(cell, "bbox") else tuple(cell)
        x0, y0, x1, y1 = bbox
        r = idx % row_count
        c = idx // row_count
        if r >= row_count or c >= col_count:
            continue
        parts = []
        for w in page_words:
            if (w["left"] >= x0 - 2 and w["top"] >= y0 - 2 and
                    w["left"] + w["width"] <= x1 + 2 and
                    w["top"] + w["height"] <= y1 + 2):
                parts.append(w["text"])
        grid[r][c] = " ".join(parts).strip()
    return grid


# ------------------------------------------------------------
# Anchor-based table reconstruction (shared: text words / OCR lines)
# ------------------------------------------------------------
_HEADER_KW = re.compile(
    r"Лабораторные|Результат|Наименование|Показатель|"
    r"Reference|Result|Test|Комментар|"
    r"[МM][иu][нnH][\.:]|[МM]a[kx][сc][\.:]", re.IGNORECASE)
_TABLE_TOP_KW = re.compile(r"Лабораторные|исследования", re.IGNORECASE)
_TABLE_BOTTOM_KW = re.compile(
    r"Обращаем|обрашаем|Оригинал|оригинал", re.IGNORECASE)


def _grids_from_anchors_per_page(words: list) -> list:
    grids = []
    pages = sorted({w["page"] for w in words})
    for p in pages:
        grid = _grid_from_anchors([w for w in words if w["page"] == p])
        if grid:
            grids.append(grid)
    return grids


def _grid_from_anchors(items: list) -> list:
    """Build a table grid from positioned text pieces.

    Anchors rows on the leftmost (name) column: each new row starts where
    a new name text appears. Columns come from the header row clustered
    by horizontal gaps. Thresholds are relative to median text height,
    so it works for any resolution.
    """
    if not items:
        return []

    heights = sorted(w["height"] for w in items)
    med_h = heights[len(heights) // 2] if heights else 10
    med_h = max(med_h, 1.0)

    # table region
    table_top = None
    table_bottom = None
    for w in items:
        if _TABLE_TOP_KW.search(w["text"]):
            table_top = w["top"] if table_top is None else min(table_top, w["top"])
        if _TABLE_BOTTOM_KW.search(w["text"]):
            table_bottom = w["top"] if table_bottom is None else min(table_bottom, w["top"])

    if table_top is None:
        return []

    region = [w for w in items
              if w["top"] >= table_top - 3 and
              (table_bottom is None or w["top"] <= table_bottom - 3)]

    # header band: keyword items clustered near the top of the table
    header_kw_items = [w for w in region if _HEADER_KW.search(w["text"])]
    if not header_kw_items:
        return []
    header_kw_items.sort(key=lambda w: w["top"])
    kw_top_min = header_kw_items[0]["top"]
    header_kw_items = [w for w in header_kw_items
                       if w["top"] <= kw_top_min + 1.5 * med_h]
    if not header_kw_items:
        return []
    header_bottom = max(w["top"] + w["height"] for w in header_kw_items)
    header_items = [w for w in region if w["top"] <= header_bottom + 0.3 * med_h]
    header_items.sort(key=lambda w: w["left"])

    # columns: cluster header items by x0 gaps
    columns = []
    for w in header_items:
        if not columns or w["left"] - columns[-1]["x1"] > 0.75 * med_h:
            columns.append({"x0": w["left"], "x1": w["left"] + w["width"], "items": [w]})
        else:
            c = columns[-1]
            c["x1"] = max(c["x1"], w["left"] + w["width"])
            c["items"].append(w)
    if len(columns) < 2:
        return []

    header_texts = [" ".join(w["text"] for w in sorted(c["items"], key=lambda w: w["top"]))
                    for c in columns]
    name_col = 0
    for i, ht in enumerate(header_texts):
        if any(kw in _norm_key(ht) for kw in _NAME_KWS):
            name_col = i
            break

    # row anchors: name-column items below the header band
    anchors = []
    for w in region:
        if w["top"] > header_bottom and _in_column(w, columns[name_col]):
            anchors.append(w)
    anchors.sort(key=lambda w: (w["top"], w["left"]))

    anchor_groups = []
    for w in anchors:
        if (anchor_groups and
                w["top"] - anchor_groups[-1]["bottom"] <= 0.5 * med_h):
            g = anchor_groups[-1]
            g["bottom"] = max(g["bottom"], w["top"] + w["height"])
            g["top"] = min(g["top"], w["top"])
        else:
            anchor_groups.append({"top": w["top"], "bottom": w["top"] + w["height"]})

    if not anchor_groups:
        return []

    boundaries = []
    for a, b in zip(anchor_groups[:-1], anchor_groups[1:]):
        boundaries.append((a["top"] + b["top"]) / 2)

    # build grid
    grid = [[""] * len(columns) for _ in range(len(anchor_groups) + 1)]

    def col_of(w):
        best, best_overlap = -1, -1.0
        for i, c in enumerate(columns):
            overlap = min(w["left"] + w["width"], c["x1"]) - max(w["left"], c["x0"])
            if overlap > best_overlap:
                best, best_overlap = i, overlap
        return best

    def row_of(w):
        r = 0
        for b in boundaries:
            if w["top"] >= b:
                r += 1
            else:
                break
        return r

    for w in header_items:
        ci = col_of(w)
        if ci >= 0:
            grid[0][ci] = (grid[0][ci] + " " + w["text"]).strip()

    data = [w for w in region if w["top"] > header_bottom]
    data.sort(key=lambda w: (w["top"], w["left"]))
    for w in data:
        ri = row_of(w) + 1
        ci = col_of(w)
        if 0 <= ri < len(grid) and ci >= 0:
            grid[ri][ci] = (grid[ri][ci] + " " + w["text"]).strip()

    return grid


def _in_column(w, col) -> bool:
    return w["left"] + w["width"] >= col["x0"] - 2 and w["left"] <= col["x1"] + 2


# ------------------------------------------------------------
# PaddleOCR extraction (scanned PDFs)
# ------------------------------------------------------------
def _paddle_ocr_pages(doc, header_lines: list) -> dict:
    ocr = _get_ocr_engine()

    all_lines = list(header_lines)
    tables = []

    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = _png_to_numpy(pix.tobytes("png"))

        lines = _ocr_text_lines(ocr, img)
        all_lines.extend([t for (_, _, _, _, t) in lines])

        items = [{
            "page": 0,
            "left": x0, "top": y0,
            "width": x1 - x0, "height": y1 - y0,
            "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2,
            "text": t,
        } for (x0, y0, x1, y1, t) in lines]

        grid = _grid_from_anchors(items)
        if not grid:
            grid = _grid_from_ppstructure(img, lines)
        if grid:
            tables.append(grid)

    return {"mode": "paddle", "lines": all_lines, "tables": tables}


def _png_to_numpy(png: bytes):
    import cv2
    import numpy as np
    arr = np.frombuffer(png, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _ocr_text_lines(ocr, img) -> list:
    lines = []
    res = ocr.ocr(img, cls=False)
    for page in res or []:
        for box, (text, score) in page:
            if score < 0.5 or not text.strip():
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append((min(xs), min(ys), max(xs), max(ys), text.strip()))
    return lines


def _grid_from_ppstructure(img, ocr_lines: list) -> list:
    try:
        engine = _get_table_engine()
        res = engine(img)
    except Exception:
        return []
    for r in res or []:
        if r.get("type") != "table":
            continue
        inner = r.get("res", {})
        html = inner.get("html", "")
        cell_bbox = inner.get("cell_bbox", [])
        if not html:
            continue
        grid = _table_html_to_grid(html, cell_bbox, ocr_lines)
        if grid:
            return grid
    return []


# ------------------------------------------------------------
# PP-Structure HTML table -> cell grid
# ------------------------------------------------------------
class _TdParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tds = []
        self._table_depth = 0
        self._row = 0
        self._col = 0
        self._in_cell = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table_depth += 1
        elif tag == "tr" and self._table_depth == 1:
            self._row += 1
            self._col = 0
        elif tag in ("td", "th") and self._table_depth == 1:
            self._in_cell = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell and self._table_depth == 1:
            self.tds.append({
                "row": self._row - 1,
                "col": self._col,
                "text": "".join(self._buf).strip(),
            })
            self._col += 1
            self._in_cell = False
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1

    def handle_data(self, data):
        if self._in_cell:
            self._buf.append(data)


def _table_html_to_grid(html: str, cell_bbox: list, ocr_lines: list) -> list:
    parser = _TdParser()
    try:
        parser.feed(html)
    except Exception:
        return []

    tds = parser.tds
    if not tds:
        return []

    rows = max(td["row"] for td in tds) + 1
    cols = max(td["col"] for td in tds) + 1
    grid = [[""] * cols for _ in range(rows)]

    for i, td in enumerate(tds):
        if td["row"] >= rows or td["col"] >= cols:
            continue
        bbox = cell_bbox[i] if i < len(cell_bbox) else None
        text = td["text"] if not bbox else _lines_in_bbox(ocr_lines, bbox)
        grid[td["row"]][td["col"]] = text

    return grid


def _lines_in_bbox(lines: list, bbox: list, pad: float = 6.0) -> str:
    x0, y0, x1, y1 = bbox
    parts = []
    for (lx0, ly0, lx1, ly1, txt) in lines:
        if lx0 >= x0 - pad and ly0 >= y0 - pad and lx1 <= x1 + pad and ly1 <= y1 + pad:
            parts.append(txt)
    return " ".join(parts)


# ------------------------------------------------------------
# Shared row-grid -> results logic
# ------------------------------------------------------------
def _results_from_grids(tables: list) -> list:
    results = []
    for grid in tables:
        results.extend(_rows_to_results(grid))
    return results


def _looks_numeric(s: str) -> bool:
    s = (s or "").strip()
    if not s or not re.search(r"\d", s):
        return False
    return re.match(r"^[\d<>,\.\-\+хx*× ]+", s) is not None


_NOISE = ["rezultat", "referens", "referenc", "laboratorn", "znacenie", "znachenie", "pokazatel"]


def _is_noise_name(name: str) -> bool:
    if not name or len(name.strip()) < 2:
        return True
    if any(kw in _norm_key(name) for kw in _NOISE):
        return True
    if re.match(r"^[\d<>,\.\-\+хx*× ]+", name.strip()):
        return True
    return False


def _rows_to_results(rows: list) -> list:
    if not rows:
        return []

    header_idx = None
    for i, row in enumerate(rows):
        texts = " ".join(c for c in row if c)
        if re.search(
            r"(?:Лабораторные|Результат|Мин\.|Макс\.|Наименование|Показатель|"
            r"Reference|Result|Test)",
            texts,
            re.IGNORECASE,
        ) or any(kw in _norm_key(texts) for kw in _HEADER_ROW_KWS):
            header_idx = i
            break

    if header_idx is None:
        # transposed layout without keywords: [names][values][ranges] blocks
        for i, row in enumerate(rows[:-1]):
            if rows[i + 1] and any(_looks_numeric(str(c)) for c in rows[i + 1][1:] if str(c).strip()):
                header_idx = i
                break
        if header_idx is None:
            return []
        col_map = {"name": 0, "result": 1, "ref": 2, "comment": 3}
    else:
        header = [str(c).lower() for c in rows[header_idx]]
        col_map = {}
        for i, ht in enumerate(header):
            ht_norm = _norm_key(ht)
            if any(kw in ht_norm for kw in _NAME_KWS):
                col_map.setdefault("name", i)
            elif any(kw in ht_norm for kw in _RESULT_KWS):
                col_map.setdefault("result", i)
            elif any(kw in ht_norm for kw in _REF_KWS):
                col_map.setdefault("ref", i)
            elif any(kw in ht_norm for kw in _COMMENT_KWS):
                col_map.setdefault("comment", i)

        if "name" not in col_map:
            col_map = {"name": 0, "result": 1, "ref": 2, "comment": 3}
        if "comment" not in col_map and len(header) > 3:
            col_map["comment"] = len(header) - 1

    def cell(row, key):
        i = col_map.get(key, -1)
        if i < 0 or i >= len(row):
            return ""
        return str(row[i]).strip()

    results = []
    i = header_idx
    first = True
    while i < len(rows):
        row = rows[i]
        if not row:
            i += 1
            continue
        n0 = _norm_key(str(row[0])).strip()

        if n0 == "rezultat" or n0.startswith(("referens", "referenc")):
            i += 1
            continue

        # transposed block: name row followed by values row
        if i + 1 < len(rows) and rows[i + 1]:
            n1 = _norm_key(str(rows[i + 1][0])).strip()
            nxt = rows[i + 1]
            transposed = (n1 == "rezultat" or _looks_numeric(nxt[0]))
            if not transposed and not str(nxt[0]).strip():
                transposed = any(_looks_numeric(str(c)) for c in nxt[1:] if str(c).strip())
            if transposed:
                hdr, val = row, nxt
                ref = None
                if i + 2 < len(rows) and rows[i + 2]:
                    cand = rows[i + 2]
                    n2 = _norm_key(str(cand[0])).strip()
                    if (n2.startswith(("referens", "referenc")) or
                            _looks_numeric(cand[0]) or
                            any(_looks_numeric(str(c)) for c in cand[1:] if str(c).strip())):
                        ref = cand

                if n1 == "rezultat" and ref is None:
                    # variant B: value in header row, name/ref in values row
                    for j in range(1, len(hdr)):
                        if not re.search(r"\d", str(hdr[j])):
                            continue
                        result_raw = str(hdr[j]).strip()
                        ref_raw = str(val[j]).strip() if j < len(val) else ""
                        name = ""
                        for k in range(1, len(hdr)):
                            if k == j:
                                continue
                            hk = _norm_key(str(hdr[k]))
                            if hk.startswith(("referens", "referenc")) or "pokazatel" in hk or "nazvanie" in hk:
                                name = str(val[k]).strip() if k < len(val) else ""
                                break
                        if not name and len(val) > 1:
                            name = str(val[1]).strip()
                        if _is_noise_name(name):
                            continue
                        r = _build_result(name, result_raw, ref_raw, "")
                        if r:
                            results.append(r)
                    i += 2
                    continue

                for j in range(len(hdr)):
                    name = str(hdr[j]).strip() if j < len(hdr) else ""
                    result_raw = str(val[j]).strip() if j < len(val) else ""
                    ref_raw = str(ref[j]).strip() if ref and j < len(ref) else ""
                    if not result_raw or _is_noise_name(name):
                        continue
                    r = _build_result(name, result_raw, ref_raw, "")
                    if r:
                        results.append(r)
                i += 3 if ref is not None else 2
                continue

        if first:
            first = False
            i += 1
            continue

        name = cell(row, "name")
        result_raw = cell(row, "result")
        ref_raw = cell(row, "ref")
        comment = cell(row, "comment")

        if result_raw and not _is_noise_name(name):
            r = _build_result(name, result_raw, ref_raw, comment)
            if r:
                results.append(r)
        i += 1

    return results


# ------------------------------------------------------------
# Result building
# ------------------------------------------------------------
_MIN_RE = re.compile(r"(?:Мин|[МM][иu][нnhH])[\.:]*\s*([\d][\d,\.]*)")
_MAX_RE = re.compile(r"(?:Макс|[МM]a[kкKxх][сcC]|[МM]a[кx][сc])[\.:]*\s*([\d][\d,\.]*)")


def _normalize_digits(s: str) -> str:
    def fix(tok):
        if re.fullmatch(r"[\d,\.\sзЗоОобб6Фф5SslI1|+<>-]*", tok) and \
                re.search(r"[\dзЗоОобб6Фф5SslI1|]", tok):
            tok = tok.translate(_OCR_DIGIT_MAP)
            tok = re.sub(r"Ф(?=\d)|(?<=\d)Ф", "2", tok)
        return tok
    return "".join(fix(t) for t in re.split(r"(\s+)", s))


def _build_result(name: str, result_raw: str, ref_raw: str, comment: str) -> Optional[ResultBase]:
    result_norm = _normalize_digits(result_raw)
    result_value = None
    num = re.search(r"(\d[\d,.]*)", result_norm)
    if num:
        try:
            result_value = float(num.group(1).replace(",", "."))
        except ValueError:
            pass

    ref_norm = _normalize_digits(ref_raw)
    ref_min, ref_max = None, None
    m_min = _MIN_RE.search(ref_norm)
    m_max = _MAX_RE.search(ref_norm)
    if m_min:
        ref_min = float(m_min.group(1).replace(",", "."))
    if m_max:
        ref_max = float(m_max.group(1).replace(",", "."))
    if ref_min is None and ref_max is None:
        rm = re.search(r"(\d[\d,.]*)\s*[-–]\s*(\d[\d,.]*)", ref_norm)
        if rm:
            ref_min = float(rm.group(1).replace(",", "."))
            ref_max = float(rm.group(2).replace(",", "."))

    unit = _extract_unit(result_raw + " " + ref_raw)

    is_abnormal = False
    if result_value is not None and ref_min is not None and ref_max is not None:
        is_abnormal = result_value < ref_min or result_value > ref_max
    combined = (comment + " " + ref_raw).lower()
    if not is_abnormal and any(kw in combined for kw in ["понижен", "повышен"]):
        is_abnormal = True

    ref_text = ""
    if ref_min is not None and ref_max is not None:
        ref_text = f"{ref_min} – {ref_max} {unit or ''}".strip()
    elif ref_min is not None:
        ref_text = f"> {ref_min} {unit or ''}".strip()
    elif ref_max is not None:
        ref_text = f"< {ref_max} {unit or ''}".strip()
    else:
        ref_text = ref_raw

    return ResultBase(
        test_name=name,
        result_value=result_value,
        result_text=result_raw if result_raw else None,
        reference_min=ref_min,
        reference_max=ref_max,
        reference_text=ref_text if ref_text else None,
        unit=unit,
        is_abnormal=is_abnormal,
    )


# ------------------------------------------------------------
# Header text extraction
# ------------------------------------------------------------
def extract_patient_name(lines: list) -> Optional[str]:
    for line in lines[:5]:
        m = re.match(r"^([А-ЯЁ][А-ЯЁA-Z\- .]{2,})\s+\((?:Муж|Жен)", line)
        if m:
            return m.group(1).strip()
    patterns = [
        r"(?:patient|name|ФИО|пациент|имя|больной|фамилия)\s*:?\s*(.+)",
        r"(?:Ф\.?И\.?О\.?)\s*:?\s*(.+)",
        r"^(?:Пациент|Patient|Больной)\s+(.+)$",
    ]
    for line in lines:
        for p in patterns:
            m = re.search(p, line, re.IGNORECASE)
            if m:
                return m.group(1).strip()
    return None


def extract_date(lines: list) -> Optional[str]:
    candidates = []
    for line in lines:
        for m in re.finditer(r"(\d{2})[./:\-](\d{2})[./:\-](\d{4})", line):
            d, mo, y = m.group(1), m.group(2), m.group(3)
            if not (1900 <= int(y) <= 2100):
                continue
            score = 3 if re.search(r"зарегистрирован|регистраци", line, re.IGNORECASE) else (
                2 if int(y) >= 2000 else 1)
            candidates.append((score, f"{y}-{mo}-{d}"))
    if candidates:
        candidates.sort(key=lambda c: -c[0])
        return candidates[0][1]

    patterns = [
        r"(?:date|дата|analysis date|дата анализа|Дата выполнения)\s*:?\s*(\d{2}[./:\-]\d{2}[./:\-]\d{2,4})",
        r"(\d{2}[./:\-]\d{2}[./:\-]\d{4})",
        r"(\d{4}[./:\-]\d{2}[./:\-]\d{2})",
    ]
    for line in lines:
        for p in patterns:
            m = re.search(p, line, re.IGNORECASE)
            if m:
                raw = m.group(1).replace(".", "-").replace("/", "-").replace(":", "-")
                parts = raw.split("-")
                if len(parts[0]) == 4:
                    return f"{parts[0]}-{parts[1]}-{parts[2]}"
                day, month, year = parts[0], parts[1], parts[2]
                if len(year) == 2:
                    year = "20" + year
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return None


def extract_study_type(lines: list) -> Optional[str]:
    for line in lines:
        if len(line) > 120:
            continue
        if re.search(r"(?:Общий анализ|Общеклинический анализ|Анализ крови|Биохимический анализ)", line, re.IGNORECASE):
            return line.strip()
    for line in lines:
        if len(line) > 120:
            continue
        if re.search(r"(?:Исследование|Анализ|Определение)", line, re.IGNORECASE) and \
                not re.match(r"^Исследование выполнено", line, re.IGNORECASE):
            return line.strip()
    return None


def extract_conclusion(lines: list) -> Optional[str]:
    parts = []
    for line in lines:
        lower = line.lower()
        if any(w in lower for w in ["понижен", "повышен", "в норме", "ормаль", "норма", "отклонен"]):
            parts.append(line)
    return " ".join(parts) if parts else None


def _extract_unit(text: str) -> Optional[str]:
    if not text:
        return None
    if "10^9" in text:
        return "*10^9/л"
    if "10^12" in text:
        return "*10^12/л"
    if re.search(r"[Мм]иллимоль", text) or re.search(r"mmol", text, re.IGNORECASE):
        return "ммоль/л"
    if re.search(r"[Мм]кмоль", text) or re.search(r"umol|мкмоль", text, re.IGNORECASE):
        return "мкмоль/л"
    if re.search(r"[Мм]моль", text) or re.search(r"mol", text, re.IGNORECASE):
        return "ммоль/л" if re.search(r"[Мм]моль", text) else "моль/л"
    if re.search(r"мл/мин", text):
        return "мл/мин/1,73м^2"
    if re.search(r"мм/ч", text):
        return "мм/ч"
    if re.search(r"нг/мл", text):
        return "нг/мл"
    if re.search(r"мг/дл", text):
        return "мг/дл"
    if re.search(r"мг/л", text):
        return "мг/л"
    if re.search(r"пг/мл", text):
        return "пг/мл"
    if re.search(r"[Фф][Ллl1]|[Ff][Ll]", text):
        return "fL"
    if re.search(r"[Пп]г", text):
        return "пг"
    if re.search(r"Единица действия", text):
        return "Ед/л"
    if re.search(r"[ЕE]диниц[аa]", text):
        return "Ед/л"
    if re.search(r"[ЕE]д/л", text) or re.search(r"U/L", text, re.IGNORECASE):
        return "Ед/л"
    if re.search(r"г/л", text) or re.search(r"g/L", text, re.IGNORECASE):
        return "г/л"
    if "%" in text:
        return "%"
    return None
