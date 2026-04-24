from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import fitz

MIN_FRAGMENT_LENGTH = 8
MIN_TOKEN_LENGTH = 4
REDACTION_FONT_SIZE = 8
MIN_REDACTION_FONT_SIZE = 3.0
REPLACEMENT_TEXT_BY_TYPE: dict[str, str] = {
    "email": "dummy.user@example.test",
    "phone": "9000000000",
    "address": "123 Dummy Street, Test City 100001",
    "id_number": "DUMMY-ID-0001",
    "bank_details": "Account 000000000000, IFSC DUMY0000001",
    "medical": "Routine follow-up advised",
    "legal": "Contract reference updated",
    "secret": "Internal reference only",
    "other": "Dummy confidential value",
}


def _build_search_terms(value: str) -> list[str]:
    raw = value.strip()
    if not raw:
        return []

    terms: list[str] = []
    seen: set[str] = set()

    def push(term: str) -> None:
        normalized = term.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        terms.append(normalized)

    push(raw)
    push(re.sub(r"\s+", " ", raw))

    for line in raw.splitlines():
        if len(line.strip()) >= MIN_FRAGMENT_LENGTH:
            push(line)

    for part in re.split(r"[,;\n]", raw):
        if len(part.strip()) >= MIN_FRAGMENT_LENGTH:
            push(part)

    return terms


def _resolve_page_index(page_number: int, page_count: int) -> int | None:
    if 0 <= page_number < page_count:
        return page_number
    if 1 <= page_number <= page_count:
        return page_number - 1
    return None


def _build_token_terms(value: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9@._/-]+", value)
    terms: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        cleaned = token.strip()
        if len(cleaned) < MIN_TOKEN_LENGTH:
            continue
        if not any(ch.isdigit() for ch in cleaned) and len(cleaned) < 6 and "@" not in cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(cleaned)
    return terms


def _pick_replacement_text(value_type: Any, _source_text: str) -> str:
    normalized_type = str(value_type).strip().lower() or "other"
    return REPLACEMENT_TEXT_BY_TYPE.get(normalized_type, REPLACEMENT_TEXT_BY_TYPE["other"])


def _search_rects(page: fitz.Page, term: str) -> list[fitz.Rect]:
    variants = [term, term.lower(), term.upper(), term.title()]
    unique_variants: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        key = variant.strip()
        if not key:
            continue
        normalized = key.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_variants.append(key)

    rects: list[fitz.Rect] = []
    for variant in unique_variants:
        rects.extend(
            page.search_for(
                variant,
                flags=fitz.TEXT_DEHYPHENATE | fitz.TEXT_PRESERVE_WHITESPACE,
            )
        )
    unique_rects: list[fitz.Rect] = []
    seen_rects: set[tuple[float, float, float, float]] = set()
    for rect in rects:
        key = (
            round(rect.x0, 2),
            round(rect.y0, 2),
            round(rect.x1, 2),
            round(rect.y1, 2),
        )
        if key in seen_rects:
            continue
        seen_rects.add(key)
        unique_rects.append(rect)
    return unique_rects


def _significantly_overlaps(rect: fitz.Rect, existing_rects: list[fitz.Rect]) -> bool:
    area = rect.width * rect.height
    if area <= 0:
        return False
    for existing in existing_rects:
        intersection = rect & existing
        if intersection.is_empty:
            continue
        overlap_ratio = (intersection.width * intersection.height) / area
        if overlap_ratio >= 0.7:
            return True
    return False


def _pick_source_font_size(page: fitz.Page, rect: fitz.Rect) -> float | None:
    text_dict = page.get_text("dict", clip=rect)
    span_sizes: list[float] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size")
                if isinstance(size, (int, float)) and size > 0:
                    span_sizes.append(float(size))
    if not span_sizes:
        return None
    return max(span_sizes)


def _pick_font_size(rect: fitz.Rect, text: str, preferred_size: float | None = None) -> float:
    if not text.strip():
        return MIN_REDACTION_FONT_SIZE
    if preferred_size is None:
        preferred_size = min(REDACTION_FONT_SIZE, max(MIN_REDACTION_FONT_SIZE, rect.height * 0.8))

    size = max(MIN_REDACTION_FONT_SIZE, preferred_size)
    text_width = fitz.get_text_length(text, fontname="helv", fontsize=size)
    if text_width <= rect.width * 0.98:
        return size

    while size >= MIN_REDACTION_FONT_SIZE:
        text_width = fitz.get_text_length(text, fontname="helv", fontsize=size)
        if text_width <= rect.width * 0.98:
            return size
        size -= 0.5
    return MIN_REDACTION_FONT_SIZE


def _insert_replacement_text(
    page: fitz.Page, rect: fitz.Rect, text: str, source_font_size: float | None
) -> None:
    if not text.strip():
        return

    preferred_size = None
    if source_font_size is not None:
        preferred_size = max(MIN_REDACTION_FONT_SIZE, source_font_size)

    if preferred_size is not None:
        remaining_height = page.insert_textbox(
            rect,
            text,
            fontname="helv",
            fontsize=preferred_size,
            color=(0, 0, 0),
            align=fitz.TEXT_ALIGN_LEFT,
        )
        if remaining_height >= 0:
            return

        # Keep the original visual size when possible, even if text is wider.
        page.insert_text(
            (rect.x0, rect.y1 - 1),
            text,
            fontname="helv",
            fontsize=preferred_size,
            color=(0, 0, 0),
        )
        return

    page.insert_textbox(
        rect,
        text,
        fontname="helv",
        fontsize=_pick_font_size(rect, text, preferred_size),
        color=(0, 0, 0),
        align=fitz.TEXT_ALIGN_LEFT,
    )


def redact_pdf_by_findings(
    file_bytes: bytes, confidential_findings: list[dict[str, Any]]
) -> bytes:
    document = fitz.open(stream=BytesIO(file_bytes), filetype="pdf")
    try:
        for page_result in confidential_findings:
            page_number = int(page_result.get("page_number", -1))
            page_index = _resolve_page_index(page_number, document.page_count)
            if page_index is None:
                continue

            page = document[page_index]
            findings = page_result.get("findings", [])
            if not isinstance(findings, list):
                continue

            has_redaction = False
            replacements: list[tuple[fitz.Rect, str, float | None]] = []
            scheduled_rects: list[fitz.Rect] = []
            for finding in findings:
                if not isinstance(finding, dict):
                    continue

                value = str(finding.get("value", "")).strip()
                if not value:
                    continue

                finding_matched = False
                finding_type = finding.get("type", "other")
                for term in _build_search_terms(value):
                    for rect in _search_rects(page, term):
                        if _significantly_overlaps(rect, scheduled_rects):
                            continue
                        source_font_size = _pick_source_font_size(page, rect)
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                        replacements.append(
                            (rect, _pick_replacement_text(finding_type, term), source_font_size)
                        )
                        scheduled_rects.append(rect)
                        has_redaction = True
                        finding_matched = True

                if finding_matched:
                    continue

                for token in _build_token_terms(value):
                    for rect in _search_rects(page, token):
                        if _significantly_overlaps(rect, scheduled_rects):
                            continue
                        source_font_size = _pick_source_font_size(page, rect)
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                        replacements.append(
                            (rect, _pick_replacement_text(finding_type, token), source_font_size)
                        )
                        scheduled_rects.append(rect)
                        has_redaction = True

            if has_redaction:
                page.apply_redactions()
                for rect, replacement_text, source_font_size in replacements:
                    visible_text = replacement_text
                    if not visible_text.strip():
                        continue
                    _insert_replacement_text(page, rect, visible_text, source_font_size)

        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()
