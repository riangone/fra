"""FastAPI Application Factory."""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.graph.nodes.hybrid_search import get_shared_retriever


STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize retriever and index documents
    get_shared_retriever()
    yield


app = FastAPI(
    title="Financial RAG & Attribution Agent API",
    description="Production-grade Financial Intelligence Engine powered by LangGraph, MCP, Hybrid Retrieval, and Sentence-Level Citation Auditing.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

DOCS_DIR = Path(__file__).parents[2] / "docs"
if DOCS_DIR.exists():
    app.mount("/docs-ja", StaticFiles(directory=str(DOCS_DIR), html=True), name="docs-ja")


@app.api_route("/", methods=["GET", "HEAD"])
async def root(request: Request):
    accept = request.headers.get("accept", "")
    index_file = STATIC_DIR / "index.html"
    if index_file.exists() and ("text/html" in accept or "application/json" not in accept):
        return FileResponse(str(index_file))

    return {
        "message": "Financial RAG Agent API is running.",
        "docs_url": "/docs",
        "showcase_ui": "/",
        "endpoints": ["/api/v1/health", "/api/v1/chat/sync", "/api/v1/chat/stream"],
    }
