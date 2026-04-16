from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS

MAX_PAGE_MARKDOWN_CHARS = 12000


def build_extraction_prompt(page_markdown: str, page_number: int) -> str:
    return f"""
You are a document privacy reviewer.
Extract POI/PII/confidential data from the markdown for page {page_number}.

Return strict JSON in this exact structure:
{{
  "findings": [
    {{
      "type": "email|phone|address|id_number|bank_details|medical|legal|secret|other",
      "value": "exact extracted value",
      "reason": "why this is confidential",
      "confidence": 0.0
    }}
  ]
}}

Rules:
- If no confidential data is found, return {{"findings":[]}}.
- confidence must be a number from 0.0 to 1.0.
- Return JSON only, no markdown.

Markdown content:
{page_markdown[:MAX_PAGE_MARKDOWN_CHARS]}
""".strip()


def parse_ollama_findings(raw_response: str) -> list[dict[str, Any]]:
    parsed = json.loads(raw_response)
    findings = parsed.get("findings", [])
    if not isinstance(findings, list):
        return []

    normalized: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        normalized.append(
            {
                "type": str(finding.get("type", "other")),
                "value": str(finding.get("value", "")).strip(),
                "reason": str(finding.get("reason", "")).strip(),
                "confidence": float(finding.get("confidence", 0.0)),
            }
        )
    return normalized


async def analyze_page_markdown(
    client: httpx.AsyncClient, page_number: int, markdown: str
) -> dict[str, Any]:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": build_extraction_prompt(markdown, page_number),
        "stream": False,
        "format": "json",
    }
    response = await client.post("/api/generate", json=payload)
    response.raise_for_status()
    raw = response.json().get("response", "{}")
    findings = parse_ollama_findings(raw)
    return {"page_number": page_number, "findings": findings}


async def extract_confidential_data(
    pages: list[dict[str, str | int]],
) -> list[dict[str, Any]]:
    page_findings: list[dict[str, Any]] = []

    timeout = httpx.Timeout(OLLAMA_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=timeout) as client:
        for page in pages:
            page_number = int(page["page_number"])
            markdown = str(page["markdown"])
            page_result = await analyze_page_markdown(client, page_number, markdown)
            page_findings.append(page_result)

    return page_findings
