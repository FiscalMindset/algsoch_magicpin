from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.services import bot_state

router = APIRouter()


class ContextRequest(BaseModel):
    scope: str  # "category", "merchant", "customer", "trigger"
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: datetime


class ContextResponse(BaseModel):
    accepted: bool
    ack_id: Optional[str] = None
    stored_at: Optional[datetime] = None
    reason: Optional[str] = None
    current_version: Optional[int] = None
    details: Optional[str] = None


@router.post("/v1/context", response_model=ContextResponse)
async def push_context(request: ContextRequest):
    """
    Receive context push from judge.
    Endpoints: category, merchant, customer, trigger.
    Idempotent by (context_id, version).
    """
    # Validate scope
    valid_scopes = ["category", "merchant", "customer", "trigger"]
    if request.scope not in valid_scopes:
        raise HTTPException(
            status_code=400,
            detail={
                "accepted": False,
                "reason": "invalid_scope",
                "details": f"Scope must be one of {valid_scopes}",
            },
        )

    # Store context
    if not bot_state.context_store:
        raise HTTPException(status_code=500, detail="Context store not initialized")

    stored = bot_state.context_store.store_context(
        request.scope, request.context_id, request.version, request.payload
    )

    if not stored:
        # Stale version
        current_version = bot_state.context_store.get_version(
            request.scope, request.context_id
        )
        return ContextResponse(
            accepted=False,
            reason="stale_version",
            current_version=current_version,
        )

    return ContextResponse(
        accepted=True,
        ack_id=f"ack_{request.context_id}_{request.version}",
        stored_at=datetime.utcnow(),
    )
