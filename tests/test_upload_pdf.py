from io import BytesIO
import base64

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter


def create_pdf_bytes() -> bytes:
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(stream)
    return stream.getvalue()


def test_upload_pdf_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    file_bytes = create_pdf_bytes()

    monkeypatch.setattr("app.api.routes.documents.process_pdf", lambda file_bytes, filename: {
        "filename": filename,
        "page_count": 1,
        "pages": [{"page_number": 1, "markdown": "# Sample"}],
    })
    async def fake_extract_confidential_data(pages):
        return [
            {
                "page_number": 1,
                "findings": [
                    {
                        "type": "email",
                        "value": "person@example.com",
                        "reason": "Personal email address",
                        "confidence": 0.95,
                    }
                ],
            }
        ]

    monkeypatch.setattr(
        "app.api.routes.documents.extract_confidential_data",
        fake_extract_confidential_data,
    )
    monkeypatch.setattr(
        "app.api.routes.documents.redact_pdf_by_findings",
        lambda file_bytes, confidential_findings: file_bytes,
    )

    response = client.post(
        "/upload-pdf",
        files={"file": ("sample.pdf", file_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"].endswith(".pdf")
    assert payload["page_count"] == 1
    assert payload["pages"][0]["page_number"] == 1
    assert payload["confidential_findings"][0]["findings"][0]["type"] == "email"
    assert payload["redacted_filename"] == f"redacted_{payload['filename']}"
    assert base64.b64decode(payload["redacted_pdf_base64"]) == file_bytes


def test_upload_pdf_rejects_non_pdf(client: TestClient) -> None:
    response = client.post(
        "/upload-pdf",
        files={"file": ("sample.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are supported."


def test_upload_pdf_rejects_empty_payload(client: TestClient) -> None:
    response = client.post(
        "/upload-pdf",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded PDF is empty."


def test_upload_pdf_rejects_large_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.documents.MAX_UPLOAD_SIZE_BYTES", 10)
    response = client.post(
        "/upload-pdf",
        files={"file": ("big.pdf", b"01234567890", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded PDF is too large."
