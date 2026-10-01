"""FastAPI application for the System 1 playground."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from playground.catalog import build_catalog, model_ids
from playground.questions import RunInput, prepare_run
from playground.runners import laya_memory_status, run_models, warm_laya
from playground.scoring import build_report

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
load_dotenv(ROOT / ".env")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(warm_laya)
    yield


app = FastAPI(title="System 1 Playground", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def disable_static_cache(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/catalog")
def catalog() -> dict:
    return build_catalog()


@app.get("/api/health")
def health() -> dict:
    ready, status = laya_memory_status()
    return {"status": "ok", "laya": {"ready": ready, "status": status}}


@app.post("/api/run")
async def run(payload: RunInput) -> dict:
    try:
        prepared = prepare_run(payload, model_ids())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    results = await run_models(prepared.model_ids, prepared.state, prepared.questions)
    return build_report(prepared, results)
