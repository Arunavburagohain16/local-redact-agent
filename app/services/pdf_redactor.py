from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import fitz

MIN_FRAGMENT_LENGTH = 8


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
            for finding in findings:
                if not isinstance(finding, dict):
                    continue

                value = str(finding.get("value", "")).strip()
                if not value:
                    continue

                for term in _build_search_terms(value):
                    for rect in page.search_for(
                        term,
                        flags=fitz.TEXT_DEHYPHENATE | fitz.TEXT_PRESERVE_WHITESPACE,
                    ):
                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        has_redaction = True

            if has_redaction:
                page.apply_redactions()

        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()
