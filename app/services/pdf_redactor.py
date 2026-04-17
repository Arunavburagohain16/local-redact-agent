from __future__ import annotations

import re
import secrets
import string
from io import BytesIO
from typing import Any

import fitz

MIN_FRAGMENT_LENGTH = 8
MIN_TOKEN_LENGTH = 4
REDACTION_FONT_SIZE = 8
MIN_REDACTION_FONT_SIZE = 3.0
LETTER_POOL = string.ascii_letters
DIGIT_POOL = string.digits


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


def _randomize_text(value: str) -> str:
    randomized: list[str] = []
    for char in value:
        if char.isspace():
            randomized.append(char)
        elif char.isalpha():
            randomized.append(secrets.choice(LETTER_POOL))
        elif char.isdigit():
            randomized.append(secrets.choice(DIGIT_POOL))
        else:
            randomized.append(char)
    return "".join(randomized)


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
    return rects


def _pick_font_size(rect: fitz.Rect, text: str) -> float:
    single_line = re.sub(r"\s+", " ", text).strip()
    if not single_line:
        return MIN_REDACTION_FONT_SIZE

    max_size = min(REDACTION_FONT_SIZE, max(MIN_REDACTION_FONT_SIZE, rect.height * 0.8))
    size = max_size
    while size >= MIN_REDACTION_FONT_SIZE:
        text_width = fitz.get_text_length(single_line, fontname="helv", fontsize=size)
        if text_width <= rect.width * 0.98:
            return size
        size -= 0.5
    return MIN_REDACTION_FONT_SIZE


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
            replacements: list[tuple[fitz.Rect, str]] = []
            for finding in findings:
                if not isinstance(finding, dict):
                    continue

                value = str(finding.get("value", "")).strip()
                if not value:
                    continue

                finding_matched = False
                for term in _build_search_terms(value):
                    for rect in _search_rects(page, term):
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                        replacements.append((rect, _randomize_text(term)))
                        has_redaction = True
                        finding_matched = True

                if finding_matched:
                    continue

                for token in _build_token_terms(value):
                    for rect in _search_rects(page, token):
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                        replacements.append((rect, _randomize_text(token)))
                        has_redaction = True

            if has_redaction:
                page.apply_redactions()
                for rect, replacement_text in replacements:
                    visible_text = re.sub(r"\s+", " ", replacement_text).strip()
                    if not visible_text:
                        continue
                    page.insert_textbox(
                        rect,
                        visible_text,
                        fontname="helv",
                        fontsize=_pick_font_size(rect, visible_text),
                        color=(0, 0, 0),
                        align=fitz.TEXT_ALIGN_LEFT,
                    )

        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()
