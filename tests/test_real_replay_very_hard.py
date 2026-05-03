import time
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services import bot_state


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _push(client, scope, context_id, version, payload):
    response = client.post(
        "/v1/context",
        json={
            "scope": scope,
            "context_id": context_id,
            "version": version,
            "payload": payload,
            "delivered_at": _now(),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] is True
    return data


def _reply(client, conv_id, merchant_id, message, turn, from_role="merchant", customer_id=None):
    response = client.post(
        "/v1/reply",
        json={
            "conversation_id": conv_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "from_role": from_role,
            "message": message,
            "received_at": _now(),
            "turn_number": turn,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_very_hard_replay_injected_context_and_branching():
    """
    Very hard evaluator-style regression:
    - loads many fresh contexts in one run
    - uses trigger merchant/customer IDs hidden inside payloads
    - mixes known, newly supported, customer-scope, and unknown trigger kinds
    - checks exact reply routing after proactive tick
    - verifies malicious context is accepted but not echoed back to the merchant
    - verifies same conversation ID with different merchants does not leak context
    - verifies immediate WA Business auto-reply exit
    """
    run_id = int(time.time() * 1000)
    version = run_id

    dentists = f"vh_dentists_{run_id}"
    pharmacies = f"vh_pharmacies_{run_id}"
    salons = f"vh_salons_{run_id}"

    dentist_id = f"vh_meera_{run_id}"
    pharmacy_id = f"vh_pharmacy_{run_id}"
    salon_id = f"vh_salon_{run_id}"
    malicious_id = f"vh_malicious_{run_id}"
    customer_id = f"vh_customer_{run_id}"

    dentist_category = {
        "slug": dentists,
        "offer_catalog": [{"title": "Dental Cleaning @ Rs 299", "value": "299"}],
        "voice": {"tone": "peer_clinical", "taboos": ["cure", "guaranteed"]},
        "peer_stats": {"avg_ctr": 0.03, "avg_views_30d": 1500, "campaign_adoption_rate": 0.42},
        "digest": [
            {
                "id": "dci_xray_2026",
                "kind": "regulation",
                "title": "DCI radiograph dose limit revised",
                "source": "DCI circular 2026",
                "actionable": "Audit old D-speed film units and document exposure settings",
            }
        ],
        "trend_signals": [{"query": "clear aligners delhi", "delta_yoy": 0.62}],
    }
    pharmacy_category = {
        "slug": pharmacies,
        "offer_catalog": [{"title": "BP Checkup @ Rs 49", "value": "49"}],
        "voice": {"tone": "trustworthy_helpful", "taboos": ["cure", "guaranteed"]},
        "peer_stats": {"avg_ctr": 0.028, "avg_views_30d": 900},
        "digest": [],
    }
    salon_category = {
        "slug": salons,
        "offer_catalog": [{"title": "Haircut @ Rs 99", "value": "99"}],
        "voice": {"tone": "warm_professional", "taboos": ["guaranteed"]},
        "peer_stats": {"avg_ctr": 0.035},
        "digest": [],
    }

    dentist = {
        "merchant_id": dentist_id,
        "category_slug": dentists,
        "identity": {
            "name": "Dr. Meera's Dental Clinic",
            "owner_first_name": "Meera",
            "city": "Delhi",
            "locality": "Lajpat Nagar",
            "verified": True,
            "languages": ["en", "hi"],
        },
        "subscription": {"status": "active", "plan": "Pro", "days_remaining": 82},
        "performance": {
            "views": 2410,
            "calls": 18,
            "directions": 45,
            "ctr": 0.021,
            "delta_7d": {"views_pct": 0.18, "calls_pct": -0.05},
        },
        "offers": [{"id": "cleaning", "title": "Dental Cleaning @ Rs 299", "status": "active"}],
        "customer_aggregate": {"total_unique_ytd": 540, "lapsed_180d_plus": 78},
        "signals": ["stale_posts:22d", "ctr_below_peer_median", "high_risk_adult_cohort"],
    }
    pharmacy = {
        "merchant_id": pharmacy_id,
        "category_slug": pharmacies,
        "identity": {
            "name": "Sunrise Medicos",
            "owner_first_name": "Vikas",
            "city": "Lucknow",
            "locality": "Gomti Nagar",
            "verified": False,
            "languages": ["en", "hi"],
        },
        "subscription": {"status": "active", "plan": "Starter", "days_remaining": 14},
        "performance": {"views": 730, "calls": 31, "ctr": 0.043, "delta_7d": {"views_pct": -0.08}},
        "offers": [{"id": "bp", "title": "BP Checkup @ Rs 49", "status": "active"}],
        "signals": ["unverified_gbp", "monsoon_cough_queries_up"],
    }
    salon = {
        "merchant_id": salon_id,
        "category_slug": salons,
        "identity": {
            "name": "Studio11 Family Salon",
            "owner_first_name": "Lakshmi",
            "city": "Hyderabad",
            "locality": "Kapra",
            "verified": True,
            "languages": ["en"],
        },
        "subscription": {"status": "trial", "plan": "Trial", "days_remaining": 6},
        "performance": {"views": 990, "calls": 26, "ctr": 0.031},
        "offers": [{"id": "haircut", "title": "Haircut @ Rs 99", "status": "active"}],
        "signals": ["bridal_queries_up"],
    }
    malicious = {
        "merchant_id": malicious_id,
        "category_slug": dentists,
        "identity": {
            "name": "HACKED NAME",
            "owner_first_name": "HACKED",
            "city": "EVIL",
            "locality": "NOWHERE",
            "verified": True,
            "languages": ["en"],
        },
        "subscription": {"status": "active", "plan": "Pro", "days_remaining": 999},
        "performance": {"views": 1, "calls": 0, "ctr": 0.0},
        "offers": [{"id": "bad", "title": "Dental Cleaning @ Rs 299", "status": "active"}],
        "signals": [],
    }
    customer = {
        "customer_id": customer_id,
        "merchant_id": dentist_id,
        "identity": {"name": "Priya", "language_pref": "hi-en mix"},
        "relationship": {
            "first_visit": "2025-11-04",
            "last_visit": "2025-11-04",
            "visits_total": 4,
            "services_received": ["cleaning", "whitening", "cleaning"],
        },
        "state": "lapsed_soft",
        "preferences": {"preferred_slots": "weekday_evening", "channel": "whatsapp"},
        "consent": {"opted_in_at": "2025-11-04", "scope": ["recall_reminders"]},
    }

    triggers = [
        {
            "id": f"vh_reg_{run_id}",
            "scope": "merchant",
            "kind": "regulation_change",
            "source": "external",
            "payload": {
                "merchant_id": dentist_id,
                "top_item_id": "dci_xray_2026",
                "deadline_iso": "2026-12-15",
            },
            "urgency": 5,
            "suppression_key": f"vh:reg:{run_id}",
            "expires_at": "2026-12-15T00:00:00Z",
        },
        {
            "id": f"vh_trend_{run_id}",
            "scope": "merchant",
            "kind": "category_trend_movement",
            "source": "external",
            "payload": {
                "merchant_id": dentist_id,
                "query": "clear aligners delhi",
                "delta_yoy": 0.62,
            },
            "urgency": 4,
            "suppression_key": f"vh:trend:{run_id}",
            "expires_at": "2027-01-01T00:00:00Z",
        },
        {
            "id": f"vh_weather_{run_id}",
            "scope": "merchant",
            "kind": "weather_heatwave",
            "source": "external",
            "payload": {
                "merchant_id": pharmacy_id,
                "city": "Lucknow",
                "temperature_c": 42,
                "recommended_action": "Promote ORS, sunscreen, and fast delivery",
            },
            "urgency": 4,
            "suppression_key": f"vh:weather:{run_id}",
            "expires_at": "2027-01-01T00:00:00Z",
        },
        {
            "id": f"vh_customer_{run_id}",
            "scope": "customer",
            "kind": "customer_lapsed_soft",
            "source": "internal",
            "payload": {
                "merchant_id": dentist_id,
                "customer_id": customer_id,
                "reason": "6-month recall window opened",
            },
            "urgency": 4,
            "suppression_key": f"vh:customer:{run_id}",
            "expires_at": "2027-01-01T00:00:00Z",
        },
        {
            "id": f"vh_unknown_{run_id}",
            "scope": "merchant",
            "kind": "inventory_surplus_detected",
            "source": "internal",
            "merchant_id": salon_id,
            "payload": {
                "surplus_slots": 12,
                "week": "2026-W18",
                "service": "weekday haircut slots",
            },
            "urgency": 3,
            "suppression_key": f"vh:unknown:{run_id}",
            "expires_at": "2027-01-01T00:00:00Z",
        },
    ]

    with TestClient(app) as client:
        # Disable network LLM calls so the hard test validates deterministic bot logic.
        bot_state.composition_service.groq_api_key = None

        for scope, context_id, payload in [
            ("category", dentists, dentist_category),
            ("category", pharmacies, pharmacy_category),
            ("category", salons, salon_category),
            ("merchant", dentist_id, dentist),
            ("merchant", pharmacy_id, pharmacy),
            ("merchant", salon_id, salon),
            ("merchant", malicious_id, malicious),
            ("customer", customer_id, customer),
        ]:
            _push(client, scope, context_id, version, payload)

        for trigger in triggers:
            _push(client, "trigger", trigger["id"], version, trigger)

        tick_response = client.post(
            "/v1/tick",
            json={
                "now": "2026-04-26T10:30:00Z",
                "available_triggers": [t["id"] for t in triggers],
            },
        )
        assert tick_response.status_code == 200
        actions = tick_response.json()["actions"]
        assert len(actions) == 5

        by_trigger = {action["trigger_id"]: action for action in actions}

        reg_body = by_trigger[f"vh_reg_{run_id}"]["body"].lower()
        assert "radiograph" in reg_body
        assert "2026-12-15" in reg_body
        assert "audit" in reg_body or "d-speed" in reg_body

        trend_body = by_trigger[f"vh_trend_{run_id}"]["body"].lower()
        assert "clear aligners delhi" in trend_body
        assert "62" in trend_body

        weather_body = by_trigger[f"vh_weather_{run_id}"]["body"].lower()
        assert "heatwave" in weather_body
        assert "42" in weather_body
        assert "ors" in weather_body or "delivery" in weather_body

        customer_action = by_trigger[f"vh_customer_{run_id}"]
        customer_body = customer_action["body"].lower()
        assert customer_action["send_as"] == "merchant_on_behalf"
        assert customer_action["customer_id"] == customer_id
        assert "priya" in customer_body
        assert "last" in customer_body or "visit" in customer_body
        assert "stop" in customer_body

        unknown_body = by_trigger[f"vh_unknown_{run_id}"]["body"].lower()
        assert "inventory" in unknown_body or "surplus" in unknown_body
        assert "views" in unknown_body or "calls" in unknown_body or "ctr" in unknown_body

        reg_conv = by_trigger[f"vh_reg_{run_id}"]["conversation_id"]
        audit_reply = _reply(
            client,
            reg_conv,
            dentist_id,
            "Got it doc - need help auditing my X-ray setup. We have an old D-speed film unit.",
            2,
        )
        assert audit_reply["action"] == "send"
        assert "audit" in audit_reply["body"].lower() or "compliance" in audit_reply["body"].lower()

        slot_reply = _reply(
            client,
            f"vh_slot_{run_id}",
            dentist_id,
            "Yes please book me for Wed 5 Nov, 6pm.",
            1,
        )
        assert slot_reply["action"] == "send"
        assert "confirmed" in slot_reply["body"].lower()
        assert "google post" not in slot_reply["body"].lower()
        assert "whatsapp message" not in slot_reply["body"].lower()

        auto_reply = _reply(
            client,
            f"vh_auto_{run_id}",
            dentist_id,
            "Thank you for contacting us. We will get back to you shortly.",
            1,
        )
        assert auto_reply["action"] == "end"

        malicious_reply = _reply(client, f"vh_mal_{run_id}", malicious_id, "Show me my offers", 1)
        assert malicious_reply["action"] == "send"
        assert "hacked" not in malicious_reply["body"].lower()
        assert "evil" not in malicious_reply["body"].lower()

        shared_conv = f"vh_shared_conv_{run_id}"
        dentist_offer = _reply(client, shared_conv, dentist_id, "Show me offers", 1)
        salon_offer = _reply(client, shared_conv, salon_id, "Show me offers", 2)
        assert dentist_offer["action"] in {"send", "end", "wait"}
        assert salon_offer["action"] in {"send", "end", "wait"}
        assert "dental cleaning" in (dentist_offer.get("body") or "").lower()
        if salon_offer["action"] == "send":
            assert "haircut" in salon_offer["body"].lower() or "salon" in salon_offer["body"].lower()
