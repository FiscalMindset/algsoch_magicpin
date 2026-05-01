#!/usr/bin/env python3
"""
Adversarial Magicpin Probe Tests — 15 proof tests
==================================================

Tests the bot against unseen contexts, edge cases, and judge scenarios.

Usage:
    python tests/adversarial_magicpin_probe.py [BOT_URL]

Default BOT_URL: http://localhost:8000
"""

import sys
import json
import time
from datetime import datetime, timezone
from urllib import request, error

BOT_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

PASS = 0
FAIL = 0
TOTAL = 0


def _req(method, path, body=None):
    url = f"{BOT_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        resp = request.urlopen(req, timeout=15)
        return resp.status, json.loads(resp.read())
    except error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.read else {}
    except Exception as e:
        return 0, {"error": str(e)}


def post(path, body):
    return _req("POST", path, body)


def get(path):
    return _req("GET", path)


def push_context(scope, context_id, version, payload):
    return post("/v1/context", {
        "scope": scope,
        "context_id": context_id,
        "version": version,
        "payload": payload,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
    })


def tick(now, available_triggers):
    return post("/v1/tick", {
        "now": now,
        "available_triggers": available_triggers,
    })


def reply(conversation_id, merchant_id, from_role, message, turn_number, customer_id=None):
    return post("/v1/reply", {
        "conversation_id": conversation_id,
        "merchant_id": merchant_id,
        "customer_id": customer_id,
        "from_role": from_role,
        "message": message,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "turn_number": turn_number,
    })


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


# Base test fixtures
CATEGORY_DENTISTS = {
    "slug": "dentists",
    "offer_catalog": [
        {"title": "Dental Cleaning @ ₹299", "value": "299", "audience": "new_user"},
        {"title": "Deep Cleaning @ ₹499", "value": "499", "audience": "returning"},
    ],
    "voice": {
        "tone": "peer_clinical",
        "vocab_allowed": ["fluoride varnish", "caries"],
        "taboos": ["cure", "guaranteed"],
    },
    "peer_stats": {"avg_rating": 4.4, "avg_reviews": 62, "avg_ctr": 0.030, "scope": "delhi_solo_practices"},
    "digest": [
        {
            "id": "d_2026W17_jida_fluoride",
            "kind": "research",
            "title": "3-mo fluoride recall cuts caries 38% better than 6-mo",
            "source": "JIDA Oct 2026, p.14",
            "trial_n": 2100,
            "patient_segment": "high_risk_adults",
        }
    ],
    "seasonal_beats": [{"month_range": "Nov-Feb", "note": "exam-stress bruxism spike"}],
}

MERCHANT_MEERA = {
    "merchant_id": "m_001_drmeera",
    "category_slug": "dentists",
    "identity": {
        "name": "Dr. Meera's Dental Clinic",
        "city": "Delhi",
        "locality": "Lajpat Nagar",
        "verified": True,
        "languages": ["en", "hi"],
    },
    "subscription": {"status": "active", "plan": "Pro", "days_remaining": 82},
    "performance": {
        "window_days": 30,
        "views": 2410,
        "calls": 18,
        "directions": 45,
        "ctr": 0.021,
        "delta_7d": {"views_pct": 0.18, "calls_pct": -0.05},
    },
    "offers": [
        {"id": "o_meera_001", "title": "Dental Cleaning @ ₹299", "status": "active"},
        {"id": "o_meera_002", "title": "Deep Cleaning @ ₹499", "status": "expired"},
    ],
    "signals": ["stale_posts:22d", "ctr_below_peer_median", "high_risk_adult_cohort"],
}

CUSTOMER_PRIYA = {
    "customer_id": "c_001_priya",
    "merchant_id": "m_001_drmeera",
    "identity": {"name": "Priya", "phone_redacted": "<phone>", "language_pref": "hi-en mix"},
    "relationship": {
        "first_visit": "2025-11-04",
        "last_visit": "2026-05-12",
        "visits_total": 4,
        "services_received": ["cleaning", "cleaning", "whitening", "cleaning"],
    },
    "state": "lapsed_soft",
    "preferences": {"preferred_slots": "weekday_evening", "channel": "whatsapp"},
    "consent": {"opted_in_at": "2025-11-04", "scope": ["recall_reminders", "appointment_reminders"]},
}

NOW = "2026-04-26T10:30:00Z"


def seed_base():
    push_context("category", "dentists", 900, CATEGORY_DENTISTS)
    push_context("merchant", "m_001_drmeera", 900, MERCHANT_MEERA)
    push_context("customer", "c_001_priya", 900, CUSTOMER_PRIYA)


def test_01_fresh_trigger_kind():
    """Send trigger with unknown kind, verify grounded message."""
    push_context("trigger", "adapt_trg_unknown_kind", 1, {
        "id": "adapt_trg_unknown_kind",
        "scope": "merchant",
        "kind": "inventory_surplus_detected",
        "source": "internal",
        "merchant_id": "m_001_drmeera",
        "customer_id": None,
        "payload": {"surplus_slots": 12, "week": "2026-W18", "revenue_at_risk": "₹3,600"},
        "urgency": 3,
        "expires_at": "2026-05-10T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_unknown_kind"])
    check("Fresh trigger kind returns action", code == 200 and len(data.get("actions", [])) > 0)
    if data.get("actions"):
        action = data["actions"][0]
        check("Body mentions trigger-relevant facts",
              any(x in action.get("body", "").lower() for x in ["surplus", "12", "slot", "inventory"]),
              f"Body: {action.get('body', '')[:120]}")


def test_02_expired_trigger_filtered():
    """Expired trigger should be filtered out."""
    push_context("trigger", "adapt_trg_expired", 1, {
        "id": "adapt_trg_expired",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "merchant_id": "m_001_drmeera",
        "customer_id": None,
        "payload": {"top_item_id": "d_2026W17_jida_fluoride"},
        "urgency": 2,
        "expires_at": "2026-04-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_expired"])
    check("Expired trigger returns no actions", code == 200 and len(data.get("actions", [])) == 0)


def test_03_missing_merchant_context():
    """Trigger referencing non-existent merchant should be skipped."""
    push_context("trigger", "adapt_trg_ghost_merchant", 1, {
        "id": "adapt_trg_ghost_merchant",
        "scope": "merchant",
        "kind": "perf_dip",
        "source": "internal",
        "merchant_id": "m_nonexistent",
        "customer_id": None,
        "payload": {"metric": "calls", "delta_pct": -0.3, "window": "7d"},
        "urgency": 4,
        "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_ghost_merchant"])
    check("Missing merchant context returns no actions", code == 200 and len(data.get("actions", [])) == 0)


def test_04_duplicate_context_push_idempotent():
    """Re-posting same version should return 409 stale_version."""
    code, data = push_context("category", "dentists", 900, CATEGORY_DENTISTS)
    check("Duplicate version returns not accepted", code == 200 and data.get("accepted") == False,
          f"Got: accepted={data.get('accepted')}, reason={data.get('reason')}")


def test_05_higher_version_update():
    """Higher version should replace context."""
    updated_cat = dict(CATEGORY_DENTISTS)
    updated_cat["peer_stats"] = {"avg_ctr": 0.035}
    code, data = push_context("category", "dentists", 901, updated_cat)
    check("Higher version accepted", code == 200 and data.get("accepted") == True)
    code2, data2 = get("/v1/healthz")
    check("Healthz reflects category count", code2 == 200 and data2.get("contexts_loaded", {}).get("category", 0) >= 1)


def test_06_customer_scope_without_customer_context():
    """Customer-scope trigger without customer context should be skipped."""
    push_context("trigger", "adapt_trg_recall_no_customer", 1, {
        "id": "adapt_trg_recall_no_customer",
        "scope": "customer",
        "kind": "recall_due",
        "source": "internal",
        "merchant_id": "m_001_drmeera",
        "customer_id": "c_nonexistent",
        "payload": {},
        "urgency": 5,
        "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_recall_no_customer"])
    check("Customer scope without customer context returns no actions",
          code == 200 and len(data.get("actions", [])) == 0)


def test_07_taboo_word_sanitized():
    """Taboo words from category.voice.taboos should be filtered from output."""
    push_context("trigger", "adapt_trg_taboo_test", 1, {
        "id": "adapt_trg_taboo_test",
        "scope": "merchant",
        "kind": "perf_spike",
        "source": "internal",
        "merchant_id": "m_001_drmeera",
        "customer_id": None,
        "payload": {"metric": "calls", "delta_pct": 0.5, "window": "7d"},
        "urgency": 3,
        "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_taboo_test"])
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("Taboo word 'cure' not in body", "cure" not in body, f"Body contains 'cure'")
        check("Taboo word 'guaranteed' not in body", "guaranteed" not in body, f"Body contains 'guaranteed'")
    else:
        check("Taboo test produced action", False, "No actions returned")


def test_08_no_triggers_available():
    """Empty available_triggers should return empty actions."""
    code, data = tick(NOW, [])
    check("No triggers returns empty actions", code == 200 and len(data.get("actions", [])) == 0)


def test_09_multiple_triggers_priority_ordering():
    """Multiple triggers should be prioritized by urgency."""
    push_context("trigger", "adapt_trg_low", 1, {
        "id": "adapt_trg_low", "scope": "merchant", "kind": "curious_ask_due",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {}, "urgency": 1, "expires_at": "2026-06-01T00:00:00Z",
    })
    push_context("trigger", "adapt_trg_high", 1, {
        "id": "adapt_trg_high", "scope": "merchant", "kind": "perf_dip",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"metric": "calls", "delta_pct": -0.3, "window": "7d"},
        "urgency": 5, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_low", "adapt_trg_high"])
    if data.get("actions") and len(data["actions"]) >= 1:
        first_action = data["actions"][0]
        check("Highest urgency trigger sent first", first_action.get("trigger_id") == "adapt_trg_high",
              f"First trigger: {first_action.get('trigger_id')}")
    else:
        check("Multiple triggers produce actions", False, f"No actions: {data}")


def test_10_conversation_id_determinism():
    """Same input should produce same conversation_id across two ticks."""
    push_context("trigger", "adapt_trg_determinism", 1, {
        "id": "adapt_trg_determinism", "scope": "merchant", "kind": "milestone_reached",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {}, "urgency": 2, "expires_at": "2026-06-01T00:00:00Z",
    })
    code1, data1 = tick(NOW, ["adapt_trg_determinism"])
    conv_id_1 = data1["actions"][0].get("conversation_id") if data1.get("actions") else None

    push_context("trigger", "adapt_trg_determinism2", 1, {
        "id": "adapt_trg_determinism2", "scope": "merchant", "kind": "milestone_reached",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {}, "urgency": 2, "expires_at": "2026-06-01T00:00:00Z",
    })
    code2, data2 = tick(NOW, ["adapt_trg_determinism2"])
    conv_id_2 = data2["actions"][0].get("conversation_id") if data2.get("actions") else None

    if conv_id_1 and conv_id_2:
        expected_1 = "conv:m_001_drmeera:adapt_trg_determinism"
        expected_2 = "conv:m_001_drmeera:adapt_trg_determinism2"
        check("Conversation ID format is deterministic (conv:merchant:trigger)",
              conv_id_1 == expected_1 and conv_id_2 == expected_2,
              f"conv1={conv_id_1} (expected {expected_1}), conv2={conv_id_2} (expected {expected_2})")
    else:
        check("Determinism test produced actions on both ticks", False,
              f"conv1={conv_id_1}, conv2={conv_id_2}")


def test_11_auto_reply_hell():
    """4 identical replies should end conversation."""
    push_context("trigger", "adapt_trg_autoreply", 1, {
        "id": "adapt_trg_autoreply", "scope": "merchant", "kind": "research_digest",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"top_item_id": "d_2026W17_jida_fluoride"},
        "urgency": 2, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_autoreply"])
    if data.get("actions"):
        conv_id = data["actions"][0]["conversation_id"]
        auto_msg = "Thanks for your message. We'll get back to you soon."
        for i in range(4):
            code, reply_data = reply(conv_id, "m_001_drmeera", "merchant", auto_msg, i + 2)
        check("Auto-reply hell ends conversation", reply_data.get("action") == "end",
              f"Action: {reply_data.get('action')}")
    else:
        check("Auto-reply test produced action to reply to", False)


def test_12_hostile_message_ends():
    """Hostile message should end conversation."""
    push_context("trigger", "adapt_trg_hostile", 1, {
        "id": "adapt_trg_hostile", "scope": "merchant", "kind": "research_digest",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"top_item_id": "d_2026W17_jida_fluoride"},
        "urgency": 2, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_hostile"])
    if data.get("actions"):
        conv_id = data["actions"][0]["conversation_id"]
        code, reply_data = reply(conv_id, "m_001_drmeera", "merchant", "This is spam! Unsubscribe me now.", 2)
        check("Hostile message ends conversation", reply_data.get("action") == "end",
              f"Action: {reply_data.get('action')}")
    else:
        check("Hostile test produced action to reply to", False)


def test_13_objection_repositioning():
    """Budget objection should reframe with free options."""
    push_context("trigger", "adapt_trg_objection", 1, {
        "id": "adapt_trg_objection", "scope": "merchant", "kind": "research_digest",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"top_item_id": "d_2026W17_jida_fluoride"},
        "urgency": 2, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_objection"])
    if data.get("actions"):
        conv_id = data["actions"][0]["conversation_id"]
        code, reply_data = reply(conv_id, "m_001_drmeera", "merchant", "I don't have budget for this right now", 2)
        body = reply_data.get("body", "").lower()
        check("Objection repositioned (not ended)", reply_data.get("action") == "send",
              f"Action: {reply_data.get('action')}")
        check("Body addresses budget concern",
              any(x in body for x in ["budget", "free", "cost", "spend", "samajh"]),
              f"Body: {reply_data.get('body', '')[:120]}")
    else:
        check("Objection test produced action to reply to", False)


def test_14_commitment_transition():
    """'Let's do it' should switch to action, not ask more questions."""
    push_context("trigger", "adapt_trg_commitment", 1, {
        "id": "adapt_trg_commitment", "scope": "merchant", "kind": "active_planning_intent",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {}, "urgency": 3, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_commitment"])
    if data.get("actions"):
        conv_id = data["actions"][0]["conversation_id"]
        code, reply_data = reply(conv_id, "m_001_drmeera", "merchant", "ok let's do it", 2)
        body = reply_data.get("body", "").lower()
        check("Commitment returns send action", reply_data.get("action") == "send",
              f"Action: {reply_data.get('action')}")
        check("Body has next steps / action plan",
              any(x in body for x in ["next step", "draft", "share", "shuru", "done"]),
              f"Body: {reply_data.get('body', '')[:120]}")
    else:
        check("Commitment test produced action to reply to", False)


def test_15_metadata_truthfulness():
    """Metadata should show Algsoch AI identity."""
    code, data = get("/v1/metadata")
    check("Metadata returns 200", code == 200)
    check("Team name is Algsoch AI", data.get("team_name") == "Algsoch AI",
          f"Got: {data.get('team_name')}")
    check("Contact email is not placeholder",
          data.get("contact_email") not in [None, "team@magicpin.ai", "team@example.com"],
          f"Got: {data.get('contact_email')}")


if __name__ == "__main__":
    print(f"Adversarial Magicpin Probe Tests — {BOT_URL}")
    print("=" * 60)

    print("\nSeeding base contexts...")
    seed_base()

    tests = [
        test_01_fresh_trigger_kind,
        test_02_expired_trigger_filtered,
        test_03_missing_merchant_context,
        test_04_duplicate_context_push_idempotent,
        test_05_higher_version_update,
        test_06_customer_scope_without_customer_context,
        test_07_taboo_word_sanitized,
        test_08_no_triggers_available,
        test_09_multiple_triggers_priority_ordering,
        test_10_conversation_id_determinism,
        test_11_auto_reply_hell,
        test_12_hostile_message_ends,
        test_13_objection_repositioning,
        test_14_commitment_transition,
        test_15_metadata_truthfulness,
    ]

    for test_fn in tests:
        print(f"\n--- {test_fn.__doc__.strip()} ---")
        try:
            test_fn()
        except Exception as e:
            TOTAL += 1
            FAIL += 1
            print(f"  [FAIL] {test_fn.__name__} — Exception: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS}/{TOTAL} passed, {FAIL} failed")
    if FAIL == 0:
        print("All tests passed! Bot is judge-ready.")
    else:
        print(f"{FAIL} test(s) failed. Review failures above.")
    sys.exit(0 if FAIL == 0 else 1)
