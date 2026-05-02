#!/usr/bin/env python3
"""
Fresh Scenario Test — simulates the actual judge harness.
Tests with entirely NEW data the bot has never seen:
- Unseen merchants, categories, triggers, customers
- Extreme performance deltas
- Novel digest items and trend signals
- Unexpected customer scopes
- Reply patterns the bot can't predict
"""

import sys
import json
import time
import ssl
import http.client
from datetime import datetime, timezone
from urllib import parse
from pathlib import Path

BOT_URL = sys.argv[1] if len(sys.argv) > 1 else "https://algsoch-magicpin.onrender.com"

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

_RUN = int(time.time() * 1000)

def _id(base: str) -> str:
    return f"fresh_{_RUN}_{base}"


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
        "version": version + _RUN + int(time.time()),
        "payload": payload,
        "delivered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    })


def tick_for(merchant_id, trigger_ids):
    return post("/v1/tick", {
        "merchant_id": merchant_id,
        "tick_id": f"tick_{merchant_id}_{_RUN}",
        "available_actions": 15,
        "available_triggers": trigger_ids,
        "now": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    })


def reply(conv_id, merchant_id, message, turn, customer_id=None, from_role="merchant"):
    return post("/v1/reply", {
        "conversation_id": conv_id,
        "merchant_id": merchant_id,
        "customer_id": customer_id,
        "from_role": from_role,
        "message": message,
        "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "turn_number": turn
    })


def check(label, condition, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {label}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def make_fresh_merchant(mid, cat_slug="dentists", identity=None, performance=None, signals=None, offers=None, subscription=None, customer_aggregate=None):
    result = {
        "merchant_id": mid,
        "category_slug": cat_slug,
        "identity": identity if identity is not None else {
            "name": f"Fresh Clinic {mid[:8]}",
            "owner_first_name": "Aarav",
            "city": "Kochi",
            "locality": "Ernakulam",
            "languages": ["en"],
        },
        "subscription": subscription if subscription is not None else {"status": "active", "plan": "Premium", "days_remaining": 45},
        "performance": performance if performance is not None else {"views": 320, "calls": 42, "ctr": 0.038, "delta_7d": {"views_pct": 0.12, "calls_pct": -0.08}},
        "signals": signals if signals is not None else ["above_peer: views_growing"],
        "offers": offers if offers is not None else [],
    }
    if customer_aggregate is not None:
        result["customer_aggregate"] = customer_aggregate
    return result


def make_fresh_category(slug, digest=None, peer_stats=None, trend_signals=None, seasonal_beats=None, offer_catalog=None, voice=None):
    return {
        "id": slug,
        "slug": slug,
        "display_name": slug.title(),
        "voice": voice if voice is not None else {"tone": "professional", "register": "professional", "salutation_examples": ["Hi {first_name}"], "vocab_allowed": [], "vocab_taboo": [], "style_notes": "Professional tone."},
        "offer_catalog": offer_catalog if offer_catalog is not None else [{"title": "Fresh Offer", "description": "New promotion"}],
        "peer_stats": peer_stats if peer_stats is not None else {"avg_views_30d": 200, "avg_calls_30d": 25, "avg_ctr": 0.03},
        "digest": digest if digest is not None else [],
        "seasonal_beats": seasonal_beats if seasonal_beats is not None else [],
        "trend_signals": trend_signals if trend_signals is not None else [],
        "regulatory_authorities": [],
    }


def make_fresh_trigger(tid, kind, merchant_id, urgency=3, scope="merchant", payload=None, expires_at=None, customer_id=None):
    result = {
        "id": tid,
        "merchant_id": merchant_id,
        "kind": kind,
        "scope": scope,
        "urgency": urgency,
        "payload": payload if payload is not None else {},
        "expires_at": expires_at if expires_at is not None else "2027-12-31T23:59:59Z",
    }
    if customer_id is not None:
        result["customer_id"] = customer_id
    return result


def make_fresh_customer(cid, identity=None, relationship=None, consent=None):
    return {
        "id": cid,
        "identity": identity if identity is not None else {"name": "Priya Sharma", "language_pref": "en"},
        "relationship": relationship if relationship is not None else {"last_visit": "2024-11-15", "visits_total": 8, "services_received": ["dental_cleaning", "filling"]},
        "consent": consent if consent is not None else ["appointment_reminders", "recall_reminders"],
    }


# =============================================================================
# FRESH SCENARIO TESTS
# =============================================================================

def test_fresh_dentist_with_extreme_dip():
    """Dentist with 60% call drop — bot should quantify loss and suggest recovery."""
    mid = _id("m_extreme_dip")
    cat = make_fresh_category("fresh_dentists_extreme",
        peer_stats={"avg_views_30d": 150, "avg_calls_30d": 30, "avg_ctr": 0.025},
        offer_catalog=[{"title": "Root Canal Package @ ₹2999", "description": "Comprehensive"}])
    merchant = make_fresh_merchant(mid, "fresh_dentists_extreme",
        performance={"views": 200, "calls": 12, "ctr": 0.02,
                     "delta_7d": {"views_pct": -0.15, "calls_pct": -0.60}},
        identity={"name": "Dr. Kavita Dental", "owner_first_name": "Kavita",
                  "city": "Thiruvananthapuram", "locality": "Pattom", "languages": ["en"]})
    trigger = make_fresh_trigger(_id("trg_dip"), "perf_dip", mid, urgency=5,
        payload={"metric": "calls", "delta_pct": -0.60, "window": "7d", "vs_baseline": 30})

    push_context("category", "fresh_dentists_extreme", 1, cat)
    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Fresh extreme dip tick produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions 60% drop", "60" in body, f"Body: {body[:100]}")
        check("Body references Thiruvananthapuram or Pattom",
              "thiruvananthapuram" in body.lower() or "pattom" in body.lower(),
              f"Body: {body[:100]}")
        check("Body has recovery suggestion", "recover" in body.lower() or "draft" in body.lower(),
              f"Body: {body[:100]}")


def test_fresh_unknown_category():
    """Completely new category slug — bot should still compose valid message."""
    mid = _id("m_unknown_cat")
    cat = make_fresh_category("pet_grooming",
        voice={"tone": "friendly", "register": "casual", "salutation_examples": ["Hi {first_name}"],
               "vocab_allowed": [], "vocab_taboo": [], "style_notes": "Pet-friendly tone."},
        peer_stats={"avg_views_30d": 80, "avg_calls_30d": 10, "avg_ctr": 0.015},
        offer_catalog=[{"title": "Full Grooming @ ₹599", "description": "Bath + nail trim"}])
    merchant = make_fresh_merchant(mid, "pet_grooming",
        identity={"name": "Paws & Claws", "owner_first_name": "Rahul",
                  "city": "Noida", "locality": "Sector 62", "languages": ["en"]},
        performance={"views": 95, "calls": 8, "ctr": 0.018})
    trigger = make_fresh_trigger(_id("trg_milestone"), "milestone_reached", mid, urgency=2,
        payload={"milestone": "50_reviews", "metric": "review_count", "value_now": 50})

    push_context("category", "pet_grooming", 1, cat)
    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Unknown category produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions milestone", "50" in body and "review" in body.lower(),
              f"Body: {body[:100]}")
        check("Body references Noida or Sector 62",
              "noida" in body.lower() or "sector 62" in body.lower(),
              f"Body: {body[:100]}")


def test_fresh_customer_with_partial_consent():
    """Customer who only consented to recall_reminders — no other messages."""
    mid = _id("m_partial_consent")
    cid = _id("c_partial")
    merchant = make_fresh_merchant(mid, "fresh_dentists",
        identity={"name": "Smile Studio", "owner_first_name": "Neha",
                  "city": "Goa", "locality": "Panaji", "languages": ["en"]})
    customer = make_fresh_customer(cid,
        identity={"name": "Aditi Menon", "language_pref": "en"},
        relationship={"last_visit": "2024-06-20", "visits_total": 3, "services_received": ["scaling"]},
        consent=["recall_reminders"])
    trigger = make_fresh_trigger(_id("trg_recall"), "recall_due", mid, urgency=3,
        scope="customer", payload={"customer_id": cid}, customer_id=cid)

    push_context("merchant", mid, 1, merchant)
    push_context("customer", cid, 1, customer)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Customer recall produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        action = data["actions"][0]
        body = action.get("body", "")
        check("Customer-facing message", action.get("send_as") == "merchant_on_behalf",
              f"send_as: {action.get('send_as')}")
        check("Body addresses customer", "aditi" in body.lower(),
              f"Body: {body[:100]}")
        check("Body mentions recall/cleaning", "recall" in body.lower() or "cleaning" in body.lower() or "booking" in body.lower() or "appointment" in body.lower(),
              f"Body: {body[:100]}")


def test_fresh_digest_with_novel_research():
    """Research digest with entirely new study — bot should ground in digest data."""
    mid = _id("m_novel_digest")
    cat = make_fresh_category("fresh_dentists_digest",
        digest=[{"id": "r_novel_1", "title": "Nano-hydroxyapatite remineralization",
                 "source": "Journal of Clinical Dentistry, 2025", "trial_n": 342,
                 "effect_size": "moderate", "patient_segment": "high_caries_risk",
                 "actionable": "Add nano-HAp product to practice inventory"}],
        peer_stats={"avg_views_30d": 180, "avg_calls_30d": 22, "avg_ctr": 0.028})
    merchant = make_fresh_merchant(mid, "fresh_dentists_digest",
        identity={"name": "Dr. Rajiv Dental Care", "owner_first_name": "Rajiv",
                  "city": "Indore", "locality": "Vijay Nagar", "languages": ["en"]},
        performance={"views": 250, "calls": 35, "ctr": 0.032},
        customer_aggregate={"high_risk_adult_count": 12})
    trigger = make_fresh_trigger(_id("trg_digest"), "research_digest", mid, urgency=2,
        payload={"top_item_id": "r_novel_1"})

    push_context("category", "fresh_dentists_digest", 1, cat)
    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Novel digest produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions nano-hydroxyapatite or remineralization",
              "nano" in body.lower() or "remineral" in body.lower(),
              f"Body: {body[:120]}")
        check("Body references 342 patients or study size", "342" in body,
              f"Body: {body[:120]}")
        check("Body mentions Indore or Vijay Nagar", "indore" in body.lower() or "vijay nagar" in body.lower(),
              f"Body: {body[:120]}")
        check("Body mentions high-risk patient count", "12" in body,
              f"Body: {body[:120]}")


def test_fresh_competitor_far_away():
    """Competitor 15km away with different offer — bot should differentiate."""
    mid = _id("m_comp_far")
    merchant = make_fresh_merchant(mid, "fresh_restaurants",
        identity={"name": "Biryani House", "owner_first_name": "Imran",
                  "city": "Hyderabad", "locality": "Banjara Hills", "languages": ["en"]},
        offers=[{"title": "Family Biryani Combo @ ₹899", "status": "active"}])
    trigger = make_fresh_trigger(_id("trg_comp"), "competitor_opened", mid, urgency=4,
        payload={"competitor_name": "Paradise Biryani", "distance_km": 15,
                 "their_offer": "Biryani + Raita @ ₹599", "opened_date": "2025-04-15"})

    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Far competitor produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions Paradise Biryani", "paradise" in body.lower(),
              f"Body: {body[:100]}")
        check("Body mentions 15km distance", "15" in body,
              f"Body: {body[:100]}")
        check("Body differentiates Family Biryani Combo", "family" in body.lower() or "biryani" in body.lower(),
              f"Body: {body[:100]}")
        check("Body references Banjara Hills or Hyderabad", "banjara" in body.lower() or "hyderabad" in body.lower(),
              f"Body: {body[:100]}")


def test_fresh_gbp_unverified_huge_uplift():
    """Unverified GBP with 50% estimated uplift — bot should quantify impact."""
    mid = _id("m_gbp_huge")
    merchant = make_fresh_merchant(mid, "fresh_dentists_gbp",
        identity={"name": "City Dental Clinic", "owner_first_name": "Sneha",
                  "city": "Surat", "locality": "Athwa", "languages": ["en"]},
        performance={"views": 500, "calls": 75, "ctr": 0.045})
    trigger = make_fresh_trigger(_id("trg_gbp"), "gbp_unverified", mid, urgency=4,
        payload={"estimated_uplift_pct": 0.50, "verification_path": "video_verification"})

    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Huge GBP uplift produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions 250 extra views (50% of 500)", "250" in body,
              f"Body: {body[:120]}")
        check("Body mentions video verification", "video" in body.lower(),
              f"Body: {body[:120]}")
        check("Body references Surat or Athwa", "surat" in body.lower() or "athwa" in body.lower(),
              f"Body: {body[:120]}")


def test_fresh_seasonal_with_zero_performance():
    """Seasonal trigger for merchant with zero views/calls — bot should still engage."""
    mid = _id("m_seasonal_zero")
    cat = make_fresh_category("fresh_gyms_seasonal",
        peer_stats={"avg_views_30d": 100, "avg_calls_30d": 15, "avg_ctr": 0.02,
                    "campaign_adoption_rate": 0.35},
        trend_signals=[{"query": "summer_fitness_challenges", "delta_yoy": 0.45}],
        offer_catalog=[{"title": "Summer Shred @ ₹1999", "description": "8-week program"}])
    merchant = make_fresh_merchant(mid, "fresh_gyms_seasonal",
        identity={"name": "FitZone Gym", "owner_first_name": "Arjun",
                  "city": "Chandigarh", "locality": "Sector 17", "languages": ["en"]},
        performance={"views": 0, "calls": 0, "ctr": 0})
    trigger = make_fresh_trigger(_id("trg_seasonal"), "category_seasonal", mid, urgency=3,
        payload={"season": "summer", "trends": ["summer_fitness_challenges_+45%"]})

    push_context("category", "fresh_gyms_seasonal", 1, cat)
    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Seasonal with zero perf produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions summer", "summer" in body.lower(),
              f"Body: {body[:100]}")
        check("Body references Chandigarh or Sector 17", "chandigarh" in body.lower() or "sector 17" in body.lower(),
              f"Body: {body[:100]}")


def test_fresh_multi_trigger_urgency_sorting():
    """Multiple triggers with varying urgency — highest should fire first."""
    mid = _id("m_multi_urgency")
    merchant = make_fresh_merchant(mid, "fresh_pharmacies",
        identity={"name": "MedPlus Pharmacy", "owner_first_name": "Deepak",
                  "city": "Lucknow", "locality": "Hazratganj", "languages": ["en"]},
        offers=[{"title": "Monthly Medicine Bundle @ ₹499", "status": "active"}])
    
    t1 = make_fresh_trigger(_id("trg_low"), "research_digest", mid, urgency=1,
        payload={"top_item_id": "d_001"})
    t2 = make_fresh_trigger(_id("trg_high"), "perf_dip", mid, urgency=5,
        payload={"metric": "calls", "delta_pct": -0.30, "window": "7d", "vs_baseline": 20})
    t3 = make_fresh_trigger(_id("trg_mid"), "competitor_opened", mid, urgency=3,
        payload={"competitor_name": "Apollo Pharmacy", "distance_km": 2})

    push_context("merchant", mid, 1, merchant)
    push_context("trigger", t1["id"], 1, t1)
    push_context("trigger", t2["id"], 1, t2)
    push_context("trigger", t3["id"], 1, t3)

    code, data = tick_for(mid, [t1["id"], t2["id"], t3["id"]])
    check("Multi-urgency tick produces actions", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        first = data["actions"][0]
        body = first.get("body", "")
        check("First action is highest urgency (perf_dip)",
              "dip" in body.lower() or "dropped" in body.lower() or "30" in body,
              f"First action body: {body[:100]}")


def test_fresh_reply_to_unseen_trigger():
    """Reply to a trigger kind the bot hasn't been trained on — should handle gracefully."""
    mid = _id("m_unknown_reply")
    merchant = make_fresh_merchant(mid, "fresh_salons",
        identity={"name": "Hair Craft Studio", "owner_first_name": "Meera",
                  "city": "Ahmedabad", "locality": "Satellite", "languages": ["en"]},
        offers=[{"title": "Keratin Treatment @ ₹1499", "status": "active"}])
    trigger = make_fresh_trigger(_id("trg_unknown_kind"), "loyalty_milestone", mid, urgency=2,
        payload={"milestone_type": "repeat_customer", "count": 100})

    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Unknown trigger kind produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body has meaningful content (>30 chars)", len(body) > 30,
              f"Body length: {len(body)}")
        check("Body mentions 100", "100" in body,
              f"Body: {body[:100]}")


def test_fresh_customer_lapsed_with_high_visits():
    """Lapsed customer with 25 visits — warm winback."""
    mid = _id("m_lapsed_high")
    cid = _id("c_lapsed_high")
    merchant = make_fresh_merchant(mid, "fresh_dentists_lapsed",
        identity={"name": "Pearl Dental Clinic", "owner_first_name": "Anjali",
                  "city": "Vizag", "locality": "Beach Road", "languages": ["en"]},
        offers=[{"title": "Smile Makeover @ ₹4999", "status": "active"}])
    customer = make_fresh_customer(cid,
        identity={"name": "Suresh Reddy", "language_pref": "en"},
        relationship={"last_visit": "2024-03-10", "visits_total": 25,
                      "services_received": ["root_canal", "crown_placement", "dental_cleaning_x4"]},
        consent=["appointment_reminders", "recall_reminders"])
    trigger = make_fresh_trigger(_id("trg_lapsed"), "customer_lapsed_hard", mid, urgency=4,
        scope="customer", payload={"customer_id": cid, "days_since_last_visit": 420}, customer_id=cid)

    push_context("merchant", mid, 1, merchant)
    push_context("customer", cid, 1, customer)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("High-visit lapsed customer produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        action = data["actions"][0]
        body = action.get("body", "")
        check("Customer-facing", action.get("send_as") == "merchant_on_behalf",
              f"send_as: {action.get('send_as')}")
        check("Body addresses Suresh", "suresh" in body.lower(),
              f"Body: {body[:100]}")
        check("Body mentions 25 visits", "25" in body,
              f"Body: {body[:100]}")
        check("Body mentions Smile Makeover or recent service", "smile" in body.lower() or "crown" in body.lower() or "cleaning" in body.lower(),
              f"Body: {body[:100]}")


def test_fresh_supply_alert_with_batches():
    """Pharmacy supply alert with affected batches — should show details."""
    mid = _id("m_supply_alert")
    cat = make_fresh_category("fresh_pharmacies_alert",
        digest=[{"id": "sa_001", "title": "Amoxicillin batch recall",
                 "source": "CDSCO", "actionable": "Check inventory and quarantine affected batches"}],
        peer_stats={"avg_views_30d": 120, "avg_calls_30d": 18, "avg_ctr": 0.022})
    merchant = make_fresh_merchant(mid, "fresh_pharmacies_alert",
        identity={"name": "LifeCare Pharmacy", "owner_first_name": "Vinod",
                  "city": "Nagpur", "locality": "Dharampeth", "languages": ["en"]})
    trigger = make_fresh_trigger(_id("trg_supply"), "supply_alert", mid, urgency=5,
        payload={"molecule": "Amoxicillin 500mg", "affected_batches": ["LOT-2024-A17", "LOT-2024-A19"],
                 "manufacturer": "Cipla Ltd", "alert_id": "sa_001",
                 "deadline_iso": "2025-06-15T00:00:00Z"})

    push_context("category", "fresh_pharmacies_alert", 1, cat)
    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Supply alert produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions Amoxicillin", "amoxicillin" in body.lower(),
              f"Body: {body[:120]}")
        check("Body mentions batch numbers", "LOT" in body or "batch" in body.lower(),
              f"Body: {body[:120]}")
        check("Body mentions Cipla", "cipla" in body.lower(),
              f"Body: {body[:120]}")
        check("Body references Nagpur or Dharampeth", "nagpur" in body.lower() or "dharampeth" in body.lower(),
              f"Body: {body[:120]}")


def test_fresh_perf_spike_with_driver():
    """Performance spike with specific likely driver — bot should capitalize."""
    mid = _id("m_spike_driver")
    merchant = make_fresh_merchant(mid, "fresh_restaurants_spike",
        identity={"name": "Dosa Plaza", "owner_first_name": "Lakshmi",
                  "city": "Mysore", "locality": "Devaraja Mohalla", "languages": ["en"]},
        performance={"views": 480, "calls": 65, "ctr": 0.052,
                     "delta_7d": {"views_pct": 0.45, "calls_pct": 0.38}},
        offers=[{"title": "Mini Tiffin @ ₹99", "status": "active"}])
    trigger = make_fresh_trigger(_id("trg_spike"), "perf_spike", mid, urgency=3,
        payload={"metric": "views", "delta_pct": 0.45, "window": "7d",
                 "likely_driver": "festival_season", "vs_baseline": 300})

    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Perf spike with driver produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions 45% increase", "45" in body,
              f"Body: {body[:100]}")
        check("Body mentions festival season", "festival" in body.lower(),
              f"Body: {body[:100]}")
        check("Body references Mysore or Devaraja Mohalla", "mysore" in body.lower() or "devaraja" in body.lower(),
              f"Body: {body[:100]}")
        check("Body has capitalize/momentum language", "momentum" in body.lower() or "capitalize" in body.lower() or "pin" in body.lower(),
              f"Body: {body[:100]}")


def test_fresh_regulation_change_with_deadline():
    """Regulation change with compliance deadline — urgency matters."""
    mid = _id("m_regulation")
    cat = make_fresh_category("fresh_dentists_reg",
        digest=[{"id": "reg_001", "title": "New dental waste disposal norms",
                 "source": "State Dental Council", "actionable": "Update waste segregation protocol"}],
        peer_stats={"avg_views_30d": 160, "avg_calls_30d": 20, "avg_ctr": 0.025})
    merchant = make_fresh_merchant(mid, "fresh_dentists_reg",
        identity={"name": "Bright Smile Dental", "owner_first_name": "Pooja",
                  "city": "Coimbatore", "locality": "RS Puram", "languages": ["en"]})
    trigger = make_fresh_trigger(_id("trg_reg"), "regulation_change", mid, urgency=4,
        payload={"top_item_id": "reg_001", "deadline_iso": "2025-07-01T00:00:00Z"})

    push_context("category", "fresh_dentists_reg", 1, cat)
    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Regulation change produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions waste disposal", "waste" in body.lower(),
              f"Body: {body[:120]}")
        check("Body mentions Coimbatore or RS Puram", "coimbatore" in body.lower() or "rs puram" in body.lower(),
              f"Body: {body[:120]}")
        check("Body has deadline awareness", "deadline" in body.lower() or "days" in body.lower() or "comply" in body.lower(),
              f"Body: {body[:120]}")


def test_fresh_reply_hinglish():
    """Hinglish reply should route correctly."""
    mid = _id("m_hinglish")
    merchant = make_fresh_merchant(mid, "fresh_salons_hi",
        identity={"name": "Beauty Zone", "owner_first_name": "Anita",
                  "city": "Jaipur", "locality": "Malviya Nagar", "languages": ["en", "hi"]})
    trigger = make_fresh_trigger(_id("trg_curious"), "curious_ask_due", mid, urgency=2,
        payload={"ask_template": "service_demand_check"})

    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    # First tick to create conversation
    code, data = tick_for(mid, [trigger["id"]])
    check("Hinglish setup produces tick action", code == 200 and len(data.get("actions", [])) >= 1)
    if not data.get("actions"):
        return
    
    # Now reply in Hinglish
    conv_id = data["actions"][0].get("conversation_id", f"conv_hinglish_{_RUN}")
    code, reply_data = reply(conv_id, mid, "kya offer hai mere liye?", 1)
    check("Hinglish reply returns send", code == 200 and reply_data.get("action") == "send",
          f"Action: {reply_data.get('action')}")
    if reply_data.get("body"):
        check("Reply has content", len(reply_data["body"]) > 20,
              f"Body: {reply_data['body'][:80]}")


def test_fresh_no_offers_at_all():
    """Merchant with zero offers — composition should not hallucinate offers."""
    mid = _id("m_no_offers")
    cat_slug = _id("cat_gyms_empty")
    cat = make_fresh_category(cat_slug,
        offer_catalog=[],
        peer_stats={"avg_views_30d": 90, "avg_calls_30d": 12, "avg_ctr": 0.025})
    merchant = make_fresh_merchant(mid, cat_slug,
        identity={"name": "Iron Temple Gym", "owner_first_name": "Vikram",
                  "city": "Pune", "locality": "Kothrud", "languages": ["en"]},
        performance={"views": 110, "calls": 15, "ctr": 0.022},
        offers=[])
    trigger = make_fresh_trigger(_id("trg_dip_no_offers"), "perf_dip", mid, urgency=4,
        payload={"metric": "views", "delta_pct": -0.25, "window": "7d", "vs_baseline": 140})
    push_context("category", cat_slug, 1, cat)
    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("No-offers merchant produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body doesn't reference non-existent offers", "offer" not in body.lower() or "suggest" in body.lower(),
              f"Body: {body[:100]}")
        check("Body references Pune or Kothrud", "pune" in body.lower() or "kothrud" in body.lower(),
              f"Body: {body[:100]}")


def test_fresh_very_high_performance():
    """Top-performing merchant — bot should celebrate, not warn."""
    mid = _id("m_high_perf")
    merchant = make_fresh_merchant(mid, "fresh_dentists_high",
        identity={"name": "Elite Dental Studio", "owner_first_name": "Kiran",
                  "city": "Bhubaneswar", "locality": "Jaydev Vihar", "languages": ["en"]},
        performance={"views": 800, "calls": 120, "ctr": 0.065,
                     "delta_7d": {"views_pct": 0.28, "calls_pct": 0.22}},
        signals=["above_peer: high_engagement"])
    trigger = make_fresh_trigger(_id("trg_spike_high"), "perf_spike", mid, urgency=3,
        payload={"metric": "calls", "delta_pct": 0.22, "window": "7d",
                 "likely_driver": "positive_reviews", "vs_baseline": 100})

    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("High perf spike produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions good news/positive", "good" in body.lower() or "great" in body.lower() or "positive" in body.lower() or "up" in body.lower(),
              f"Body: {body[:100]}")
        check("Body references Bhubaneswar or Jaydev Vihar", "bhubaneswar" in body.lower() or "jaydev" in body.lower(),
              f"Body: {body[:100]}")


def test_fresh_dormant_long_time():
    """Dormant merchant for 90 days with signals."""
    mid = _id("m_dormant_long")
    merchant = make_fresh_merchant(mid, "fresh_salons_dormant",
        identity={"name": "Glamour Salon", "owner_first_name": "Ritu",
                  "city": "Indore", "locality": "Rajwada", "languages": ["en"]},
        performance={"views": 50, "calls": 5, "ctr": 0.01},
        signals=["ctr_below_peer", "unverified_gbp"])
    trigger = make_fresh_trigger(_id("trg_dormant"), "dormant_with_vera", mid, urgency=2,
        payload={"days_since_last_merchant_message": 90, "last_topic": "offer_refresh"})

    push_context("merchant", mid, 1, merchant)
    push_context("trigger", trigger["id"], 1, trigger)

    code, data = tick_for(mid, [trigger["id"]])
    check("Long dormant produces action", code == 200 and len(data.get("actions", [])) >= 1,
          f"Code: {code}")
    if data.get("actions"):
        body = data["actions"][0].get("body", "")
        check("Body mentions 90 days", "90" in body,
              f"Body: {body[:100]}")
        check("Body references Indore or Rajwada", "indore" in body.lower() or "rajwada" in body.lower(),
              f"Body: {body[:100]}")


# =============================================================================
# RUN ALL FRESH SCENARIO TESTS
# =============================================================================

if __name__ == "__main__":
    print(f"\n{'='*70}")
    print(f"           Fresh Scenario Test — Simulating Actual Judge")
    print(f"{'='*70}")
    print(f"\nBot URL: {BOT_URL}")
    print(f"These tests use entirely NEW data the bot has never seen.\n")

    # Run all fresh scenario tests
    test_fresh_dentist_with_extreme_dip()
    test_fresh_unknown_category()
    test_fresh_customer_with_partial_consent()
    test_fresh_digest_with_novel_research()
    test_fresh_competitor_far_away()
    test_fresh_gbp_unverified_huge_uplift()
    test_fresh_seasonal_with_zero_performance()
    test_fresh_multi_trigger_urgency_sorting()
    test_fresh_reply_to_unseen_trigger()
    test_fresh_customer_lapsed_with_high_visits()
    test_fresh_supply_alert_with_batches()
    test_fresh_perf_spike_with_driver()
    test_fresh_regulation_change_with_deadline()
    test_fresh_reply_hinglish()
    test_fresh_no_offers_at_all()
    test_fresh_very_high_performance()
    test_fresh_dormant_long_time()

    print(f"\n{'='*70}")
    print(f"                     FRESH SCENARIO RESULTS")
    print(f"{'='*70}")
    print(f"\n  Total: {PASS}/{TOTAL} passed")
    if FAIL > 0:
        print(f"  {FAIL} test(s) failed.")
    else:
        print(f"  All fresh scenario tests passed!")

    sys.exit(0 if FAIL == 0 else 1)
