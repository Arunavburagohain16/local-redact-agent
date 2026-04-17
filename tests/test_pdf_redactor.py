from io import BytesIO

import fitz
from pypdf import PdfReader, PdfWriter

from app.services.pdf_redactor import _randomize_text, redact_pdf_by_findings


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


def test_randomize_text_preserves_shape() -> None:
    source = "AAFCG9846E person@example.com"

    randomized = _randomize_text(source)

    assert len(randomized) == len(source)
    assert randomized != source
    assert randomized[5:9].isdigit()
    assert randomized[10] == " "
    assert randomized[-4] == "."
