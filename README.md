# local-redact-agent

FastAPI service for uploading and processing PDF files in memory at runtime.

## Python version

This project targets Python `3.13`.

## Setup with uv

1. Install dependencies:

```bash
uv sync
```

2. Start the API server:

```bash
uv run uvicorn app.main:app --reload
```

The service starts at `http://127.0.0.1:8000`.

## Ollama setup

This API calls local Ollama after markdown conversion.

1. Start Ollama and pull model:

```bash
ollama pull gemma4
ollama serve
```

2. Optional environment variables:

- `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
- `OLLAMA_MODEL` (default: `gemma4`)
- `OLLAMA_TIMEOUT_SECONDS` (default: `120`)

## API endpoints

- `GET /health` - basic health check.
- `POST /upload-pdf` - upload a PDF file and get a processing summary.
  - Files are processed in-memory and are not stored on disk.
  - Current max upload size is 20 MB.
  - Each page markdown is analyzed by Ollama to extract POI/PII/confidential data.
  - The API redacts extracted values in the original PDF and returns it as base64.

## Project structure

```text
app/
  api/
    routes/
  core/
  services/
tests/
```

## Test upload

```bash
curl -X POST "http://127.0.0.1:8000/upload-pdf" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/absolute/path/to/file.pdf"
```

Example response:

```json
{
  "filename": "example.pdf",
  "page_count": 2,
  "pages": [
    {
      "page_number": 1,
      "markdown": "# Page 1 markdown..."
    },
    {
      "page_number": 2,
      "markdown": "# Page 2 markdown..."
    }
  ],
  "confidential_findings": [
    {
      "page_number": 1,
      "findings": [
        {
          "type": "email",
          "value": "person@example.com",
          "reason": "Personal email address",
          "confidence": 0.95
        }
      ]
    }
  ],
  "redacted_filename": "redacted_example.pdf",
  "redacted_pdf_base64": "<base64-pdf-bytes>"
}
```

To save the redacted PDF from response:

```python
import base64
from pathlib import Path

payload = response.json()
Path(payload["redacted_filename"]).write_bytes(
    base64.b64decode(payload["redacted_pdf_base64"])
)
```

## Run tests

```bash
uv run pytest
```
