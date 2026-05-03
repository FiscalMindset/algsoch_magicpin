from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
from app.services import bot_state
import asyncio
import json

router = APIRouter()


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: datetime
    turn_number: int


class ReplyAction(BaseModel):
    action: str
    body: Optional[str] = None
    cta: Optional[str] = None
    rationale: str
    wait_seconds: Optional[int] = None


_last_response_bodies: Dict[str, str] = {}
_last_messages: Dict[str, str] = {}


def _is_hindi(text: str) -> bool:
    return any('\u0900' <= c <= '\u097F' for c in text)


def _is_hinglish(text: str) -> bool:
    hi_markers = ["kya", "kaise", "kaisa", "kahan", "kab", "kyun", "mera", "mere", "meri",
                  "tum", "aap", "hamara", "hamare", "hai", "hain", "tha", "the", "thi",
                  "karna", "karo", "karein", "dekho", "dekha", "dekhi", "batayein",
                  "batao", "chahiye", "mujhe", "humein", "apne", "apna", "apni",
                  "profile ke", "apni", "baare", "mein", "jaanna"]
    text_lower = text.lower()
    return any(word in text_lower for word in hi_markers)


def _check_repetition(conv_id: str, body: str) -> bool:
    prev = _last_response_bodies.get(conv_id, "")
    return prev.strip() == body.strip()


def _record_response(conv_id: str, body: str):
    _last_response_bodies[conv_id] = body


def _handle_repetition(conv_id: str, body: str):
    if _check_repetition(conv_id, body):
        _record_response(conv_id, body)
        return ReplyAction(
            action="end",
            body="I notice I may have mentioned this before. Let me know when you're ready to take the next step!",
            cta="none",
            rationale="Detected exact repetition of previous response; ending conversation to avoid spam."
        )
    return None


def _get_merchant_name(m):
    identity = m.get("identity", {}) if isinstance(m, dict) else {}
    return identity.get("owner_first_name") or identity.get("name", "there")


def _get_active_offers(m):
    offers = m.get("offers", []) if isinstance(m, dict) else []
    return [o.get("title") for o in offers if isinstance(o, dict) and o.get("status") == "active"]


def _get_perf_summary(m):
    perf = m.get("performance", {}) if isinstance(m, dict) else {}
    parts = []
    if perf.get("views"): parts.append(f"{perf['views']} views")
    if perf.get("calls"): parts.append(f"{perf['calls']} calls")
    if perf.get("directions"): parts.append(f"{perf['directions']} directions")
    if perf.get("ctr"): parts.append(f"CTR {perf['ctr']*100:.1f}%")
    delta = perf.get("delta_7d", {})
    if delta.get("views_pct"):
        sign = "+" if delta["views_pct"] > 0 else ""
        parts.append(f"views {sign}{delta['views_pct']*100:.0f}% (7d)")
    return ", ".join(parts) if parts else "No performance data yet"


def _find_best_trigger_for_merchant(merchant_id):
    if not bot_state.context_store:
        return {}
    for (scope, cid), ctx in bot_state.context_store.contexts.items():
        if scope == "trigger" and ctx.get("merchant_id") == merchant_id:
            return ctx
    return {}


def _hindi_offers(name, active_offers, category_context):
    if active_offers:
        offers_str = "\n".join(f"\u2022 {o}" for o in active_offers)
        return (
            f"{name}, \u0906\u092a\u0915\u0947 active offers \u092f\u0947 \u0939\u0948\u0902:\n{offers_str}\n\n"
            f"\u0915\u094d\u092f\u093e \u092e\u0948\u0902 \u0907\u0928\u092e\u0947\u0902 \u0938\u0947 \u0915\u094b\u0908 refresh \u0915\u0930\u0942\u0901 \u092f\u093e Google post draft \u0915\u0930\u0942\u0901?"
        )
    cat_offers = category_context.get("offer_catalog", []) if isinstance(category_context, dict) else []
    if cat_offers:
        top = cat_offers[0].get("title") if isinstance(cat_offers[0], dict) else str(cat_offers[0])
        return (
            f"{name}, \u0905\u092d\u0940 \u0915\u094b\u0908 active offer \u0928\u0939\u0940\u0902 \u0939\u0948\u0964 "
            f"Main recommend \u0915\u0930\u0942\u0902\u0917\u093e: {top}\n"
            f"\u0915\u094d\u092f\u093e \u092e\u0948\u0902 \u0907\u0938\u094d\u0938\u0947 activate \u0915\u0930\u0942\u0901?"
        )
    return f"{name}, \u0905\u092d\u0940 \u0915\u094b\u0908 active offer \u0928\u0939\u0940\u0902 \u0939\u0948\u0964 Category \u0915\u0947 \u0939\u093f\u0938\u093e\u092c \u0938\u0947 suggest \u0915\u0930\u0942\u0901?"


def _hindi_perf(name, location, perf_summary, signals, category_context):
    body = f"{name}, \u092f\u0947 \u0930\u0939\u093e \u0906\u092a\u0915\u093e 30-day snapshot ({location}):\n{perf_summary}\n\n"
    if any("ctr_below" in s for s in signals):
        peer_ctr = category_context.get("peer_stats", {}).get("avg_ctr") if isinstance(category_context, dict) else None
        if peer_ctr:
            body += f"\u26a0\ufe0f \u0906\u092a\u0915\u093e CTR peer median ({peer_ctr*100:.1f}%) \u0938\u0947 \u0928\u0940\u091a\u0947 \u0939\u0948\u0964 Improve \u0915\u0930\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f post draft \u0915\u0930\u0942\u0901?"
    elif any("high" in s or "growing" in s or "above_peer" in s for s in signals):
        body += f"\u092c\u0922\u093c\u093f\u092f\u093e \u091a\u0932 \u0930\u0939\u093e \u0939\u0948! Follow-up campaign \u091a\u0932\u093e\u090a\u0901?"
    else:
        body += f"\u0907\u0938 week improve \u0915\u0930\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f \u0915\u094b\u0908 quick action suggest \u0915\u0930\u0942\u0901?"
    return body


def _hindi_greeting(name, location, cat_slug, active_offers, signals, trigger_ctx, category_context):
    if trigger_ctx:
        trigger_kind = trigger_ctx.get("kind", "update").replace("_", " ")
        trigger_payload = trigger_ctx.get("payload", {})
        body = f"Hi {name}! {location} \u0915\u0947 \u0932\u093f\u090f quick update:\nTrigger: {trigger_kind}\n"
        if trigger_ctx.get("kind") == "research_digest":
            digest = category_context.get("digest", []) if isinstance(category_context, dict) else []
            top_id = trigger_payload.get("top_item_id")
            if top_id and digest:
                for d in digest:
                    if isinstance(d, dict) and d.get("id") == top_id:
                        body += f"Research: {d.get('title', 'New study')}\n"
                        if d.get("source"): body += f"Source: {d['source']}\n"
                        break
        body += "\nAur details chahiye ya action draft karu?"
    else:
        body = f"Hi {name}! Aapka {cat_slug or 'business'} {location or 'your area'} \u092e\u0947\u0902 steady chal raha hai.\n"
        if active_offers:
            body += f"Aapka offer '{active_offers[0]}' active hai.\n"
        if signals:
            top_signal = signals[0].split(":")[0].replace("_", " ")
            body += f"Notice kiya: {top_signal}.\n"
        body += "Kuch specific check karna hai?"
    return body


def _hindi_profile(name, is_verified):
    body = f"{name}, "
    if is_verified is True:
        body += "\u0906\u092a\u0915\u093e Google profile verified \u0914\u0930 active \u0939\u0948\u0964\n"
    elif is_verified is False:
        body += "\u0906\u092a\u0915\u093e Google profile \u0905\u092d\u0940 verified \u0928\u0939\u0940\u0902 \u0939\u0948\u0964 \u0907\u0938\u0938\u0947 visibility ~30% \u0915\u092e \u0939\u094b\u0924\u0940 \u0939\u0948\u0964\nVerification \u092e\u0947\u0902 guide \u0915\u0930\u0942\u0901?\n"
    else:
        body += "profile status check karta hoon.\n"
    body += "Quick audit \u0915\u0930\u0942\u0901 \u0914\u0930 \u092c\u0924\u093e\u090a\u0901 \u0915\u094d\u092f\u093e missing \u0939\u0948?"
    return body


def _hindi_reviews(name, review_themes):
    if review_themes:
        themes_str = "\n".join(f"\u2022 {t['theme']}: {t['sentiment']} ({t['occurrences_30d']} mentions)" for t in review_themes[:3])
        return f"{name}, \u0907\u0938 \u092e\u0939\u0940\u0928\u0947 aapke reviews \u092e\u0947\u0902 \u092f\u0947 themes aa rahi hain:\n{themes_str}\n\nNegative reviews \u0915\u0947 replies draft \u0915\u0930\u0942\u0901?"
    return f"{name}, \u0905\u092d\u0940 \u0915\u094b\u0908 specific review theme \u0928\u0939\u0940\u0902 \u0939\u0948\u0964 Latest reviews pull \u0915\u0930\u0942\u0901?"


def _hindi_commitment(name, active_offers):
    next_step = "Main WhatsApp message + Google post draft karunga"
    if active_offers:
        next_step = f"Main '{active_offers[0]}' \u0915\u0947 around WhatsApp message + Google post draft karunga"
    first_name = name.split()[0] if isinstance(name, str) else ""
    return (
        f"Theek hai {first_name} \u2014 next steps:\n"
        f"1) {next_step}.\n"
        f"2) \u0906\u092a YES reply \u0915\u0930\u0947\u0902 approve \u0915\u0930\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f, \u092f\u093e 1 change bata dein.\n"
        f"3) Main final copy share karunga.\n"
        f"Proceed \u0915\u0930\u0947\u0902?"
    )


def _hindi_gst(name):
    return f"{name}, main aapke Google Business Profile \u0914\u0930 marketing pe focus karta hoon \u2014 tax filing pe nahi. GST \u0915\u0947 \u0932\u093f\u090f apne CA se connect \u0915\u0930\u0947\u0902\u0964 Listing se related kuch aur help chahiye?"


def _hindi_yes(name):
    return (
        f"Shandaar {name}! Main shuru karta hoon.\n"
        f"Aapke current data \u0915\u0947 basis pe draft prepare karunga. "
        f"Thoda time dijiye \u2014 yahan share karunga."
    )


def _hindi_no(name):
    return (
        f"Koi baat nahi {name}. Main baad \u092e\u0947\u0902 check karunga.\n"
        f"Agar mann badle, toh 'show me offers' \u092f\u093e 'how am I doing' \u0932\u093f\u0916 \u0926\u0947\u0902\u0964"
    )


def _hindi_fallback(name, location):
    city = location if location else "aapke area"
    return (
        f"{name} \u2014 {city} \u0915\u0947 \u0932\u093f\u090f quick update.\n"
        f"Trigger: general update.\n"
        f"\u0915\u094d\u092f\u093e \u0906\u092a \u091a\u093e\u0939\u0924\u0947 \u0939\u0948\u0902 main aapke best offer + ek clear CTA \u0915\u0947 saath message draft karu?"
    )


def _make_reply(action: str, body: str, cta: str, rationale: str, conv_id: str = None, wait_seconds: int = None):
    if conv_id and _check_repetition(conv_id, body):
        return ReplyAction(
            action="end",
            body="I notice I may have mentioned this before. Let me know when you're ready to take the next step!",
            cta="none",
            rationale="Detected exact repetition of previous response; ending conversation."
        )
    if conv_id:
        _record_response(conv_id, body)
    return ReplyAction(action=action, body=body, cta=cta, rationale=rationale, wait_seconds=wait_seconds)


@router.post("/v1/reply", response_model=ReplyAction)
async def reply(request: ReplyRequest):
    try:
        if not bot_state.conversation_manager:
            raise HTTPException(status_code=500, detail="Conversation manager not initialized")

        # Truncate oversized messages to prevent connection resets
        max_msg_len = 4096
        raw_message = request.message or ""
        if len(raw_message) > max_msg_len:
            raw_message = raw_message[:max_msg_len] + " [truncated]"

        msg_lower = raw_message.lower()
        msg_clean = msg_lower.strip().rstrip("?.!,")

        has_hindi = _is_hindi(raw_message)
        has_hinglish = _is_hinglish(raw_message)
        use_hindi = has_hindi or has_hinglish

        hostile_markers = ["stop", "unsubscribe", "useless", "spam", "don't message", "do not message", "never message", "block"]
        if any(m in msg_lower for m in hostile_markers):
            bot_state.conversation_manager.end_conversation(request.conversation_id)
            return ReplyAction(action="end", rationale="User asked to stop / hostile message. Exiting conversation.")

        disinterest = ["not interested", "no thanks", "don't want", "do not want", "no need", "stop it"]
        if any(m in msg_lower for m in disinterest):
            bot_state.conversation_manager.end_conversation(request.conversation_id)
            return ReplyAction(action="end", rationale="Merchant not interested. Exiting conversation politely.")

        later_markers = ["later", "tomorrow", "call me later", "busy", "not now", "send later", "remind me"]
        if any(m in msg_lower for m in later_markers):
            return ReplyAction(action="wait", wait_seconds=3600, rationale="Merchant asked to come back later; backing off 1 hour.")

        if request.conversation_id not in bot_state.conversation_manager.conversation_metadata:
            bot_state.conversation_manager.create_conversation(
                conversation_id=request.conversation_id,
                merchant_id=request.merchant_id,
                customer_id=request.customer_id,
            )

        bot_state.conversation_manager.add_turn(
            request.conversation_id, request.from_role, request.message, request.turn_number
        )

        conv_context = bot_state.conversation_manager.get_conversation_context(request.conversation_id)
        if conv_context and conv_context.get("status") == "ended":
            return ReplyAction(action="end", rationale="Conversation already ended; ignoring further messages.")

        is_auto_reply = bot_state.conversation_manager.detect_auto_reply(request.conversation_id)
        if is_auto_reply:
            bot_state.conversation_manager.end_conversation(request.conversation_id)
            return ReplyAction(
                action="end",
                rationale="Detected auto-reply pattern. Exiting conversation gracefully."
            )
        merchant_context = None
        if bot_state.context_store:
            raw_merchant = bot_state.context_store.get_context("merchant", request.merchant_id)
            merchant_context = json.loads(json.dumps(raw_merchant)) if raw_merchant else {}

        cat_slug = merchant_context.get("category_slug") if isinstance(merchant_context, dict) else None
        category_context = {}
        if cat_slug and bot_state.context_store:
            category_context = bot_state.context_store.get_context("category", cat_slug) or {}

        name = _get_merchant_name(merchant_context)
        active_offers = _get_active_offers(merchant_context)
        perf_summary = _get_perf_summary(merchant_context)
        signals = merchant_context.get("signals", []) if isinstance(merchant_context, dict) else []
        city = merchant_context.get("identity", {}).get("city", "") if isinstance(merchant_context, dict) else ""
        locality = merchant_context.get("identity", {}).get("locality", "") if isinstance(merchant_context, dict) else ""
        location = f"{locality}, {city}" if locality and city else city or ""
        cid = request.conversation_id

        # Extract trigger_context specifically for this conversation
        trigger_context = {}
        if conv_context and bot_state.context_store:
            trigger_id = conv_context.get("trigger_id")
            if trigger_id:
                trigger_context = bot_state.context_store.get_context("trigger", trigger_id) or {}
        if not trigger_context:
            trigger_context = _find_best_trigger_for_merchant(request.merchant_id)
            
        trig_kind = trigger_context.get("kind", "").lower() if trigger_context else ""
        trig_payload = trigger_context.get("payload", {}) if trigger_context else {}

        # ── Customer-facing reply routing ──
        is_customer_conv = request.from_role.lower() in ["customer", "user"] or bool(request.customer_id)
        if conv_context and conv_context.get("customer_id"):
            is_customer_conv = True

        if is_customer_conv:
            customer_name = ""
            customer_context = None
            if bot_state.context_store and request.customer_id:
                customer_context = bot_state.context_store.get_context("customer", request.customer_id)
                if customer_context:
                    cust_id = customer_context.get("identity", {})
                    customer_name = cust_id.get("name", "")

            # Slot booking / appointment confirmation - MUST use send action
            booking_markers = ["book me", "book for", "appointment", "slot", " nov ", " dec ", " jan ", " feb ", " mar ", " apr ", " may ", " jun ", " jul ", " aug ", " sep ", " oct ", "pm", "am", ":00", ":30", "tomorrow", "next week", "time"]
            if any(m in msg_lower for m in booking_markers):
                body = f"Confirmed! I've noted your appointment. {customer_name or 'See you'} at the scheduled time. Reply STOP to cancel."
                return _make_reply("send", body, "none", "Customer confirmed slot; sending confirmation.", cid)

            # Customer stop
            if any(m in msg_lower for m in hostile_markers):
                bot_state.conversation_manager.end_conversation(request.conversation_id)
                return ReplyAction(action="end", rationale="Customer asked to stop; ending conversation.")

            # Customer commitment (yes please, yes book)
            commitment_markers = ["yes please", "yes book", "book", "confirm", "ok book", "okay book"]
            if any(m in msg_lower for m in commitment_markers):
                body = f"Great! I've booked your slot. {customer_name or 'See you'} soon! Reply STOP to cancel anytime."
                return _make_reply("send", body, "none", "Customer committed to booking; confirming.", cid)

            # Customer question
            question_markers = ["what", "how", "when", "where", "why", "cost", "price", "fee", "charge"]
            if any(m in msg_lower for m in question_markers):
                offer_ref = f"\nOffer: {active_offers[0]}." if active_offers else ""
                body = f"Hi{f' {customer_name}' if customer_name else ''}! {name} here.{offer_ref}\nHappy to answer — what would you like to know?"
                return _make_reply("send", body, "open_ended", "Customer asked question; responding with context.", cid)

            # Customer greeting
            if any(k in msg_lower for k in ["hi", "hello", "hey", "namaste"]):
                offer_ref = f" Current offer: {active_offers[0]}." if active_offers else ""
                body = f"Hi{f' {customer_name}' if customer_name else ''}! {name} here.{offer_ref}\nHow can we help you today?"
                return _make_reply("send", body, "open_ended", "Customer greeted; welcoming with offer info.", cid)

            # Default customer reply
            offer_ref = f" Offer: {active_offers[0]}." if active_offers else ""
            body = f"Thanks{f' {customer_name}' if customer_name else ''}! {name} here.{offer_ref}\nWe'll get back to you shortly."
            return _make_reply("send", body, "open_ended", "Default customer response.", cid)

        # ── Merchant-facing reply routing ──
        # Detect merchant intent and respond contextually
        msg_has_hindi = _is_hindi(raw_message)
        msg_has_hinglish = _is_hinglish(raw_message)
        merchant_use_hindi = msg_has_hindi or msg_has_hinglish

        # Objection handling
        objections = ["no budget", "too expensive", "cant afford", "can't afford", "not worth it", "waste of money", "dont need this", "don't need this", "don't have budget", "cannot afford", "not now, budget"]
        if any(m in msg_lower for m in objections):
            if use_hindi:
                body = (
                    f"{name}, samajh sakta hoon. Budget concern valid hai.\n"
                    f"Good news: basic features free hain. Koi cost nahi.\n"
                    f"Shuru karein? Sirf 2 min lagenge."
                )
            else:
                body = (
                    f"Understood, {name}. Budget matters.\n"
                    f"The good news: the basic actions I'm suggesting are free — no cost to you.\n"
                    f"Want me to show you what you can do at zero spend?"
                )
            return _make_reply("send", body, "binary_yes_no", "Objection on budget; reframing with free options.", cid)

        # Context-specific merchant question handling - address what merchant actually asked
        # (trigger_context and trig_kind are loaded above)

        # If merchant asks about specific setup/equipment related to regulation
        setup_markers = ["setup", "equipment", "unit", "machine", "device", "x-ray", "film", "audit", "checking", "check my", "help", "need help", "how to"]
        if any(m in msg_lower for m in setup_markers) and "regulation" in trig_kind:
            deadline = trig_payload.get("deadline_iso", "")
            deadline_display = f" by {deadline[:10]}" if deadline else ""
            actionable = ""
            digest = category_context.get("digest", []) if isinstance(category_context, dict) else []
            top_id = trig_payload.get("top_item_id") or trig_payload.get("alert_id")
            if top_id and digest:
                for d in digest:
                    if isinstance(d, dict) and d.get("id") == top_id:
                        actionable = d.get("actionable", "")
                        break
            action_line = f" Action: {actionable}" if actionable else ""
            body = (
                f"{name}, good that you're proactive about compliance.{action_line}.\n"
                f"Deadline{deadline_display} — I recommend scheduling an audit this week.\n"
                f"Want me to draft a compliance checklist + patient notification message?"
            )
            return _make_reply("send", body, "binary_yes_no", "Merchant asked about regulation compliance setup; providing actionable guidance.", cid)

        # If merchant asks about performance/dip related to trigger
        if any(m in msg_lower for m in ["why", "what happened", "what caused", "reason"]) and trig_kind in ["perf_dip", "seasonal_perf_dip"]:
            metric = trig_payload.get("metric", "views")
            delta = trig_payload.get("delta_pct")
            pct = int(round(float(delta) * 100)) if delta is not None else 0
            body = (
                f"{name}, your {metric} dropped {abs(pct)}% recently. This often happens due to stale posts, outdated offers, or seasonal shifts.\n"
                f"Quick fix: Refresh your top offer + post 2 GBP updates this week.\n"
                f"Want me to draft both?"
            )
            return _make_reply("send", body, "binary_yes_no", "Merchant asked about performance dip cause; explaining + offering fix.", cid)

        if any(k in msg_lower for k in ["offer", "my offer", "current offer", "what offer"]):
            if use_hindi:
                body = _hindi_offers(name, active_offers, category_context)
            elif active_offers:
                offers_str = "\n".join(f"\u2022 {o}" for o in active_offers)
                body = f"{name}, here are your active offers:\n{offers_str}\n\nWant me to refresh one of these or draft a Google post around it?"
            else:
                cat_offers = category_context.get("offer_catalog", []) if isinstance(category_context, dict) else []
                if cat_offers:
                    top = cat_offers[0].get("title") if isinstance(cat_offers[0], dict) else str(cat_offers[0])
                    body = f"{name}, you don't have any active offers right now. I recommend setting up: {top}\nWant me to activate it for you?"
                else:
                    body = f"{name}, you don't have any active offers currently. Want me to suggest one based on your category?"
            return _make_reply("send", body, "open_ended", "Merchant asked about offers; showing current or recommending new.", cid)

        if any(k in msg_lower for k in ["performance", "how am i doing", "my numbers", "stats", "dashboard"]):
            if use_hindi:
                body = _hindi_perf(name, location, perf_summary, signals, category_context)
            else:
                body = f"{name}, here's your 30-day snapshot ({location}):\n{perf_summary}\n\n"
                if any("ctr_below" in s for s in signals):
                    peer_ctr = category_context.get("peer_stats", {}).get("avg_ctr") if isinstance(category_context, dict) else None
                    if peer_ctr:
                        body += f"\u26a0\ufe0f Your CTR is below peer median ({peer_ctr*100:.1f}%). Want me to draft a post to improve this?"
                elif any("high" in s or "growing" in s or "above_peer" in s for s in signals):
                    body += f"Looking solid! Want me to double down with a follow-up campaign?"
                else:
                    body += f"Want me to suggest one quick action to improve this week?"
            return _make_reply("send", body, "open_ended", "Merchant asked about performance; sharing numbers + contextual suggestion.", cid)

        if any(k in msg_lower for k in ["hi", "hello", "hey", "what's new", "what is new", "any update"]):
            if use_hindi:
                body = _hindi_greeting(name, location, cat_slug, active_offers, signals, trigger_context, category_context)
            elif trigger_context:
                trigger_kind = trigger_context.get("kind", "update").replace("_", " ")
                trigger_payload = trigger_context.get("payload", {})
                body = f"Hi {name}! Quick update for {location}:\nTrigger: {trigger_kind}\n"
                if trigger_context.get("kind") == "research_digest":
                    digest = category_context.get("digest", []) if isinstance(category_context, dict) else []
                    top_id = trigger_payload.get("top_item_id")
                    if top_id and digest:
                        for d in digest:
                            if isinstance(d, dict) and d.get("id") == top_id:
                                body += f"Research: {d.get('title', 'New study')}\n"
                                if d.get("source"): body += f"Source: {d['source']}\n"
                                break
                body += "\nWant me to pull more details or draft an action?"
            else:
                body = f"Hi {name}! Everything looks steady for your {cat_slug or 'business'} in {location or 'your area'}.\n"
                if active_offers:
                    body += f"Your offer '{active_offers[0]}' is active and running.\n"
                if signals:
                    top_signal = signals[0].split(":")[0].replace("_", " ")
                    body += f"Noticed: {top_signal}.\n"
                body += "Want me to check anything specific?"
            return _make_reply("send", body, "open_ended", "Merchant greeted; providing contextual update.", cid)

        if any(k in msg_lower for k in ["gst", "tax", "itr", "file tax", "gst return"]):
            body = _hindi_gst(name) if use_hindi else f"{name}, I focus on your Google Business Profile and marketing \u2014 not tax filing. For GST, I'd recommend connecting with your CA. Want help with anything else related to your listing?"
            return _make_reply("send", body, "open_ended", "Merchant asked off-topic GST question; polite deflection.", cid)

        if any(k in msg_lower for k in ["profile", "google profile", "my listing", "my page", "gbp"]):
            is_verified = merchant_context.get("identity", {}).get("verified") if isinstance(merchant_context, dict) else None
            if use_hindi:
                body = _hindi_profile(name, is_verified)
            else:
                body = f"{name}, "
                if is_verified is True:
                    body += "your Google profile is verified and active.\n"
                elif is_verified is False:
                    body += "your Google profile is NOT verified yet. This reduces visibility by ~30%.\nWant me to guide you through verification?\n"
                else:
                    body += "let me check your profile status.\n"
                body += "Want me to do a quick audit and tell you what's missing?"
            return _make_reply("send", body, "binary_yes_no", "Merchant asked about profile; showing status + offering audit.", cid)

        if any(k in msg_lower for k in ["review", "rating", "what are people saying"]):
            review_themes = merchant_context.get("review_themes", []) if isinstance(merchant_context, dict) else []
            if use_hindi:
                body = _hindi_reviews(name, review_themes)
            elif review_themes:
                themes_str = "\n".join(f"\u2022 {t['theme']}: {t['sentiment']} ({t['occurrences_30d']} mentions)" for t in review_themes[:3])
                body = f"{name}, here's what's showing in your reviews this month:\n{themes_str}\n\nWant me to draft responses to the negative ones?"
            else:
                body = f"{name}, I don't have specific review themes loaded right now. Want me to pull your latest reviews?"
            return _make_reply("send", body, "open_ended", "Merchant asked about reviews; showing themes + offering response drafts.", cid)

        commitment_markers = ["ok lets do it", "okay lets do it", "let's do it", "whats next", "what's next", "do it", "lets start", "yes please", "yes proceed", "go ahead", "proceed"]
        if any(m in msg_lower for m in commitment_markers):
            if use_hindi:
                body = _hindi_commitment(name, active_offers)
            else:
                offer_ref = f"around '{active_offers[0]}'" if active_offers else ""
                body = (
                    f"Done, {name.split()[0] if isinstance(name, str) else 'done'} \u2014 next steps:\n"
                    f"1) I will draft a WhatsApp message {offer_ref} + a Google post.\n"
                    f"2) You reply YES to approve, or tell me 1 change.\n"
                    f"3) I will share the final copy to send.\n"
                    f"Proceed?"
                )
            return _make_reply("send", body, "binary_yes_no", "Merchant committed; switching to execution.", cid)

        if msg_clean in ["yes", "sure", "ok", "okay", "go", "yeah", "haan", "ha"] or any(k in msg_lower for k in ["tell me more", "more details", "what are"]):
            topic = trig_payload.get("question_topic") or trig_payload.get("milestone", "")
            if topic:
                topic = topic.replace("_", " ")
            if active_offers and not topic:
                offers_info = f"Your active offers: {', '.join(active_offers)}.\n"
                body = f"{name}, {offers_info}Want me to draft a campaign around one of these?"
            elif topic:
                body = f"{name}, about {topic}: I can draft a focused message + Google post. Your top offer is {active_offers[0] if active_offers else 'active'}. Want me to proceed?"
            elif use_hindi:
                body = _hindi_yes(name)
            else:
                body = (
                    f"Great, {name}! I'll get started.\n"
                    f"I'll pull together a draft based on your current data. "
                    f"Give me a moment \u2014 I'll share it here."
                )
            return _make_reply("send", body, "none", "Merchant said yes; acknowledging and preparing next action.", cid)

        if msg_clean in ["no", "nope", "nah", "not now", "nahi"]:
            body = _hindi_no(name) if use_hindi else (
                f"No problem, {name}. I'll check back later.\n"
                f"If you change your mind, just say 'show me offers' or 'how am I doing'."
            )
            return _make_reply("wait", body, "none", "Merchant declined; backing off for 1 hour.", cid, 3600)

        if bot_state.composition_service:
            conversation_history = bot_state.conversation_manager.get_conversation(request.conversation_id)

            composed = await bot_state.composition_service.compose(
                category=category_context,
                merchant=merchant_context or {},
                trigger=trigger_context,
                customer=None,
                conversation_history=conversation_history,
                force_template=False,
            )
            return _make_reply("send", composed.body, composed.cta, composed.rationale, cid)

        body = _hindi_fallback(name, location) if use_hindi else "Thanks for your message. I'm processing this now."
        return _make_reply("send", body, "open_ended", "Fallback response.", cid)

    except asyncio.TimeoutError:
        return ReplyAction(action="wait", wait_seconds=300, rationale="Processing timeout, backing off.")
    except Exception as e:
        print(f"Error in reply: {e}")
        return ReplyAction(action="wait", wait_seconds=60, rationale=f"Error occurred: {str(e)}")
