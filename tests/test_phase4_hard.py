#!/usr/bin/env python3
"""
Phase 4 Hard Adversarial Tests — 33 proof tests
=================================================

Tests edge cases the judge will throw at the bot:
- Unicode/Devanagari encoding, emoji, null bytes
- Malformed inputs, missing fields, wrong types
- State leakage between test runs
- Near-expiry triggers (within 1 second)
- Version edge cases (v0, huge versions, negative)
- Suppression key deduplication
- Empty merchant identities
- Multi-merchant, multi-category isolation
- Conversation state across turns
- Timezone edge cases
- Large payloads
- Reply with unknown conversation IDs
- Cross-conversation interference
- Trigger with missing payload
- Customer with minimal/consent-revoked data
- Sequential replay: tick → reply → tick → reply patterns

Usage:
    python tests/test_phase4_hard.py [BOT_URL]

Default BOT_URL: http://localhost:8001
"""

import sys
import json
import time
import ssl
import http.client
from datetime import datetime, timezone
from urllib import parse

BOT_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"

PASS = 0
FAIL = 0
TOTAL = 0

# Parse base URL
_parsed = parse.urlparse(BOT_URL)
_IS_HTTPS = _parsed.scheme == "https"
_HOST = _parsed.hostname
_PORT = _parsed.port or (443 if _IS_HTTPS else 80)
_BASE = _parsed.path.rstrip("/")

_TLS_CTX = None
if _IS_HTTPS:
    _TLS_CTX = ssl.create_default_context()
    _TLS_CTX.maximum_version = ssl.TLSVersion.TLSv1_2

# Unique prefix per test run to avoid state collision across runs
_RUN = int(time.time()) % 100000

def _id(base: str) -> str:
    return f"h{_RUN}_{base}"


def _req(method, path, body=None, retries=3):
    full_path = f"{_BASE}{path}" if not path.startswith(_BASE) else path
    data = json.dumps(body).encode("utf-8") if body else None
    headers = {"Content-Type": "application/json"}
    if data:
        headers["Content-Length"] = str(len(data))
    for attempt in range(retries):
        try:
            if _IS_HTTPS:
                conn = http.client.HTTPSConnection(_HOST, _PORT, timeout=30, context=_TLS_CTX)
            else:
                conn = http.client.HTTPConnection(_HOST, _PORT, timeout=30)
            conn.request(method, full_path, body=data, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            conn.close()
            return resp.status, json.loads(raw) if raw else {}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
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


NOW = "2026-04-26T10:30:00Z"

# ── Base fixtures ──

def make_cat(slug="dentists", taboos=None):
    return {
        "slug": slug,
        "offer_catalog": [{"title": "Dental Cleaning @ ₹299", "value": "299", "audience": "new_user"}],
        "voice": {"tone": "peer_clinical", "taboos": taboos or ["cure", "guaranteed"]},
        "peer_stats": {"avg_rating": 4.4, "avg_reviews": 62, "avg_ctr": 0.030, "scope": "delhi_solo_practices"},
        "digest": [{"id": "d_001", "kind": "research", "title": "Fluoride study", "source": "JIDA 2026"}],
        "seasonal_beats": [{"month_range": "Nov-Feb", "note": "bruxism spike"}],
    }


def make_merchant(mid="h_m", name="Dr. Test Clinic", city="Delhi", locality="CP", cat_slug="dentists", offers=None, signals=None, perf=None):
    return {
        "merchant_id": mid,
        "category_slug": cat_slug,
        "identity": {"name": name, "city": city, "locality": locality, "languages": ["en", "hi"], "verified": True},
        "subscription": {"status": "active", "plan": "Pro", "days_remaining": 82},
        "performance": perf or {"window_days": 30, "views": 2410, "calls": 18, "directions": 45, "ctr": 0.021},
        "offers": offers or [{"id": "o_001", "title": "Dental Cleaning @ ₹299", "status": "active"}],
        "signals": signals or ["stale_posts:22d"],
    }


def make_trigger(tid, kind, mid, urgency=2, payload=None, scope="merchant", expires="2026-06-01T00:00:00Z"):
    return {
        "id": tid, "scope": scope, "kind": kind,
        "merchant_id": mid, "customer_id": None,
        "payload": payload or {},
        "urgency": urgency, "expires_at": expires,
    }


def make_customer(cid, mid, name="Test", lang="en", state="lapsed_soft"):
    return {
        "customer_id": cid,
        "merchant_id": mid,
        "identity": {"name": name, "language_pref": lang},
        "relationship": {"first_visit": "2025-06-01", "last_visit": "2026-01-15", "visits_total": 2, "services_received": ["cleaning"]},
        "state": state,
        "consent": {"opted_in_at": "2025-06-01", "scope": ["recall_reminders"]},
    }


def seed_base():
    # Category context_id MUST match merchant's category_slug for lookup to work
    push_context("category", "dentists", 60000 + _RUN, make_cat("dentists"))
    m_id = _id("m_001")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    return "dentists", m_id


def tick_for(mid, trigger_ids):
    return tick(NOW, trigger_ids)


def do_tick_and_reply(mid, kind, payload=None, replies=None):
    """Helper: push merchant + trigger, tick, then replay a sequence of replies."""
    # Use full mid hash to avoid collision (m_hindi vs m_hinglish)
    import hashlib
    mid_hash = hashlib.md5(mid.encode()).hexdigest()[:8]
    tid = _id(f"trg_{kind}_{mid_hash}")
    push_context("merchant", mid, 1, make_merchant(mid, cat_slug="dentists"))
    push_context("trigger", tid, 1, make_trigger(tid, kind, mid, payload=payload))
    code, data = tick_for(mid, [tid])
    if not data.get("actions"):
        return None, []
    conv_id = data["actions"][0]["conversation_id"]
    results = []
    for i, msg in enumerate(replies or []):
        code2, r2 = reply(conv_id, mid, "merchant", msg, i + 2)
        results.append(r2)
    return data["actions"][0], results


# ── Tests ──


def test_01_unicode_merchant_name():
    """Merchant with Hindi/Unicode name should compose readable message."""
    m_id = _id("m_unicode")
    tid = _id("trg_unicode")
    push_context("category", "dentists", 60001 + _RUN, make_cat("dentists"))
    push_context("merchant", m_id, 1, make_merchant(m_id, name="डॉ. राम क्लिनिक", city="Mumbai", locality="Andheri", cat_slug="dentists"))
    push_context("trigger", tid, 1, make_trigger(tid, "research_digest", m_id, payload={"top_item_id": "d_001"}))
    code, data = tick_for(m_id, [tid])
    check("Unicode merchant produces action", code == 200 and data.get("actions"))


def test_02_emoji_in_trigger_payload():
    """Trigger with emoji in payload should not crash composition."""
    m_id = _id("m_emoji")
    tid = _id("trg_emoji")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("trigger", tid, 1, make_trigger(tid, "festival_upcoming", m_id, payload={"event": "🎉 Diwali 🪔", "days_away": 14}))
    code, data = tick_for(m_id, [tid])
    check("Emoji in payload produces action", code == 200 and data.get("actions"))


def test_03_empty_merchant_identity():
    """Merchant with minimal/empty identity should still compose."""
    m_id = _id("m_empty")
    tid = _id("trg_empty")
    push_context("merchant", m_id, 1, {
        "merchant_id": m_id, "category_slug": "dentists",
        "identity": {"name": "", "city": "", "locality": "", "languages": []},
        "subscription": {"status": "active", "plan": "Basic", "days_remaining": 1},
        "performance": {}, "offers": [], "signals": [],
    })
    push_context("trigger", tid, 1, make_trigger(tid, "perf_dip", m_id, urgency=5, payload={"metric": "views", "delta_pct": -0.5, "window": "7d"}))
    code, data = tick_for(m_id, [tid])
    check("Empty identity merchant produces action", code == 200 and data.get("actions"))


def test_04_trigger_missing_payload():
    """Trigger with empty payload dict should fall back gracefully."""
    m_id = _id("m_nopayload")
    tid = _id("trg_nopayload")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("trigger", tid, 1, make_trigger(tid, "competitor_opened", m_id, payload={}))
    code, data = tick_for(m_id, [tid])
    check("Empty payload produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("Body has generic competitor fallback",
              any(x in body for x in ["competitor", "update", "ahead", "offer"]),
              f"Body: {data['actions'][0].get('body', '')[:120]}")


def test_05_near_expiry_trigger():
    """Trigger expiring 1 second from now should still fire."""
    m_id = _id("m_nearexpiry")
    tid = _id("trg_nearexpiry")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("trigger", tid, 1, {
        "id": tid, "scope": "merchant", "kind": "milestone_reached",
        "merchant_id": m_id, "customer_id": None,
        "payload": {"milestone": "100_reviews"},
        "urgency": 1, "expires_at": "2026-04-26T10:30:01Z",
    })
    code, data = tick("2026-04-26T10:30:00Z", [tid])
    check("Near-expiry trigger (1s before) fires", code == 200 and data.get("actions"))


def test_06_expired_trigger_1s_ago():
    """Trigger expired 1 second ago should be filtered."""
    m_id = _id("m_expired")
    tid = _id("trg_expired")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("trigger", tid, 1, {
        "id": tid, "scope": "merchant", "kind": "milestone_reached",
        "merchant_id": m_id, "customer_id": None,
        "payload": {},
        "urgency": 5, "expires_at": "2026-04-26T10:29:59Z",
    })
    code, data = tick("2026-04-26T10:30:00Z", [tid])
    check("1s-expired trigger filtered", code == 200 and len(data.get("actions", [])) == 0)


def test_07_huge_version_number():
    """Context with very large version number should be accepted."""
    code, data = push_context("category", _id("cat_huge"), 999999999, make_cat("dentists"))
    check("Huge version accepted", code == 200 and data.get("accepted") == True)


def test_08_version_zero():
    """Context with version 0 should be rejected (current is 0 for new keys)."""
    code, data = push_context("category", _id("cat_zero"), 0, {"slug": "zero_test"})
    check("Version 0 rejected (same as default)", code == 200 and data.get("accepted") == False)


def test_09_suppression_key_dedup():
    """Same suppression key across two ticks → second should be deduped."""
    m_id = _id("m_dedup")
    tid = _id("trg_dedup")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("trigger", tid, 1, make_trigger(tid, "research_digest", m_id, payload={"top_item_id": "d_001"}))

    code1, data1 = tick_for(m_id, [tid])
    check("First tick produces action", code1 == 200 and data1.get("actions"))

    code2, data2 = tick_for(m_id, [tid])
    check("Second tick deduped (no action)", code2 == 200 and not data2.get("actions"))


def test_10_multi_merchant_isolation():
    """Two merchants, each with own triggers → no cross-contamination."""
    ma = _id("m_iso_a")
    mb = _id("m_iso_b")
    ta = _id("trg_iso_a")
    tb = _id("trg_iso_b")

    push_context("merchant", ma, 1, make_merchant(ma, name="Clinic A", city="Delhi", locality="CP", cat_slug="dentists"))
    push_context("merchant", mb, 1, make_merchant(mb, name="Clinic B", city="Mumbai", locality="Bandra", cat_slug="dentists"))
    push_context("trigger", ta, 1, make_trigger(ta, "perf_spike", ma, payload={"metric": "views", "delta_pct": 0.5, "window": "7d"}))
    push_context("trigger", tb, 1, make_trigger(tb, "perf_spike", mb, payload={"metric": "calls", "delta_pct": 0.3, "window": "7d"}))

    code_a, data_a = tick_for(ma, [ta])
    code_b, data_b = tick_for(mb, [tb])

    check("Merchant A trigger produces action", code_a == 200 and data_a.get("actions"))
    check("Merchant B trigger produces action", code_b == 200 and data_b.get("actions"))

    if data_a.get("actions") and data_b.get("actions"):
        body_a = data_a["actions"][0].get("body", "")
        body_b = data_b["actions"][0].get("body", "")
        check("Merchant A message references Clinic A",
              "Clinic A" in body_a or "Delhi" in body_a or "CP" in body_a,
              f"Body A: {body_a[:80]}")
        check("Merchant B message references Clinic B",
              "Clinic B" in body_b or "Mumbai" in body_b or "Bandra" in body_b,
              f"Body B: {body_b[:80]}")


def test_11_large_category_payload():
    """Category with 50+ digest items should not crash."""
    m_id = _id("m_large")
    tid = _id("trg_large")
    big_cat = make_cat("dentists")
    big_cat["digest"] = [{"id": f"d_{i}", "kind": "research", "title": f"Study #{i}", "source": f"Journal {i}"} for i in range(50)]
    push_context("category", "dentists", 60002 + _RUN, big_cat)
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("trigger", tid, 1, make_trigger(tid, "research_digest", m_id, payload={"top_item_id": "d_25"}))
    code, data = tick_for(m_id, [tid])
    check("Large category produces action", code == 200 and data.get("actions"))


def test_12_conversation_unknown_id_reply():
    """Reply to unknown conversation ID should create conversation and respond."""
    m_id = _id("m_unknown")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("trigger", _id("trg_unknown"), 1, make_trigger(_id("trg_unknown"), "research_digest", m_id))
    code, data = reply("conv:unknown:trg", m_id, "merchant", "Hello, what's new?", 1)
    check("Unknown conv_id creates conversation", code == 200 and data.get("action") == "send",
          f"Action: {data.get('action')}")


def test_13_conversation_state_preserved():
    """Multi-turn conversation should preserve state across turns."""
    m_id = _id("m_state")
    action, results = do_tick_and_reply(m_id, "curious_ask_due",
        payload={"question_topic": "offers"},
        replies=[
            "What are my current offers?",
            "yes please",
            "I don't have budget",
        ])
    check("Statetest tick produces action", action is not None)
    if results:
        check("Turn 1: offer query returns send", results[0].get("action") == "send", f"Action: {results[0].get('action')}")
        check("Turn 1: body mentions offers",
              "offer" in results[0].get("body", "").lower(),
              f"Body: {results[0].get('body', '')[:80]}")
    if len(results) >= 2:
        check("Turn 2: yes returns send", results[1].get("action") == "send", f"Action: {results[1].get('action')}")
    if len(results) >= 3:
        check("Turn 3: budget objection returns send (not end)",
              results[2].get("action") == "send", f"Action: {results[2].get('action')}")
        check("Turn 3: body addresses budget",
              any(x in results[2].get("body", "").lower() for x in ["budget", "free", "cost"]),
              f"Body: {results[2].get('body', '')[:80]}")


def test_14_hindi_reply_routing():
    """Hindi/Devanagari reply should route through Hindi handlers."""
    m_id = _id("m_hindi")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["मुझे और जानकारी चाहिए"])
    check("Hindi reply test setup produces action", action is not None)
    if results:
        check("Hindi message returns send", results[0].get("action") == "send", f"Action: {results[0].get('action')}")


def test_15_hinglish_reply_routing():
    """Hinglish reply should route through Hindi handlers."""
    m_id = _id("m_hinglish")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["kya hai meri offers?"])
    check("Hinglish reply test setup produces action", action is not None)
    if results:
        check("Hinglish message returns send", results[0].get("action") == "send", f"Action: {results[0].get('action')}")


def test_16_disinterest_ends_conversation():
    """'Not interested' reply should end conversation."""
    m_id = _id("m_disinterest")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["I'm not interested in this"])
    if results:
        check("Not interested ends conversation", results[0].get("action") == "end", f"Action: {results[0].get('action')}")
    else:
        check("Disinterest test produced action", False)


def test_17_later_request_returns_wait():
    """'Busy, call later' reply should return wait action."""
    m_id = _id("m_later")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["I'm busy right now, call me later"])
    if results:
        check("Later request returns wait", results[0].get("action") == "wait", f"Action: {results[0].get('action')}")
        check("Wait has wait_seconds", results[0].get("wait_seconds") is not None, f"wait_seconds: {results[0].get('wait_seconds')}")
    else:
        check("Later test produced action", False)


def test_18_no_reply_returns_wait():
    """'no' reply should return wait action with backoff."""
    m_id = _id("m_no")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["no"])
    if results:
        check("No returns wait", results[0].get("action") == "wait", f"Action: {results[0].get('action')}")
        check("No has wait_seconds", results[0].get("wait_seconds") is not None, f"wait_seconds: {results[0].get('wait_seconds')}")
    else:
        check("No reply test produced action", False)


def test_19_offers_query_routing():
    """'Show me offers' should route to offers handler."""
    m_id = _id("m_offers_q")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["What are my current offers?"])
    if results:
        check("Offers query returns send", results[0].get("action") == "send", f"Action: {results[0].get('action')}")
        check("Body mentions offers",
              "offer" in results[0].get("body", "").lower(),
              f"Body: {results[0].get('body', '')[:80]}")
    else:
        check("Offers query test produced action", False)


def test_20_performance_query_routing():
    """'How am I doing' should route to performance handler."""
    m_id = _id("m_perf_q")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["How am I doing?"])
    if results:
        check("Perf query returns send", results[0].get("action") == "send", f"Action: {results[0].get('action')}")
        body = results[0].get("body", "").lower()
        check("Body mentions performance metrics",
              any(x in body for x in ["views", "calls", "ctr", "snapshot", "performance"]),
              f"Body: {results[0].get('body', '')[:80]}")
    else:
        check("Perf query test produced action", False)


def test_21_greeting_routing():
    """'Hi' should route to greeting handler."""
    m_id = _id("m_greet")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["Hi, what's new?"])
    if results:
        check("Greeting returns send", results[0].get("action") == "send", f"Action: {results[0].get('action')}")
    else:
        check("Greeting test produced action", False)


def test_22_profile_query_routing():
    """'Check my profile' should route to profile handler."""
    m_id = _id("m_profile")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["What's my Google profile status?"])
    if results:
        check("Profile query returns send", results[0].get("action") == "send", f"Action: {results[0].get('action')}")
        check("Body mentions profile/verified",
              any(x in results[0].get("body", "").lower() for x in ["profile", "verified", "google", "audit"]),
              f"Body: {results[0].get('body', '')[:80]}")
    else:
        check("Profile test produced action", False)


def test_23_full_replay_sequence():
    """Full judge replay: tick → reply(yes) → reply(budget) → reply(let's do it)."""
    m_id = _id("m_replay")
    action, results = do_tick_and_reply(m_id, "competitor_opened",
        payload={"competitor_name": "Rival Clinic", "distance_km": 0.5, "their_offer": "Free checkup"},
        replies=["yes", "I can't afford this", "ok let's do it"])
    check("Full replay tick produces action", action is not None)
    if len(results) >= 1:
        check("Replay yes → send", results[0].get("action") == "send", f"Action: {results[0].get('action')}")
    if len(results) >= 2:
        check("Replay budget → send (reframe)", results[1].get("action") == "send", f"Action: {results[1].get('action')}")
    if len(results) >= 3:
        check("Replay commitment → send with plan", results[2].get("action") == "send", f"Action: {results[2].get('action')}")
        check("Commitment body has action plan",
              any(x in results[2].get("body", "").lower() for x in ["draft", "next", "step", "shuru"]),
              f"Body: {results[2].get('body', '')[:80]}")


def test_24_off_topic_deflection():
    """GST/tax question should deflect politely."""
    m_id = _id("m_gst")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["How do I file my GST return?"])
    if results:
        check("GST question deflects", results[0].get("action") == "send", f"Action: {results[0].get('action')}")
        body = results[0].get("body", "").lower()
        check("Body deflects GST question",
              any(x in body for x in ["ca", "focus", "listing", "profile", "tax"]),
              f"Body: {results[0].get('body', '')[:80]}")
    else:
        check("GST test produced action", False)


def test_25_customer_minimal_consent():
    """Customer with only recall_reminders consent should only get recall messages."""
    m_id = _id("m_cust_min")
    cid = _id("c_minimal")
    tid = _id("trg_cust_min")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("customer", cid, 1, make_customer(cid, m_id, name="Sunita"))
    push_context("trigger", tid, 1, {
        "id": tid, "scope": "customer", "kind": "recall_due",
        "merchant_id": m_id, "customer_id": cid,
        "payload": {}, "urgency": 4, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick_for(m_id, [tid])
    check("Minimal consent customer produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Customer-facing message addresses customer",
              "Sunita" in body,
              f"Body: {body[:80]}")
        check("Customer message uses merchant_on_behalf",
              data["actions"][0].get("send_as") == "merchant_on_behalf",
              f"send_as: {data['actions'][0].get('send_as')}")


def test_26_multiple_triggers_max_5():
    """7 triggers → max 5 actions returned."""
    m_id = _id("m_multi7")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    tids = []
    for i in range(7):
        tid = _id(f"trg_multi7_{i}")
        tids.append(tid)
        push_context("trigger", tid, 1, make_trigger(tid, "research_digest", m_id, urgency=i+1, payload={"top_item_id": "d_001"}))
    code, data = tick_for(m_id, tids)
    check("Max 5 actions returned", code == 200 and len(data.get("actions", [])) <= 5,
          f"Got {len(data.get('actions', []))} actions")
    check("At least 1 action returned", code == 200 and len(data.get("actions", [])) >= 1)


def test_27_conversation_id_format_all_cases():
    """Verify conversation_id format for merchant, customer, and mixed scopes."""
    m_id = _id("m_convfmt")
    tid_m = _id("trg_convfmt_m")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("trigger", tid_m, 1, make_trigger(tid_m, "milestone_reached", m_id, urgency=1, payload={}))
    code1, data1 = tick_for(m_id, [tid_m])
    if data1.get("actions"):
        cid1 = data1["actions"][0].get("conversation_id", "")
        check("Merchant conv_id format: conv:merchant:trigger",
              cid1 == f"conv:{m_id}:{tid_m}",
              f"Got: {cid1}")

    # Customer scope
    cid_c = _id("c_convfmt")
    tid_c = _id("trg_convfmt_c")
    push_context("customer", cid_c, 1, make_customer(cid_c, m_id, name="Test"))
    push_context("trigger", tid_c, 1, {
        "id": tid_c, "scope": "customer", "kind": "recall_due",
        "merchant_id": m_id, "customer_id": cid_c,
        "payload": {}, "urgency": 1, "expires_at": "2026-06-01T00:00:00Z",
    })
    code2, data2 = tick_for(m_id, [tid_c])
    if data2.get("actions"):
        cid2 = data2["actions"][0].get("conversation_id", "")
        check("Customer conv_id format: conv:merchant:trigger:customer",
              cid2 == f"conv:{m_id}:{tid_c}:{cid_c}",
              f"Got: {cid2}")


def test_28_tick_empty_triggers():
    """Tick with empty available_triggers should return empty actions."""
    code, data = tick(NOW, [])
    check("Empty triggers returns empty actions", code == 200 and data.get("actions") == [])


def test_29_tick_nonexistent_triggers():
    """Tick with nonexistent trigger IDs should return empty actions."""
    code, data = tick(NOW, [_id("trg_ghost_1"), _id("trg_ghost_2")])
    check("Nonexistent triggers returns empty actions", code == 200 and data.get("actions") == [])


def test_30_version_bump_mid_conversation():
    """Version bump merchant context mid-conversation → reply uses new data."""
    m_id = _id("m_versioned")
    tid = _id("trg_versioned")
    push_context("merchant", m_id, 1, {
        "merchant_id": m_id, "category_slug": "dentists",
        "identity": {"name": "Old Clinic", "city": "Delhi", "locality": "CP", "languages": ["en"]},
        "subscription": {"status": "active", "plan": "Basic", "days_remaining": 30},
        "performance": {"views": 100, "calls": 5, "ctr": 0.01},
        "offers": [{"id": "o_old", "title": "Old Offer @ ₹100", "status": "active"}],
        "signals": [],
    })
    push_context("trigger", tid, 1, make_trigger(tid, "curious_ask_due", m_id, payload={"question_topic": "offers"}))
    code, data = tick_for(m_id, [tid])
    check("Versioned tick produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        conv_id = data["actions"][0]["conversation_id"]
        # Bump merchant context with new offers
        push_context("merchant", m_id, 2, {
            "merchant_id": m_id, "category_slug": "dentists",
            "identity": {"name": "New Clinic", "city": "Delhi", "locality": "CP", "languages": ["en"]},
            "subscription": {"status": "active", "plan": "Pro", "days_remaining": 90},
            "performance": {"views": 500, "calls": 25, "ctr": 0.04},
            "offers": [{"id": "o_new", "title": "Premium Offer @ ₹999", "status": "active"}],
            "signals": ["growing"],
        })
        code2, r2 = reply(conv_id, m_id, "merchant", "yes", 2)
        check("Versioned reply returns send", r2.get("action") == "send", f"Action: {r2.get('action')}")
        body = r2.get("body", "").lower()
        check("Reply uses new data (new offer/premium/999)",
              any(x in body for x in ["premium", "999", "new", "growing"]),
              f"Body: {r2.get('body', '')[:80]}")


def test_31_taboo_in_unseen_trigger_kind():
    """Taboo words should be filtered even in unknown trigger kinds."""
    m_id = _id("m_taboo")
    tid = _id("trg_taboo")
    push_context("category", "dermatologists", 50002, make_cat("dermatologists", taboos=["permanent cure", "miracle", "100%"]))
    push_context("merchant", m_id, 1, make_merchant(m_id, name="SkinCare Clinic", city="Mumbai", locality="Bandra", cat_slug="dermatologists"))
    push_context("trigger", tid, 1, make_trigger(tid, "unknown_strange_event", m_id, payload={"event": "permanent cure miracle found", "detail": "100% effective"}))
    code, data = tick_for(m_id, [tid])
    check("Unknown trigger with taboos produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("'permanent cure' filtered from body", "permanent cure" not in body, f"Body: {body[:120]}")
        check("'miracle' filtered from body", "miracle" not in body, f"Body: {body[:120]}")
        check("'100%' filtered from body", "100%" not in body, f"Body: {body[:120]}")


def test_32_urgency_priority_ordering():
    """Triggers sorted by urgency*highest first, then by version."""
    m_id = _id("m_priority")
    tl = _id("trg_urg_low")
    tm = _id("trg_urg_med")
    th = _id("trg_urg_high")
    push_context("merchant", m_id, 1, make_merchant(m_id, cat_slug="dentists"))
    push_context("trigger", tl, 1, make_trigger(tl, "curious_ask_due", m_id, urgency=1, payload={}))
    push_context("trigger", tm, 1, make_trigger(tm, "competitor_opened", m_id, urgency=3, payload={"competitor_name": "Rival", "distance_km": 1}))
    push_context("trigger", th, 1, make_trigger(th, "perf_dip", m_id, urgency=5, payload={"metric": "calls", "delta_pct": -0.5, "window": "7d"}))
    code, data = tick_for(m_id, [tl, tm, th])
    if data.get("actions") and len(data["actions"]) >= 2:
        first = data["actions"][0].get("trigger_id")
        second = data["actions"][1].get("trigger_id")
        check("Highest urgency (5) sent first", first == th, f"First: {first}")
        check("Medium urgency (3) sent second", second == tm, f"Second: {second}")
    else:
        check("Priority test produced enough actions", False, f"Got {len(data.get('actions', []))} actions")


def test_33_review_query_routing():
    """'What are people saying' should route to review handler."""
    m_id = _id("m_review")
    action, results = do_tick_and_reply(m_id, "research_digest",
        payload={"top_item_id": "d_001"},
        replies=["What are people saying in reviews?"])
    if results:
        check("Review query returns send", results[0].get("action") == "send", f"Action: {results[0].get('action')}")
    else:
        check("Review test produced action", False)


if __name__ == "__main__":
    print(f"Phase 4 Hard Adversarial Tests — {BOT_URL}")
    print("=" * 60)

    print("\nSeeding base contexts...")
    seed_base()

    tests = [
        test_01_unicode_merchant_name,
        test_02_emoji_in_trigger_payload,
        test_03_empty_merchant_identity,
        test_04_trigger_missing_payload,
        test_05_near_expiry_trigger,
        test_06_expired_trigger_1s_ago,
        test_07_huge_version_number,
        test_08_version_zero,
        test_09_suppression_key_dedup,
        test_10_multi_merchant_isolation,
        test_11_large_category_payload,
        test_12_conversation_unknown_id_reply,
        test_13_conversation_state_preserved,
        test_14_hindi_reply_routing,
        test_15_hinglish_reply_routing,
        test_16_disinterest_ends_conversation,
        test_17_later_request_returns_wait,
        test_18_no_reply_returns_wait,
        test_19_offers_query_routing,
        test_20_performance_query_routing,
        test_21_greeting_routing,
        test_22_profile_query_routing,
        test_23_full_replay_sequence,
        test_24_off_topic_deflection,
        test_25_customer_minimal_consent,
        test_26_multiple_triggers_max_5,
        test_27_conversation_id_format_all_cases,
        test_28_tick_empty_triggers,
        test_29_tick_nonexistent_triggers,
        test_30_version_bump_mid_conversation,
        test_31_taboo_in_unseen_trigger_kind,
        test_32_urgency_priority_ordering,
        test_33_review_query_routing,
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
    if FAIL == 0:
        print("All tests passed! Bot handles hard adversarial cases correctly.")
    else:
        print(f"{FAIL} test(s) failed. Review failures above.")
    sys.exit(0 if FAIL == 0 else 1)
