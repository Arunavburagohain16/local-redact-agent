# local-redact-agent

Local-first FastAPI service for detecting and redacting sensitive information in PDF files.

`local-redact-agent` runs a complete PDF redaction flow on your machine: upload a PDF, extract page content, use a local Ollama model to detect confidential values, and return a redacted PDF in the response.

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Usage Example](#usage-example)
- [Project Structure](#project-structure)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Features

- Local-first processing with no required external cloud API.
- In-memory PDF processing (uploaded files are not persisted by this service).
- AI-assisted confidential data extraction using local Ollama models.
- Automatic redaction of matched values in the original PDF.
- JSON response includes findings and base64-encoded redacted PDF output.

## How It Works

1. Client uploads a PDF to `POST /upload-pdf`.
2. Service validates file type, filename, and size.
3. PDF pages are converted to markdown/text.
4. Page content is sent to Ollama for confidential-data extraction.
5. Detected values are located and redacted in the source PDF.
6. API returns:
   - Original metadata and page data
   - Structured confidential findings
   - `redacted_pdf_base64` and `redacted_filename`

## Requirements

- Python `3.13`
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) running locally

## Quickstart

1. Install dependencies:

```bash
uv sync
```

2. Pull and run the default Ollama model:

```bash
ollama pull gemma4
ollama serve
```

3. Start the API:

```bash
uv run uvicorn app.main:app --reload
```

4. Open API docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Configuration

Environment variables (all optional):

- `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
- `OLLAMA_MODEL` (default: `gemma4`)
- `OLLAMA_TIMEOUT_SECONDS` (default: `120`)

Service constants:

- Maximum upload size: `20 MB`

## API Reference

### `GET /health`

Health check endpoint.

Example response:

```json
{
  "status": "ok"
}
```

### `POST /upload-pdf`

Upload a PDF and receive extraction + redaction results.

Behavior:

- Accepts `multipart/form-data` with one `file` field.
- Only `application/pdf` is supported.
- Returns `400` for invalid file type, empty file, missing filename, or oversized upload.
- Returns `502` if confidential extraction fails.
- Returns `500` if PDF redaction fails.

## Usage Example

Request:

```bash
curl -X POST "http://127.0.0.1:8000/upload-pdf" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/absolute/path/to/file.pdf"
```

Response shape:

```json
{
  "filename": "example.pdf",
  "page_count": 2,
  "pages": [
    {
      "page_number": 1,
      "markdown": "# Page 1 markdown..."
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

Save the redacted PDF locally:

```python
import base64
from pathlib import Path

payload = response.json()
Path(payload["redacted_filename"]).write_bytes(
    base64.b64decode(payload["redacted_pdf_base64"])
)
```

## Project Structure

```text
app/
  api/
    routes/
  core/
  services/
tests/
```

## Development

Run tests:

```bash
uv run pytest
```

## Contributing

Contributions are welcome. Please open an issue to discuss substantial changes before submitting a pull request.

## License

No license file is currently included in this repository.
