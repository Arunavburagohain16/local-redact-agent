from __future__ import annotations

import re
from io import BytesIO
from functools import lru_cache
from pathlib import Path
from typing import Any

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

PAGE_SEPARATOR = "__PAGE_BREAK__"


@lru_cache(maxsize=1)
def get_converter() -> PdfConverter:
    return PdfConverter(
        artifact_dict=create_model_dict(),
        config={"paginate_output": True, "page_separator": PAGE_SEPARATOR},
    )


def split_markdown_by_page(markdown: str) -> list[dict[str, str | int]]:
    pattern = re.compile(rf"\{{(\d+)\}}{re.escape(PAGE_SEPARATOR)}")
    matches = list(pattern.finditer(markdown))
    if not matches:
        return [{"page_number": 1, "markdown": markdown.strip()}]

    pages: list[dict[str, str | int]] = []
    for index, match in enumerate(matches):
        page_number = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        page_markdown = markdown[start:end].strip()
        pages.append({"page_number": page_number, "markdown": page_markdown})

    return pages


def process_pdf(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """Convert PDF bytes to page-wise markdown using Marker."""
    rendered = get_converter()(BytesIO(file_bytes))
    markdown_text, _, _ = text_from_rendered(rendered)
    pages = split_markdown_by_page(markdown_text)

    return {
        "filename": Path(filename).name,
        "page_count": len(pages),
        "pages": pages,
    }
