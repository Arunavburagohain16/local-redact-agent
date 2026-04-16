from fastapi import FastAPI

app = FastAPI(title="Local Redact Agent API", version="0.1.0")
from app.api.router import api_router

app.include_router(api_router)
