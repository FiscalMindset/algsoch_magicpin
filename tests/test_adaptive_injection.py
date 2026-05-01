#!/usr/bin/env python3
"""
Phase 3 Adaptive Context Injection Tests — 12 proof tests
==========================================================

Simulates the judge's mid-test context injection behavior:
- New digest items (version bumps on category contexts)
- Updated performance snapshots (spikes, dips)
- New triggers with unseen kinds
- New customer contexts + recall_due triggers
- Cross-context consistency (bot must use NEW data, not stale)

Usage:
    python tests/test_adaptive_injection.py [BOT_URL]

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

# Parse base URL once
_parsed = parse.urlparse(BOT_URL)
_IS_HTTPS = _parsed.scheme == "https"
_HOST = _parsed.hostname
_PORT = _parsed.port or (443 if _IS_HTTPS else 80)
_BASE = _parsed.path.rstrip("/")

_TLS_CTX = None
if _IS_HTTPS:
    _TLS_CTX = ssl.create_default_context()
    _TLS_CTX.maximum_version = ssl.TLSVersion.TLSv1_2


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

BASE_CATEGORY = {
    "slug": "dentists",
    "offer_catalog": [{"title": "Dental Cleaning @ ₹299", "value": "299", "audience": "new_user", "status": "active"}],
    "voice": {"tone": "peer_clinical", "taboos": ["cure", "guaranteed"]},
    "peer_stats": {"avg_rating": 4.4, "avg_reviews": 62, "avg_ctr": 0.030, "scope": "delhi_solo_practices"},
    "digest": [
        {"id": "d_001", "kind": "research", "title": "Fluoride recall study", "source": "JIDA Oct 2026", "trial_n": 2100, "patient_segment": "high_risk_adults"}
    ],
    "seasonal_beats": [{"month_range": "Nov-Feb", "note": "exam-stress bruxism spike"}],
}

BASE_MERCHANT = {
    "merchant_id": "m_001_drmeera",
    "category_slug": "dentists",
    "identity": {"name": "Dr. Meera's Dental Clinic", "city": "Delhi", "locality": "Lajpat Nagar", "languages": ["en", "hi"], "verified": True},
    "subscription": {"status": "active", "plan": "Pro", "days_remaining": 82},
    "performance": {"window_days": 30, "views": 2410, "calls": 18, "directions": 45, "ctr": 0.021, "delta_7d": {"views_pct": 0.18, "calls_pct": -0.05}},
    "offers": [{"id": "o_001", "title": "Dental Cleaning @ ₹299", "status": "active"}],
    "signals": ["stale_posts:22d", "ctr_below_peer_median", "high_risk_adult_cohort"],
}


def seed_base():
    push_context("category", "dentists", 10000, BASE_CATEGORY)
    push_context("merchant", "m_001_drmeera", 10000, BASE_MERCHANT)


# ── Tests ──

def test_01_new_digest_injected():
    """Judge pushes 5 new digest items via version bump. Bot must reference new items."""
    updated_cat = dict(BASE_CATEGORY)
    updated_cat["digest"] = [
        {"id": "d_001", "kind": "research", "title": "Fluoride recall study", "source": "JIDA Oct 2026", "trial_n": 2100},
        {"id": "d_002", "kind": "research", "title": "Aligner therapy increases referral rate 42%", "source": "ADA Mar 2026", "trial_n": 850, "patient_segment": "adults_25_45"},
        {"id": "d_003", "kind": "compliance", "title": "New bio-waste disposal rules effective April", "source": "Delhi Health Dept", "action_required": True},
        {"id": "d_004", "kind": "research", "title": "Teledentistry follow-ups reduce no-show by 31%", "source": "IDJ Feb 2026", "trial_n": 1200},
        {"id": "d_005", "kind": "research", "title": "Xylitol gum reduces caries in high-risk cohort", "source": "JIDA Jan 2026", "trial_n": 600, "patient_segment": "high_risk_adults"},
    ]
    push_context("category", "dentists", 10001, updated_cat)
    push_context("trigger", "adapt_trg_new_digest", 1, {
        "id": "adapt_trg_new_digest", "scope": "merchant", "kind": "research_digest",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"top_item_id": "d_002"},
        "urgency": 3, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_new_digest"])
    check("New digest trigger produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("Body references new digest topic (aligner/referral)",
              any(x in body for x in ["aligner", "referral", "42", "ada"]),
              f"Body: {data['actions'][0].get('body', '')[:150]}")


def test_02_compliance_digest_injected():
    """Judge pushes compliance digest. Bot must convey urgency + action required."""
    push_context("trigger", "adapt_trg_compliance", 1, {
        "id": "adapt_trg_compliance", "scope": "merchant", "kind": "research_digest",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"top_item_id": "d_003"},
        "urgency": 4, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_compliance"])
    check("Compliance digest produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("Body mentions compliance/bio-waste/rules",
              any(x in body for x in ["bio-waste", "compliance", "rules", "disposal", "waste"]),
              f"Body: {data['actions'][0].get('body', '')[:150]}")


def test_03_perf_dip_injected():
    """Judge pushes updated merchant performance with dip. Bot must reflect new numbers."""
    updated_merchant = dict(BASE_MERCHANT)
    updated_merchant["performance"] = {
        "window_days": 30, "views": 1800, "calls": 8, "directions": 20,
        "ctr": 0.012, "delta_7d": {"views_pct": -0.35, "calls_pct": -0.55}
    }
    push_context("merchant", "m_001_drmeera", 2, updated_merchant)
    push_context("trigger", "adapt_trg_perf_dip", 1, {
        "id": "adapt_trg_perf_dip", "scope": "merchant", "kind": "perf_dip",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"metric": "calls", "delta_pct": -0.55, "window": "7d", "likely_driver": "stale_posts"},
        "urgency": 5, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_perf_dip"])
    check("Perf dip trigger produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("Body reflects dip metrics (calls dropped/negative)",
              any(x in body for x in ["dip", "dropped", "fell", "decline", "down", "decreased"]),
              f"Body: {data['actions'][0].get('body', '')[:150]}")


def test_04_perf_spike_injected():
    """Judge pushes merchant with performance spike. Bot must reinforce momentum."""
    updated_merchant = dict(BASE_MERCHANT)
    updated_merchant["performance"] = {
        "window_days": 30, "views": 4200, "calls": 35, "directions": 80,
        "ctr": 0.045, "delta_7d": {"views_pct": 0.74, "calls_pct": 0.94}
    }
    push_context("merchant", "m_001_drmeera", 3, updated_merchant)
    push_context("trigger", "adapt_trg_perf_spike", 1, {
        "id": "adapt_trg_perf_spike", "scope": "merchant", "kind": "perf_spike",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"metric": "views", "delta_pct": 0.74, "window": "7d", "likely_driver": "google_post_viral"},
        "urgency": 2, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_perf_spike"])
    check("Perf spike trigger produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("Body reflects spike/growth momentum",
              any(x in body for x in ["spike", "up", "nice", "growing", "momentum", "increased"]),
              f"Body: {data['actions'][0].get('body', '')[:150]}")


def test_05_new_customer_injected_with_recall():
    """Judge pushes new customer context mid-test + recall_due trigger. Bot must ground in customer data."""
    push_context("customer", "adapt_c_new_rajesh", 1, {
        "customer_id": "adapt_c_new_rajesh",
        "merchant_id": "m_001_drmeera",
        "identity": {"name": "Rajesh Kumar", "phone_redacted": "<phone>", "language_pref": "hi"},
        "relationship": {
            "first_visit": "2025-08-15",
            "last_visit": "2025-11-20",
            "visits_total": 6,
            "services_received": ["root_canal", "crown", "cleaning", "cleaning", "cleaning", "filling"]
        },
        "state": "lapsed_hard",
        "preferences": {"preferred_slots": "weekend_morning", "channel": "whatsapp"},
        "consent": {"opted_in_at": "2025-08-15", "scope": ["recall_reminders"]},
    })
    push_context("trigger", "adapt_trg_recall_rajesh", 1, {
        "id": "adapt_trg_recall_rajesh", "scope": "customer", "kind": "recall_due",
        "merchant_id": "m_001_drmeera", "customer_id": "adapt_c_new_rajesh",
        "payload": {},
        "urgency": 4, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_recall_rajesh"])
    check("New customer recall produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body addresses customer by name (Rajesh)", "Rajesh" in body, f"Body: {body[:120]}")
        check("Body is customer-facing (merchant_on_behalf)",
              data["actions"][0].get("send_as") == "merchant_on_behalf",
              f"send_as: {data['actions'][0].get('send_as')}")


def test_06_new_category_see_injection():
    """Judge pushes an entirely new category (dermatologists). Bot must compose using new category."""
    push_context("category", "dermatologists", 1, {
        "slug": "dermatologists",
        "offer_catalog": [{"title": "Acne Treatment Consult @ ₹499", "status": "active", "audience": "new_user"}],
        "voice": {"tone": "clinical_professional", "taboos": ["permanent cure", "miracle"]},
        "peer_stats": {"avg_ctr": 0.025, "avg_rating": 4.2},
        "digest": [{"id": "derm_001", "title": "Retinoid therapy reduces acne scarring 60%", "source": "IJDVL 2026"}],
    })
    push_context("merchant", "m_002_skin", 1, {
        "merchant_id": "m_002_skin",
        "category_slug": "dermatologists",
        "identity": {"name": "SkinGlow Clinic", "city": "Mumbai", "locality": "Bandra", "languages": ["en"]},
        "subscription": {"status": "active", "plan": "Basic", "days_remaining": 30},
        "performance": {"views": 800, "calls": 5, "ctr": 0.018},
        "offers": [{"id": "o_skin_001", "title": "Acne Treatment Consult @ ₹499", "status": "active"}],
        "signals": ["new_merchant:15d"],
    })
    push_context("trigger", "adapt_trg_skin_welcome", 1, {
        "id": "adapt_trg_skin_welcome", "scope": "merchant", "kind": "research_digest",
        "merchant_id": "m_002_skin", "customer_id": None,
        "payload": {"top_item_id": "derm_001"},
        "urgency": 2, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_skin_welcome"])
    check("New category merchant produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("Body references dermatology topic (retinoid/acne/scarring)",
              any(x in body for x in ["retinoid", "acne", "scar", "skin"]),
              f"Body: {data['actions'][0].get('body', '')[:150]}")
        check("Body uses correct merchant name (SkinGlow)",
              "skinglow" in body or "bandra" in body,
              f"Body: {data['actions'][0].get('body', '')[:150]}")


def test_07_seasonal_event_trigger():
    """Judge pushes seasonal event trigger. Bot must propose campaign draft."""
    push_context("trigger", "adapt_trg_festival", 1, {
        "id": "adapt_trg_festival", "scope": "merchant", "kind": "festival_upcoming",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"event": "Diwali", "days_away": 14, "expected_demand_spike": "teeth_whitening"},
        "urgency": 3, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_festival"])
    check("Festival trigger produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("Body mentions festival/campaign/draft",
              any(x in body for x in ["diwali", "festival", "campaign", "draft", "whitening"]),
              f"Body: {data['actions'][0].get('body', '')[:150]}")


def test_08_competitor_new_category():
    """Judge pushes competitor trigger for non-dentist category."""
    push_context("trigger", "adapt_trg_skin_competitor", 1, {
        "id": "adapt_trg_skin_competitor", "scope": "merchant", "kind": "competitor_opened",
        "merchant_id": "m_002_skin", "customer_id": None,
        "payload": {"competitor_name": "ClearSkin Clinic", "distance_km": 1.2, "their_offer": "Free skin analysis", "opened_date": "2026-04-20"},
        "urgency": 4, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_skin_competitor"])
    check("Competitor trigger for new category produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        body = data["actions"][0].get("body", "").lower()
        check("Body references competitor/competition",
              any(x in body for x in ["competitor", "clearskin", "competition", "stay ahead", "differentiate"]),
              f"Body: {data['actions'][0].get('body', '')[:150]}")


def test_09_stale_data_not_used():
    """After version bump, tick must use NEW performance data, not old."""
    updated_merchant = dict(BASE_MERCHANT)
    updated_merchant["performance"] = {
        "window_days": 30, "views": 5000, "calls": 42, "directions": 90,
        "ctr": 0.055, "delta_7d": {"views_pct": 1.07, "calls_pct": 1.33}
    }
    push_context("merchant", "m_001_drmeera", 4, updated_merchant)
    push_context("trigger", "adapt_trg_stale_check", 1, {
        "id": "adapt_trg_stale_check", "scope": "merchant", "kind": "milestone_reached",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"milestone": "5000_views", "achieved_at": "2026-04-26"},
        "urgency": 2, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_stale_check"])
    check("Milestone trigger produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        rationale = data["actions"][0].get("rationale", "").lower()
        body = data["actions"][0].get("body", "").lower()
        check("Rationale/body doesn't reference stale low numbers",
              "2410" not in body and "18" not in body.split("calls")[0][-5:] if "calls" in body else True,
              f"Body: {data['actions'][0].get('body', '')[:150]}")


def test_10_expired_after_injection():
    """Judge injects trigger but it's already expired. Must be filtered."""
    push_context("trigger", "adapt_trg_expired_new", 1, {
        "id": "adapt_trg_expired_new", "scope": "merchant", "kind": "ipl_match_today",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"match": "MI vs CSK", "date": "2026-04-01"},
        "urgency": 1, "expires_at": "2026-04-02T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_expired_new"])
    check("Expired injected trigger filtered", code == 200 and len(data.get("actions", [])) == 0)


def test_11_multi_turn_with_updated_context():
    """Push new context, start conversation, reply, verify bot uses new context in follow-up."""
    push_context("merchant", "m_001_drmeera", 5, {
        **BASE_MERCHANT,
        "performance": {"views": 3000, "calls": 25, "ctr": 0.030, "delta_7d": {"views_pct": 0.24, "calls_pct": 0.38}},
        "offers": [
            {"id": "o_001", "title": "Dental Cleaning @ ₹299", "status": "active"},
            {"id": "o_002", "title": "Teeth Whitening @ ₹999", "status": "active"},
        ],
    })
    push_context("trigger", "adapt_trg_multi_turn", 1, {
        "id": "adapt_trg_multi_turn", "scope": "merchant", "kind": "curious_ask_due",
        "merchant_id": "m_001_drmeera", "customer_id": None,
        "payload": {"question_topic": "new_whitening_offer"},
        "urgency": 3, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_multi_turn"])
    check("Multi-turn setup produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        conv_id = data["actions"][0]["conversation_id"]
        code2, reply_data = reply(conv_id, "m_001_drmeera", "merchant", "Yes, tell me more", 2)
        check("Reply returns send action", reply_data.get("action") == "send", f"Action: {reply_data.get('action')}")
        body = reply_data.get("body", "").lower()
        check("Reply body references updated context (whitening/new offer)",
              any(x in body for x in ["whitening", "offer", "999", "teeth"]),
              f"Body: {reply_data.get('body', '')[:120]}")


def test_12_cross_scope_linking():
    """Verify category → merchant → trigger → customer all link correctly after injection."""
    push_context("customer", "adapt_c_cross_test", 1, {
        "customer_id": "adapt_c_cross_test",
        "merchant_id": "m_002_skin",
        "identity": {"name": "Anita", "language_pref": "en"},
        "relationship": {"first_visit": "2026-01-10", "last_visit": "2026-02-15", "visits_total": 3, "services_received": ["consultation", "facial"]},
        "state": "lapsed_soft",
        "consent": {"opted_in_at": "2026-01-10", "scope": ["recall_reminders"]},
    })
    push_context("trigger", "adapt_trg_cross_scope", 1, {
        "id": "adapt_trg_cross_scope", "scope": "customer", "kind": "recall_due",
        "merchant_id": "m_002_skin", "customer_id": "adapt_c_cross_test",
        "payload": {},
        "urgency": 4, "expires_at": "2026-06-01T00:00:00Z",
    })
    code, data = tick(NOW, ["adapt_trg_cross_scope"])
    check("Cross-scope linking produces action", code == 200 and data.get("actions"))
    if data.get("actions"):
        action = data["actions"][0]
        check("Conversation ID includes merchant + trigger + customer",
              "m_002_skin" in action.get("conversation_id", "") and "adapt_c_cross_test" in action.get("conversation_id", ""),
              f"conv_id: {action.get('conversation_id')}")
        body = action.get("body", "")
        check("Body uses correct merchant (SkinGlow) and customer (Anita)",
              "Anita" in body and ("SkinGlow" in body or "Bandra" in body),
              f"Body: {body[:120]}")


if __name__ == "__main__":
    print(f"Phase 3 Adaptive Context Injection Tests — {BOT_URL}")
    print("=" * 60)

    print("\nSeeding base contexts...")
    seed_base()

    tests = [
        test_01_new_digest_injected,
        test_02_compliance_digest_injected,
        test_03_perf_dip_injected,
        test_04_perf_spike_injected,
        test_05_new_customer_injected_with_recall,
        test_06_new_category_see_injection,
        test_07_seasonal_event_trigger,
        test_08_competitor_new_category,
        test_09_stale_data_not_used,
        test_10_expired_after_injection,
        test_11_multi_turn_with_updated_context,
        test_12_cross_scope_linking,
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
        print("All tests passed! Bot handles adaptive context injection correctly.")
    else:
        print(f"{FAIL} test(s) failed. Review failures above.")
    sys.exit(0 if FAIL == 0 else 1)
