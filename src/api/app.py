"""FastAPI Application Factory."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.graph.nodes.hybrid_search import get_shared_retriever


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


@app.get("/")
async def root():
    return {
        "message": "Financial RAG Agent API is running.",
        "docs_url": "/docs",
        "endpoints": ["/api/v1/health", "/api/v1/chat/sync", "/api/v1/chat/stream"],
    }
