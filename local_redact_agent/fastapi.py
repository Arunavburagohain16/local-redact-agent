"""FastAPI exports for running the HTTP service."""

from app.main import app as app


def create_app():
    """Return the configured FastAPI app instance."""
    return app
