from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import bot_state

router = APIRouter(prefix="/v1/playground", tags=["playground"])

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_DIR = REPO_ROOT / "dataset"
GEN_SCRIPT = SEED_DIR / "generate_dataset.py"
EXPANDED_DIR = REPO_ROOT / "expanded"


def _ensure_expanded() -> None:
    test_pairs = EXPANDED_DIR / "test_pairs.json"
    if test_pairs.exists():
        return
    if not GEN_SCRIPT.exists():
        raise HTTPException(status_code=500, detail="Dataset generator not found")
    try:
        EXPANDED_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                sys.executable,
                str(GEN_SCRIPT),
                "--seed-dir",
                str(SEED_DIR),
                "--out",
                str(EXPANDED_DIR),
            ],
            check=True,
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate expanded dataset: {e}") from e


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_test_pairs() -> List[Dict[str, Any]]:
    _ensure_expanded()
    data = _read_json(EXPANDED_DIR / "test_pairs.json")
    return data.get("pairs", [])


def _load_merchant(merchant_id: str) -> Dict[str, Any]:
    _ensure_expanded()
    path = EXPANDED_DIR / "merchants" / f"{merchant_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Merchant not found")
    return _read_json(path)


def _load_trigger(trigger_id: str) -> Dict[str, Any]:
    _ensure_expanded()
    path = EXPANDED_DIR / "triggers" / f"{trigger_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _read_json(path)


def _load_customer(customer_id: str) -> Dict[str, Any]:
    _ensure_expanded()
    path = EXPANDED_DIR / "customers" / f"{customer_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Customer not found")
    return _read_json(path)


def _load_category(slug: str) -> Dict[str, Any]:
    _ensure_expanded()
    path = EXPANDED_DIR / "categories" / f"{slug}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Category not found")
    return _read_json(path)


class GenerateResponse(BaseModel):
    ok: bool
    expanded_dir: str
    generated_at: datetime


@router.post("/generate", response_model=GenerateResponse)
async def generate():
    """Generate the deterministic expanded dataset (if missing)."""
    _ensure_expanded()
    return GenerateResponse(ok=True, expanded_dir=str(EXPANDED_DIR), generated_at=datetime.utcnow())


class ResetResponse(BaseModel):
    ok: bool
    cleared: Dict[str, int]
    reset_at: datetime


@router.post("/reset", response_model=ResetResponse)
async def reset_bot_state():
    """
    Local-only helper to reset in-memory bot state for repeatable manual testing.
    Does not exist in the official challenge contract.
    """
    cleared = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0, "conversations": 0}

    if bot_state.context_store:
        counts = bot_state.context_store.get_contexts_count()
        cleared.update(counts)
        bot_state.context_store.clear()

    if bot_state.conversation_manager:
        cleared["conversations"] = len(bot_state.conversation_manager.get_all_conversations() or {})
        bot_state.conversation_manager.conversations = {}
        bot_state.conversation_manager.conversation_metadata = {}

    if hasattr(bot_state, "sent_suppression_keys") and bot_state.sent_suppression_keys is not None:
        bot_state.sent_suppression_keys.clear()

    return ResetResponse(ok=True, cleared=cleared, reset_at=datetime.utcnow())


class TestPairView(BaseModel):
    test_id: str
    trigger_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    kind: Optional[str] = None
    category_slug: Optional[str] = None
    merchant_name: Optional[str] = None


@router.get("/test-pairs", response_model=List[TestPairView])
async def test_pairs():
    """Return the 30 canonical test pairs with light enrichment for UI."""
    pairs = _load_test_pairs()
    enriched: List[TestPairView] = []
    for p in pairs:
        trig = _load_trigger(p["trigger_id"])
        merch = _load_merchant(p["merchant_id"])
        enriched.append(
            TestPairView(
                test_id=p["test_id"],
                trigger_id=p["trigger_id"],
                merchant_id=p["merchant_id"],
                customer_id=p.get("customer_id"),
                kind=trig.get("kind"),
                category_slug=merch.get("category_slug"),
                merchant_name=merch.get("identity", {}).get("name") or merch.get("identity", {}).get("business_name"),
            )
        )
    return enriched


class TestCaseResponse(BaseModel):
    test_id: str
    category: Dict[str, Any]
    merchant: Dict[str, Any]
    trigger: Dict[str, Any]
    customer: Optional[Dict[str, Any]] = None


@router.get("/test-case/{test_id}", response_model=TestCaseResponse)
async def test_case(test_id: str):
    """Load a full test case (category + merchant + trigger + optional customer)."""
    pair = next((p for p in _load_test_pairs() if p.get("test_id") == test_id), None)
    if not pair:
        raise HTTPException(status_code=404, detail="Test case not found")

    trigger = _load_trigger(pair["trigger_id"])
    merchant = _load_merchant(pair["merchant_id"])
    category = _load_category(merchant.get("category_slug", ""))
    customer = _load_customer(pair["customer_id"]) if pair.get("customer_id") else None

    return TestCaseResponse(
        test_id=test_id,
        category=category,
        merchant=merchant,
        trigger=trigger,
        customer=customer,
    )


class ComposeRequest(BaseModel):
    test_id: str
    force_template: bool = True


@router.post("/compose")
async def compose(req: ComposeRequest):
    """
    Compose the next proactive message for a test case (local UI helper).
    This does not affect judge endpoints; it exists only for human testing.
    """
    case = await test_case(req.test_id)
    if not bot_state.composition_service:
        raise HTTPException(status_code=500, detail="Composition service not initialized")

    composed = await bot_state.composition_service.compose(
        category=case.category,
        merchant=case.merchant,
        trigger=case.trigger,
        customer=case.customer,
        conversation_history=None,
        force_template=req.force_template,
    )

    return {
        "test_id": req.test_id,
        "message": composed.model_dump(),
    }
