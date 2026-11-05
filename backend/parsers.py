"""Parser registry: multiple extraction backends, selectable per upload."""

from typing import List


def available_parsers() -> List[str]:
    parsers = ["local"]
    try:
        from docling_processor import is_available
        if is_available():
            parsers.append("docling")
    except Exception:
        pass
    return parsers


def extract_payload(pdf_path: str, parser: str = "local") -> str:
    """Extract PDF content with the selected parser, returning the JSON
    payload consumed by ocr_processor.parse_blood_analysis."""
    if parser == "docling":
        from docling_processor import extract_text_from_pdf
        return extract_text_from_pdf(pdf_path)
    from ocr_processor import extract_text_from_pdf
    return extract_text_from_pdf(pdf_path)
