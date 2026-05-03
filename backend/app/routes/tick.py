from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.services import bot_state
import asyncio

router = APIRouter()


class TickRequest(BaseModel):
    now: datetime
    available_triggers: List[str] = []


class Action(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: Optional[str] = None
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


def _deterministic_conversation_id(merchant_id: str, trigger_id: str, customer_id: Optional[str] = None) -> str:
    parts = ["conv", merchant_id, trigger_id]
    if customer_id:
        parts.append(customer_id)
    return ":".join(parts)


def _compute_priority(trigger_ctx: Dict[str, Any]) -> float:
    urgency = int(trigger_ctx.get("urgency") or 1)
    version = 1
    if trigger_ctx.get("id"):
        version = bot_state.context_store.get_version("trigger", trigger_ctx["id"]) if bot_state.context_store else 1
    return urgency * 10 + version


def _trigger_payload(trigger_ctx: Dict[str, Any]) -> Dict[str, Any]:
    payload = trigger_ctx.get("payload", {})
    return payload if isinstance(payload, dict) else {}


def _linked_id(trigger_ctx: Dict[str, Any], key: str) -> Optional[str]:
    payload = _trigger_payload(trigger_ctx)
    value = trigger_ctx.get(key) or payload.get(key)
    if value:
        return str(value)
    if key == "merchant_id":
        for alt in ("merchant", "business_id"):
            if payload.get(alt):
                return str(payload[alt])
    if key == "customer_id":
        for alt in ("customer", "user_id"):
            if payload.get(alt):
                return str(payload[alt])
    return None


@router.post("/v1/tick", response_model=TickResponse)
async def tick(request: TickRequest):
    try:
        if not bot_state.context_store or not bot_state.composition_service or not bot_state.conversation_manager:
            return TickResponse(actions=[])

        actions: List[Action] = []
        trigger_rows: List[Dict[str, Any]] = []

        for trigger_id in request.available_triggers:
            trigger_ctx = bot_state.context_store.get_context("trigger", trigger_id)
            if not trigger_ctx:
                continue

            try:
                exp = trigger_ctx.get("expires_at")
                if exp and isinstance(exp, str):
                    exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                    if exp_dt <= request.now:
                        continue
            except Exception:
                pass

            suppression_key = trigger_ctx.get("suppression_key") or f"trg:{trigger_id}"
            if suppression_key in bot_state.sent_suppression_keys:
                continue

            merchant_id = _linked_id(trigger_ctx, "merchant_id")
            if not merchant_id:
                continue

            merchant_ctx = bot_state.context_store.get_context("merchant", merchant_id)
            if not merchant_ctx:
                continue

            category_slug = merchant_ctx.get("category_slug")
            category_ctx = bot_state.context_store.get_context("category", category_slug) if category_slug else {}

            customer_ctx = None
            customer_id = _linked_id(trigger_ctx, "customer_id")
            if customer_id:
                customer_ctx = bot_state.context_store.get_context("customer", customer_id)
                if trigger_ctx.get("scope") == "customer" and not customer_ctx:
                    continue

            trigger_rows.append({
                "id": trigger_id,
                "ctx": trigger_ctx,
                "merchant_id": merchant_id,
                "merchant_ctx": merchant_ctx,
                "category_ctx": category_ctx or {},
                "customer_ctx": customer_ctx,
                "customer_id": customer_id,
                "suppression_key": suppression_key,
                "priority": _compute_priority(trigger_ctx),
            })

        trigger_rows.sort(key=lambda r: -r["priority"])

        for row in trigger_rows[:15]:  # Allow up to 15 actions per tick (within 20 action cap)
            trigger_id = row["id"]
            trigger_ctx = row["ctx"]
            merchant_id = row["merchant_id"]
            merchant_ctx = row["merchant_ctx"]
            category_ctx = row["category_ctx"]
            customer_ctx = row["customer_ctx"]
            customer_id = row["customer_id"]
            suppression_key = row["suppression_key"]

            composed = await bot_state.composition_service.compose(
                category=category_ctx,
                merchant=merchant_ctx,
                trigger=trigger_ctx,
                customer=customer_ctx,
                conversation_history=None,
                force_template=False,
            )
            if not composed.body:
                continue

            conversation_id = _deterministic_conversation_id(merchant_id, trigger_id, customer_id)

            if conversation_id not in bot_state.conversation_manager.conversation_metadata:
                bot_state.conversation_manager.create_conversation(
                    conversation_id=conversation_id,
                    merchant_id=merchant_id,
                    customer_id=customer_id,
                )
                bot_state.conversation_manager.conversation_metadata[conversation_id]["trigger_id"] = trigger_id

            bot_state.sent_suppression_keys.add(suppression_key)

            merchant_identity = merchant_ctx.get("identity", {}) if isinstance(merchant_ctx, dict) else {}
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
        return TickResponse(actions=[])
    except Exception as e:
        print(f"Error in tick: {e}")
        return TickResponse(actions=[])
