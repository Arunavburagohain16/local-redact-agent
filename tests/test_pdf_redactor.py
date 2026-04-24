from io import BytesIO

import fitz
from pypdf import PdfReader, PdfWriter

from app.services.pdf_redactor import _pick_replacement_text, redact_pdf_by_findings


def create_pdf_bytes() -> bytes:
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(stream)
    return stream.getvalue()


def create_text_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=400, height=200)
    page.insert_text(
        (20, 40),
        "Contact: person@example.com Invoice: D413152DN2503838",
        fontname="helv",
        fontsize=12,
    )
    data = document.tobytes()
    document.close()
    return data


def create_sensitive_only_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=260, height=120)
    page.insert_text(
        (20, 50),
        "person@example.com",
        fontname="helv",
        fontsize=12,
    )
    data = document.tobytes()
    document.close()
    return data


def test_redact_pdf_by_findings_returns_valid_pdf() -> None:
    file_bytes = create_pdf_bytes()
    findings = [{"page_number": 0, "findings": [{"value": "person@example.com"}]}]

    redacted = redact_pdf_by_findings(file_bytes, findings)

    reader = PdfReader(BytesIO(redacted))
    assert len(reader.pages) == 1


def test_redact_pdf_replaces_found_text() -> None:
    file_bytes = create_text_pdf_bytes()
    findings = [
        {
            "page_number": 0,
            "findings": [
                {"value": "person@example.com"},
                {"value": "D413152DN2503838"},
            ],
        }
    ]

    redacted = redact_pdf_by_findings(file_bytes, findings)

    document = fitz.open(stream=BytesIO(redacted), filetype="pdf")
    page_text = document[0].get_text()
    document.close()

    assert "person@example.com" not in page_text
    assert "D413152DN2503838" not in page_text


def test_redact_pdf_falls_back_to_token_matching() -> None:
    file_bytes = create_text_pdf_bytes()
    findings = [
        {
            "page_number": 0,
            "findings": [
                {
                    "value": "Primary contact is PERSON@EXAMPLE.COM and ref is D413152DN2503838"
                }
            ],
        }
    ]

    redacted = redact_pdf_by_findings(file_bytes, findings)

    document = fitz.open(stream=BytesIO(redacted), filetype="pdf")
    page_text = document[0].get_text()
    document.close()

    assert "person@example.com" not in page_text.lower()
    assert "d413152dn2503838" not in page_text.lower()


def test_redact_pdf_inserts_visible_replacement_text() -> None:
    file_bytes = create_sensitive_only_pdf_bytes()
    findings = [{"page_number": 0, "findings": [{"value": "person@example.com"}]}]

    redacted = redact_pdf_by_findings(file_bytes, findings)

    document = fitz.open(stream=BytesIO(redacted), filetype="pdf")
    page_text = document[0].get_text().strip()
    document.close()

    assert page_text
    assert "person@example.com" not in page_text.lower()


def test_redact_pdf_preserves_original_font_size_when_possible() -> None:
    file_bytes = create_sensitive_only_pdf_bytes()
    findings = [{"page_number": 0, "findings": [{"value": "person@example.com"}]}]

    redacted = redact_pdf_by_findings(file_bytes, findings)

    document = fitz.open(stream=BytesIO(redacted), filetype="pdf")
    text_dict = document[0].get_text("dict")
    document.close()

    span_sizes: list[float] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size")
                if isinstance(size, (int, float)):
                    span_sizes.append(float(size))

    assert span_sizes
    assert max(span_sizes) >= 11.0


def test_pick_replacement_text_uses_type_specific_placeholders() -> None:
    email_replacement = _pick_replacement_text("email", "person@example.com")
    phone_replacement = _pick_replacement_text("phone", "9876543210")
    id_replacement = _pick_replacement_text("id_number", "D413152DN2503838")
    fallback_replacement = _pick_replacement_text("unknown_type", "something")
    second_email_replacement = _pick_replacement_text("email", "person@example.com")

    assert email_replacement == "dummy.user@example.test"
    assert second_email_replacement == email_replacement
    assert phone_replacement == "9000000000"
    assert id_replacement == "DUMMY-ID-0001"
    assert fallback_replacement == "Dummy confidential value"
