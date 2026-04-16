import json

from app.services.confidential_extractor import parse_ollama_findings


def test_parse_ollama_findings_normalizes_payload() -> None:
    raw = json.dumps(
        {
            "findings": [
                {
                    "type": "phone",
                    "value": "555-123-9999",
                    "reason": "Phone number",
                    "confidence": 0.9,
                }
            ]
        }
    )

    findings = parse_ollama_findings(raw)

    assert len(findings) == 1
    assert findings[0]["type"] == "phone"
    assert findings[0]["value"] == "555-123-9999"


def test_parse_ollama_findings_handles_bad_shape() -> None:
    raw = json.dumps({"findings": "invalid"})
    assert parse_ollama_findings(raw) == []
