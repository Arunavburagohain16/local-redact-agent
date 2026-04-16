from io import BytesIO

from pypdf import PdfReader, PdfWriter

from app.services.pdf_redactor import redact_pdf_by_findings


def create_pdf_bytes() -> bytes:
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(stream)
    return stream.getvalue()


def test_redact_pdf_by_findings_returns_valid_pdf() -> None:
    file_bytes = create_pdf_bytes()
    findings = [{"page_number": 0, "findings": [{"value": "person@example.com"}]}]

    redacted = redact_pdf_by_findings(file_bytes, findings)

    reader = PdfReader(BytesIO(redacted))
    assert len(reader.pages) == 1
