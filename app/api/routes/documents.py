from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import MAX_UPLOAD_SIZE_BYTES
from app.services.confidential_extractor import extract_confidential_data
from app.services.pdf_processor import process_pdf
from app.services.pdf_redactor import redact_pdf_by_findings

router = APIRouter()


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Uploaded PDF is too large.")

    try:
        result = process_pdf(file_bytes=file_bytes, filename=Path(file.filename).name)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=f"Unable to process PDF: {exc}") from exc

    try:
        result["confidential_findings"] = await extract_confidential_data(result["pages"])
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=502,
            detail=f"Unable to extract confidential data with Ollama: {exc}",
        ) from exc

    try:
        redacted_pdf = redact_pdf_by_findings(file_bytes, result["confidential_findings"])
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unable to redact PDF: {exc}") from exc

    result["redacted_filename"] = f"redacted_{result['filename']}"
    result["redacted_pdf_base64"] = base64.b64encode(redacted_pdf).decode("ascii")

    return result
