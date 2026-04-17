# local-redact-agent

Local-first FastAPI service for detecting and redacting sensitive information in PDF files.

`local-redact-agent` runs a complete PDF redaction flow on your machine: upload a PDF, extract page content, use a local Ollama model to detect confidential values, and save a redacted PDF locally.

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Quickstart](#quickstart)
- [Install as a Package](#install-as-a-package)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Usage Examples](#usage-examples)
- [Project Structure](#project-structure)
- [Development](#development)
- [Release Checklist](#release-checklist)
- [Contributing](#contributing)
- [License](#license)

## Features

- Local-first processing with no required external cloud API.
- In-memory PDF processing (uploaded files are not persisted by this service).
- AI-assisted confidential data extraction using local Ollama models.
- Automatic redaction of matched values in the original PDF using randomized replacement text.
- Redacted PDFs are automatically saved to a local output directory.

## How It Works

1. Client uploads a PDF to `POST /upload-pdf`.
2. Service validates file type, filename, and size.
3. PDF pages are converted to markdown/text.
4. Page content is sent to Ollama for confidential-data extraction.
5. Detected values are located and replaced with randomized surrogate text in the source PDF.
6. API returns:
   - Original metadata and page data
   - Structured confidential findings
   - `redacted_filename` and `redacted_file_path`

## Requirements

- Python `3.12+`
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
uv run local-redact-agent --reload
```

4. Open API docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Install as a Package

Install from local source:

```bash
pip install .
```

Install editable for development:

```bash
pip install -e ".[dev]"
```

Run API after install:

```bash
local-redact-agent --host 127.0.0.1 --port 8000
```

## Configuration

Environment variables (all optional):

- `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
- `OLLAMA_MODEL` (default: `gemma4`)
- `OLLAMA_TIMEOUT_SECONDS` (default: `120`)
- `REDACTED_OUTPUT_DIR` (default: `redacted_output`)

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

## Usage Examples

### API request

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
  "redacted_file_path": "/absolute/path/to/redacted_output/redacted_example.pdf"
}
```

### Python library import

```python
from pathlib import Path

from local_redact_agent import redact_pdf_document_sync

pdf_bytes = Path("example.pdf").read_bytes()
result = redact_pdf_document_sync(file_bytes=pdf_bytes, filename="example.pdf")

Path("redacted_example.pdf").write_bytes(result["redacted_pdf_bytes"])
print(result["confidential_findings"])
```

## Project Structure

```text
app/
  api/
    routes/
  core/
  services/
local_redact_agent/
tests/
```

## Development

Run tests:

```bash
uv run pytest
```

## Release Checklist

1. Bump version in `pyproject.toml`.
2. Ensure tests pass locally:

```bash
uv run pytest
```

3. Build and validate distributions:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

4. Create and publish a GitHub release.
5. Confirm the GitHub Actions workflow `.github/workflows/publish.yml` succeeds.

Notes:
- Configure [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) for this repository before first release.
- Replace placeholder URLs in `pyproject.toml` under `[project.urls]`.

## Contributing

Contributions are welcome. Please open an issue to discuss substantial changes before submitting a pull request.

## License

This project is licensed under the MIT License. See `LICENSE`.
