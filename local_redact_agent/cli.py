"""CLI helpers for running the API service."""

from __future__ import annotations

import argparse

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="redactora",
        description="Run Redactora API server.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable hot-reload for development.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    uvicorn.run(
        "local_redact_agent.fastapi:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
