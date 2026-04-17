from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import MAX_UPLOAD_SIZE_BYTES, REDACTED_OUTPUT_DIR
from app.services.confidential_extractor import extract_confidential_data
from app.services.pdf_processor import process_pdf
from app.services.pdf_redactor import redact_pdf_by_findings

router = APIRouter()


async def _process_and_redact(file: UploadFile) -> tuple[dict[str, Any], bytes]:
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

    return result, redacted_pdf


def _resolve_output_path(filename: str) -> Path:
    REDACTED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REDACTED_OUTPUT_DIR / filename
    if not output_path.exists():
        return output_path

    stem = output_path.stem
    suffix = output_path.suffix
    counter = 1
    while True:
        candidate = REDACTED_OUTPUT_DIR / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)) -> dict[str, Any]:
    result, redacted_pdf = await _process_and_redact(file)
    redacted_filename = f"redacted_{result['filename']}"
    output_path = _resolve_output_path(redacted_filename)
    output_path.write_bytes(redacted_pdf)

    result["redacted_filename"] = output_path.name
    result["redacted_file_path"] = str(output_path.resolve())
    return result
