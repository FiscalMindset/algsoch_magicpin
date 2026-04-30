from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from app.routes import (
    health_router,
    context_router,
    tick_router,
    reply_router,
    dataset_router,
    playground_router,
    docs_router,
    merchant_sim_router,
    monitor_router,
)
from app.services import bot_state, ContextStore, ConversationManager, CompositionService
from app.middleware.request_logger_middleware import RequestLoggingMiddleware
import os
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(
    title="Vera AI Assistant",
    description="Merchant AI assistant for magicpin",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware (must be added AFTER CORS)
app.add_middleware(RequestLoggingMiddleware)


@app.on_event("startup")
async def startup_event():
    """Initialize bot state on startup."""
    bot_state.context_store = ContextStore()
    bot_state.conversation_manager = ConversationManager()

    # Prefer Groq by default when a Groq key is present, otherwise fall back to Anthropic.
    llm_client = None
    if os.environ.get("GROQ_API_KEY") or os.environ.get("VITE_GROQ_API_KEY"):
        llm_client = None
    elif os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic

            llm_client = Anthropic()
        except Exception as e:
            print(f"LLM client initialization failed (falling back to templates): {e}")

    bot_state.composition_service = CompositionService(llm_client)

    # Read GROQ API key from environment if provided and store in bot state
    groq_key = os.environ.get("GROQ_API_KEY") or os.environ.get("VITE_GROQ_API_KEY")
    if groq_key:
        bot_state.groq_api_key = groq_key
        print("GROQ API key loaded from environment (masked):", groq_key[:4] + "...")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    if bot_state.context_store:
        bot_state.context_store.clear()


# Include routers
app.include_router(health_router)
app.include_router(context_router)
app.include_router(tick_router)
app.include_router(reply_router)
app.include_router(dataset_router)
app.include_router(playground_router)
app.include_router(docs_router)
app.include_router(merchant_sim_router)
app.include_router(monitor_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Vera AI Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
    }
