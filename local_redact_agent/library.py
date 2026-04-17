"""Reusable library entrypoints for PDF redaction workflows."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.services.confidential_extractor import extract_confidential_data
from app.services.pdf_processor import process_pdf
from app.services.pdf_redactor import redact_pdf_by_findings


async def redact_pdf_document(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """
    Run end-to-end extraction and redaction for a PDF.

    Returns API-like metadata plus `redacted_pdf_bytes`.
    """
    result = process_pdf(file_bytes=file_bytes, filename=Path(filename).name)
    result["confidential_findings"] = await extract_confidential_data(result["pages"])
    result["redacted_pdf_bytes"] = redact_pdf_by_findings(
        file_bytes, result["confidential_findings"]
    )
    return result


def redact_pdf_document_sync(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """Synchronous wrapper around `redact_pdf_document`."""
    return asyncio.run(redact_pdf_document(file_bytes=file_bytes, filename=filename))
