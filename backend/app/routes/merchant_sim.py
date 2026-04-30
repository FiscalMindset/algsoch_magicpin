import httpx
import os
import re
import json
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import bot_state

router = APIRouter(prefix="/v1/simulate", tags=["simulate"])

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MERCHANT_MODEL", "phi3:latest")


class MerchantSimRequest(BaseModel):
    merchant_name: str
    category: str
    city: str
    bot_message: str
    bot_cta: Optional[str] = None
    conversation_history: list = []
    personality: Optional[str] = "normal"  # "normal", "hostile", "enthusiastic", "busy"


class MerchantSimResponse(BaseModel):
    merchant_reply: str
    intent: str
    confidence: float


PERSONALITY_PROMPTS = {
    "normal": "You are a realistic Indian small business owner (merchant) chatting with an AI assistant called Vera on WhatsApp. You speak in a mix of Hindi and English (Hinglish). You are polite but practical, focused on your business. Keep replies short (1-3 sentences).",
    "hostile": "You are an irritated Indian business owner who thinks AI messages are spam. You are rude, dismissive, and want to stop receiving messages. Keep replies very short (1 sentence max).",
    "enthusiastic": "You are an enthusiastic Indian business owner who loves new technology. You are eager to try everything Vera suggests and always ask follow-up questions. Keep replies short but energetic.",
    "busy": "You are a busy Indian business owner who barely has time to check messages. You give very short, clipped responses. Often say 'later', 'busy', or 'send me details'.",
    "auto_reply": "You are a WhatsApp Business auto-reply bot. You send the same formal canned response every time: 'Thank you for contacting us. We will get back to you shortly.' Always send the exact same message.",
}


@router.post("/ollama-merchant", response_model=MerchantSimResponse)
async def simulate_ollama_merchant(req: MerchantSimRequest):
    """
    Use Ollama to simulate a realistic merchant reply.
    This endpoint generates a merchant response based on the bot's message and context.
    """
    try:
        personality = req.personality or "normal"
        sys_prompt = PERSONALITY_PROMPTS.get(personality, PERSONALITY_PROMPTS["normal"])

        conversation_context = ""
        for turn in req.conversation_history[-4:]:
            role = "Vera" if turn.get("role") == "bot" else req.merchant_name
            conversation_context += f"[{role}]: {turn.get('text', '')}\n"

        prompt = f"""{sys_prompt}

MERCHANT CONTEXT:
- Name: {req.merchant_name}
- Business: {req.category} in {req.city}

CONVERSATION SO FAR:
{conversation_context}

VERA'S LATEST MESSAGE:
"{req.bot_message}"

CTA FROM VERA: {req.bot_cta or 'none'}

Respond as the merchant. Output JSON only:
{{"reply": "<merchant's reply>", "intent": "<yes|no|question|hostile|auto_reply|neutral|commitment|not_interested>","confidence": <0.5-1.0>}}"""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7},
                },
            )
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "")

        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            parsed = json.loads(match.group())
            return MerchantSimResponse(
                merchant_reply=parsed.get("reply", raw.strip()),
                intent=parsed.get("intent", "neutral"),
                confidence=float(parsed.get("confidence", 0.7)),
            )

        return MerchantSimResponse(
            merchant_reply=raw.strip(),
            intent="neutral",
            confidence=0.5,
        )

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama connection failed: {str(e)}. Make sure Ollama is running at {OLLAMA_URL}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merchant simulation failed: {str(e)}")


@router.get("/ollama-healthz")
async def ollama_healthz():
    """Check if Ollama is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return {
                    "status": "ok",
                    "ollama_url": OLLAMA_URL,
                    "available_models": [m.get("name") for m in models],
                    "merchant_model": OLLAMA_MODEL,
                }
    except Exception as e:
        pass

    return {
        "status": "unavailable",
        "ollama_url": OLLAMA_URL,
        "error": "Ollama is not running or not reachable",
    }


@router.post("/ollama-reply")
async def ollama_reply(req: MerchantSimRequest):
    """
    Simplified version: just returns the merchant reply string.
    For use in conversational flow.
    """
    sim_result = await simulate_ollama_merchant(req)
    return {"reply": sim_result.merchant_reply, "intent": sim_result.intent, "confidence": sim_result.confidence}
