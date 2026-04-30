from fastapi import APIRouter, HTTPException
from app.models import HealthzResponse, MetadataResponse
from app.services import bot_state
from datetime import datetime

router = APIRouter()


@router.get("/v1/healthz", response_model=HealthzResponse)
async def healthz():
    """
    Liveness probe endpoint.
    Returns health status and contexts loaded count.
    """
    bot_state.update_healthz()

    contexts_loaded = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    if bot_state.context_store:
        contexts_loaded = bot_state.context_store.get_contexts_count()

    return HealthzResponse(
        status="ok",
        uptime_seconds=bot_state.get_uptime_seconds(),
        contexts_loaded=contexts_loaded,
    )


@router.get("/v1/metadata", response_model=MetadataResponse)
async def metadata():
    """
    Bot identity and configuration endpoint.
    """
    model = "deterministic-template"
    approach = "Deterministic 4-context composition (template rules) for stable outputs"
    if getattr(bot_state, "composition_service", None):
        provider = getattr(bot_state.composition_service, "provider", None)
        if provider == "groq":
            model = getattr(bot_state.composition_service, "groq_model", model)
            approach = "4-context composition framework with Groq default routing"
        elif provider == "anthropic":
            model = "claude-opus-4-7"
            approach = "4-context composition framework with optional LLM assistance"

    return MetadataResponse(
        team_name="Vera AI Team",
        team_members=["AI Engineer"],
        model=model,
        approach=approach,
        contact_email="team@magicpin.ai",
        version="1.0.0",
        submitted_at=datetime.utcnow(),
        groq_default=bool(bot_state.groq_api_key),
        default_provider=(bot_state.composition_service.provider if bot_state.composition_service else None),
    )
