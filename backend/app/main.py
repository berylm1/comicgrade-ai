"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import comics, vision

app = FastAPI(
    title="ComicGrade AI",
    description="Comic book valuation & grading prototype API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype-wide; tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vision.router)
app.include_router(comics.router)


@app.get("/")
async def root() -> dict:
    return {"app": "ComicGrade AI", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}