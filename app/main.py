from fastapi import FastAPI

app = FastAPI(title="Redactora API", version="0.1.0")
from app.api.router import api_router

app.include_router(api_router)
