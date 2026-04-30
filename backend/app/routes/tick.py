from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.services import bot_state
import asyncio
import uuid

router = APIRouter()


class TickRequest(BaseModel):
    now: datetime
    available_triggers: List[str] = []


class Action(BaseModel):
    # Contract fields (challenge-testing-brief.md)
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: Optional[str] = None  # "vera" | "merchant_on_behalf"
    trigger_id: Optional[str] = None
    template_name: Optional[str] = None
    template_params: Optional[List[str]] = None
    body: Optional[str] = None
    cta: Optional[str] = None
    suppression_key: Optional[str] = None
    rationale: Optional[str] = None
    wait_seconds: Optional[int] = None


class TickResponse(BaseModel):
    actions: List[Action]


@router.post("/v1/tick", response_model=TickResponse)
async def tick(request: TickRequest):
    """
    Periodic wake-up endpoint.
    Bot inspects context and decides whether to send proactive messages.
    Timeout: 30 seconds.
    """
    try:
        if not bot_state.context_store or not bot_state.composition_service or not bot_state.conversation_manager:
            return TickResponse(actions=[])

        actions: List[Action] = []

        # Load triggers, filter expired/missing, then prioritize by urgency (desc).
        trigger_rows: List[Dict[str, Any]] = []
        for trigger_id in request.available_triggers:
            trigger_ctx = bot_state.context_store.get_context("trigger", trigger_id) or {}
            if not trigger_ctx:
                continue

            # Expiry guard
            try:
                exp = trigger_ctx.get("expires_at")
                if exp and isinstance(exp, str) and request.now:
                    exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                    if exp_dt <= request.now:
                        continue
            except Exception:
                pass

            suppression_key = trigger_ctx.get("suppression_key") or f"trg:{trigger_id}"
            if suppression_key in bot_state.sent_suppression_keys:
                continue

            merchant_id = trigger_ctx.get("merchant_id")
            if not merchant_id:
                continue

            trigger_rows.append({"id": trigger_id, "ctx": trigger_ctx, "suppression_key": suppression_key})

        trigger_rows.sort(key=lambda r: (-int(r["ctx"].get("urgency") or 1), str(r["ctx"].get("kind") or ""), r["id"]))

        # Avoid spam: send at most 3 actions per tick (still under 20 cap).
        for row in trigger_rows[:3]:
            trigger_id = row["id"]
            trigger_ctx = row["ctx"]
            suppression_key = row["suppression_key"]

            merchant_ctx = bot_state.context_store.get_context("merchant", merchant_id) or {}
            category_slug = merchant_ctx.get("category_slug")
            category_ctx = bot_state.context_store.get_context("category", category_slug) if category_slug else {}

            customer_ctx = None
            customer_id = trigger_ctx.get("customer_id")
            if customer_id:
                customer_ctx = bot_state.context_store.get_context("customer", customer_id)
                if trigger_ctx.get("scope") == "customer" and not customer_ctx:
                    # Can't safely message a customer without customer context.
                    continue

            composed = await bot_state.composition_service.compose(
                category=category_ctx or {},
                merchant=merchant_ctx,
                trigger=trigger_ctx,
                customer=customer_ctx,
                conversation_history=None,
                force_template=True,
            )
            if not composed.body:
                continue

            conversation_id = f"conv_{trigger_id}_{uuid.uuid4().hex[:8]}"
            bot_state.conversation_manager.create_conversation(
                conversation_id=conversation_id,
                merchant_id=merchant_id,
                customer_id=customer_id,
            )
            # Stash trigger id for reply continuity.
            bot_state.conversation_manager.conversation_metadata[conversation_id]["trigger_id"] = trigger_id

            bot_state.sent_suppression_keys.add(suppression_key)

            merchant_identity = (merchant_ctx or {}).get("identity", {}) if isinstance(merchant_ctx, dict) else {}
            merchant_display_name = (
                merchant_identity.get("owner_first_name")
                or merchant_identity.get("name")
                or merchant_identity.get("business_name")
                or merchant_id
            )
            kind = trigger_ctx.get("kind") or "update"
            template_name = f"vera_{kind}_v1"
            template_params = [str(merchant_display_name), composed.body]

            actions.append(
                Action(
                    conversation_id=conversation_id,
                    merchant_id=merchant_id,
                    customer_id=customer_id,
                    send_as="vera" if trigger_ctx.get("scope") == "merchant" else "merchant_on_behalf",
                    trigger_id=trigger_id,
                    template_name=template_name,
                    template_params=template_params,
                    body=composed.body,
                    cta=composed.cta,
                    suppression_key=suppression_key,
                    rationale=composed.rationale,
                )
            )

        return TickResponse(actions=actions)

    except asyncio.TimeoutError:
        # Return empty actions on timeout
        return TickResponse(actions=[])
    except Exception as e:
        print(f"Error in tick: {e}")
        return TickResponse(actions=[])
