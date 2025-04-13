from fastapi import FastAPI
from app.api.route import router as api_router
from app.db.database import engine, Base
import uvicorn
from app.models import models
from app.core.config import config

app = FastAPI(
    title=config.api_title,
    version=config.api_version,
    description="A robust, event-driven exchange rate API built with FastAPI and SQLAlchemy."
)


app.include_router(api_router, prefix="/api")

Base.metadata.create_all(bind=engine)

@app.get("/", tags=["Health Check"])
async def health_check():
    return {
        "name": "Koel Exchange Rate API",
        "description": "Koel is an exchange rate api service. It primarily provides exchange rate data for various currencies.",
        "version": "0.1.0",
        "status": "running"
    }