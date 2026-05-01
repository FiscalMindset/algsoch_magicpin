#!/usr/bin/env python3
"""
Unit tests for magicpin composition and tick logic.
Runs locally without a server — directly imports the modules.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from datetime import datetime, timezone
from app.services.composition import ContextStore, ConversationManager, CompositionService
from app.services.state import BotState

PASS = 0
FAIL = 0
TOTAL = 0


def check(name, condition, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    return condition


def make_store():
    store = ContextStore()
    store.store_context("category", "dentists", 1, {
        "slug": "dentists",
        "offer_catalog": [{"title": "Dental Cleaning @ ₹299", "status": "active"}],
        "voice": {"tone": "peer_clinical", "taboos": ["cure", "guaranteed"]},
        "peer_stats": {"avg_ctr": 0.030},
        "digest": [{"id": "d_001", "title": "Fluoride recall study", "source": "JIDA", "trial_n": 2100}],
    })
    store.store_context("merchant", "m_001", 1, {
        "merchant_id": "m_001",
        "category_slug": "dentists",
        "identity": {"name": "Dr. Meera's Clinic", "city": "Delhi", "locality": "Lajpat Nagar", "languages": ["en", "hi"]},
        "performance": {"views": 2410, "calls": 18, "ctr": 0.021},
        "offers": [{"id": "o_001", "title": "Dental Cleaning @ ₹299", "status": "active"}],
        "signals": ["ctr_below_peer_median"],
    })
    store.store_context("customer", "c_001", 1, {
        "customer_id": "c_001",
        "merchant_id": "m_001",
        "identity": {"name": "Priya", "language_pref": "hi-en mix"},
        "relationship": {"last_visit": "2026-05-12", "visits_total": 4, "services_received": ["cleaning", "whitening"]},
        "consent": {"scope": ["recall_reminders"]},
    })
    return store


def test_01_context_store_versioning():
    store = make_store()
    cur = store.get_version("category", "dentists")
    check("Initial version is 1", cur == 1, f"Got: {cur}")
    stored = store.store_context("category", "dentists", 1, {"slug": "dentists"})
    check("Same version rejected", stored == False)
    stored = store.store_context("category", "dentists", 2, {"slug": "dentists", "new": True})
    check("Higher version accepted", stored == True)
    check("Version updated to 2", store.get_version("category", "dentists") == 2)


def test_01_composition_known_trigger():
    store = make_store()
    comp = CompositionService()
    trigger = {
        "id": "trg_research",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "merchant_id": "m_001",
        "customer_id": None,
        "payload": {"top_item_id": "d_001"},
        "urgency": 2,
    }
    import asyncio
    msg = asyncio.get_event_loop().run_until_complete(comp.compose(
        category=store.get_context("category", "dentists"),
        merchant=store.get_context("merchant", "m_001"),
        trigger=trigger,
        customer=None,
        force_template=True,
    ))
    check("Known trigger produces body", bool(msg.body), f"Body: {msg.body[:80] if msg.body else 'EMPTY'}")
    check("Body mentions research/digest", any(x in msg.body.lower() for x in ["research", "digest", "nugget", "update"]),
          f"Body: {msg.body[:120]}")


def test_03_composition_unknown_trigger():
    store = make_store()
    comp = CompositionService()
    trigger = {
        "id": "trg_unknown",
        "scope": "merchant",
        "kind": "inventory_surplus_detected",
        "source": "internal",
        "merchant_id": "m_001",
        "customer_id": None,
        "payload": {"surplus_slots": 12, "week": "2026-W18"},
        "urgency": 3,
    }
    import asyncio
    msg = asyncio.get_event_loop().run_until_complete(comp.compose(
        category=store.get_context("category", "dentists"),
        merchant=store.get_context("merchant", "m_001"),
        trigger=trigger,
        customer=None,
        force_template=True,
    ))
    check("Unknown trigger produces body", bool(msg.body), f"Body: {msg.body[:80] if msg.body else 'EMPTY'}")
    check("Body mentions trigger kind", "inventory surplus detected" in msg.body.lower() or "inventory" in msg.body.lower(),
          f"Body: {msg.body[:120]}")
    check("Body includes performance facts", any(x in msg.body.lower() for x in ["views", "calls", "ctr"]),
          f"Body: {msg.body[:120]}")


def test_04_customer_scope_with_context():
    store = make_store()
    comp = CompositionService()
    trigger = {
        "id": "trg_recall",
        "scope": "customer",
        "kind": "recall_due",
        "source": "internal",
        "merchant_id": "m_001",
        "customer_id": "c_001",
        "payload": {},
        "urgency": 4,
    }
    import asyncio
    msg = asyncio.get_event_loop().run_until_complete(comp.compose(
        category=store.get_context("category", "dentists"),
        merchant=store.get_context("merchant", "m_001"),
        trigger=trigger,
        customer=store.get_context("customer", "c_001"),
        force_template=True,
    ))
    check("Customer recall produces body", bool(msg.body), f"Body: {msg.body[:80] if msg.body else 'EMPTY'}")
    check("Body mentions customer name", "Priya" in msg.body, f"Body: {msg.body[:120]}")


def test_05_customer_scope_without_context():
    store = make_store()
    comp = CompositionService()
    trigger = {
        "id": "trg_recall_no_cust",
        "scope": "customer",
        "kind": "recall_due",
        "source": "internal",
        "merchant_id": "m_001",
        "customer_id": "c_nonexistent",
        "payload": {},
        "urgency": 4,
    }
    import asyncio
    msg = asyncio.get_event_loop().run_until_complete(comp.compose(
        category=store.get_context("category", "dentists"),
        merchant=store.get_context("merchant", "m_001"),
        trigger=trigger,
        customer=None,
        force_template=True,
    ))
    check("Customer scope without context returns empty body", msg.body == "", f"Body: {msg.body[:80]}")


def test_06_conversation_manager_auto_reply():
    cm = ConversationManager()
    cm.create_conversation("conv_001", "m_001")
    auto_msg = "Thanks for your message. We'll get back to you soon."
    for i in range(4):
        cm.add_turn("conv_001", "merchant", auto_msg, i + 1)
    check("Auto-reply detected after 4 identical messages", cm.detect_auto_reply("conv_001") == True)


def test_07_conversation_manager_no_auto_reply():
    cm = ConversationManager()
    cm.create_conversation("conv_002", "m_001")
    cm.add_turn("conv_002", "merchant", "Yes, please proceed", 1)
    cm.add_turn("conv_002", "merchant", "Tell me more", 2)
    cm.add_turn("conv_002", "merchant", "What are the options", 3)
    check("Different messages not flagged as auto-reply", cm.detect_auto_reply("conv_002") == False)


def test_08_suppression_key_determinism():
    from app.routes.tick import _deterministic_conversation_id
    cid1 = _deterministic_conversation_id("m_001", "trg_001")
    cid2 = _deterministic_conversation_id("m_001", "trg_001")
    check("Conversation ID is deterministic", cid1 == cid2, f"cid1={cid1}, cid2={cid2}")
    check("Conversation ID format correct", cid1 == "conv:m_001:trg_001", f"Got: {cid1}")


def test_09_conversation_id_with_customer():
    from app.routes.tick import _deterministic_conversation_id
    cid = _deterministic_conversation_id("m_001", "trg_001", "c_001")
    check("Conversation ID includes customer", cid == "conv:m_001:trg_001:c_001", f"Got: {cid}")


def test_10_priority_scoring():
    from app.routes.tick import _compute_priority
    from app.services import bot_state
    bot_state.context_store = make_store()
    p1 = _compute_priority({"id": "trg_high", "urgency": 5})
    p2 = _compute_priority({"id": "trg_low", "urgency": 1})
    check("High urgency has higher priority", p1 > p2, f"p1={p1}, p2={p2}")


if __name__ == "__main__":
    print("Unit Tests — Composition & Tick Logic")
    print("=" * 60)

    tests = [
        test_01_context_store_versioning,
        test_01_composition_known_trigger,
        test_03_composition_unknown_trigger,
        test_04_customer_scope_with_context,
        test_05_customer_scope_without_context,
        test_06_conversation_manager_auto_reply,
        test_07_conversation_manager_no_auto_reply,
        test_08_suppression_key_determinism,
        test_09_conversation_id_with_customer,
        test_10_priority_scoring,
    ]

    for test_fn in tests:
        print(f"\n--- {test_fn.__doc__.strip()} ---")
        try:
            test_fn()
        except Exception as e:
            TOTAL += 1
            FAIL += 1
            import traceback
            print(f"  [FAIL] {test_fn.__name__} — Exception: {e}")
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS}/{TOTAL} passed, {FAIL} failed")
    sys.exit(0 if FAIL == 0 else 1)
