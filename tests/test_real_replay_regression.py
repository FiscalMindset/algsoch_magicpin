import time
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def test_real_score_replay_regression():
    """
    Covers the evaluator failure pattern from the 58/100 report:
    - injected context must be accepted
    - payload-linked regulation trigger must produce a non-empty, grounded action
    - X-ray setup reply must stay on the regulation branch
    - customer-style slot pick must not fall into merchant campaign approval flow
    - WhatsApp Business auto-reply must end immediately
    """
    run_id = int(time.time() * 1000)
    category_id = f"real_replay_dentists_{run_id}"
    merchant_id = f"real_replay_merchant_{run_id}"
    trigger_id = f"real_replay_trigger_{run_id}"

    category = {
        "slug": category_id,
        "offer_catalog": [{"title": "Dental Cleaning @ Rs 299", "value": "299"}],
        "voice": {
            "tone": "peer_clinical",
            "taboos": ["cure", "guaranteed"],
        },
        "peer_stats": {"avg_ctr": 0.03, "avg_views_30d": 1600},
        "digest": [
            {
                "id": "dci_radiograph_2026",
                "kind": "regulation",
                "title": "DCI radiograph dose limit revised",
                "source": "DCI circular 2026",
                "actionable": "Audit old D-speed film units and document exposure settings",
            }
        ],
    }
    merchant = {
        "merchant_id": merchant_id,
        "category_slug": category_id,
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
        "offers": [{"id": "offer_cleaning", "title": "Dental Cleaning @ Rs 299", "status": "active"}],
        "customer_aggregate": {"total_unique_ytd": 540, "lapsed_180d_plus": 78},
        "signals": ["stale_posts:22d", "ctr_below_peer_median", "high_risk_adult_cohort"],
    }
    trigger = {
        "id": trigger_id,
        "scope": "merchant",
        "kind": "regulation_change",
        "source": "external",
        # Put merchant_id inside payload as post-submission injected triggers may do.
        "payload": {
            "merchant_id": merchant_id,
            "category": category_id,
            "top_item_id": "dci_radiograph_2026",
            "deadline_iso": "2026-12-15",
        },
        "urgency": 5,
        "suppression_key": f"real_replay:{run_id}",
        "expires_at": "2026-12-15T00:00:00Z",
    }

    with TestClient(app) as client:
        for scope, context_id, payload in [
            ("category", category_id, category),
            ("merchant", merchant_id, merchant),
            ("trigger", trigger_id, trigger),
        ]:
            response = client.post(
                "/v1/context",
                json={
                    "scope": scope,
                    "context_id": context_id,
                    "version": run_id,
                    "payload": payload,
                    "delivered_at": _now(),
                },
            )
            assert response.status_code == 200
            assert response.json()["accepted"] is True

        tick = client.post(
            "/v1/tick",
            json={"now": "2026-04-26T10:30:00Z", "available_triggers": [trigger_id]},
        )
        assert tick.status_code == 200
        actions = tick.json()["actions"]
        assert len(actions) == 1
        body = actions[0]["body"].lower()
        assert "dci" in body or "radiograph" in body
        assert "2026-12-15" in body
        assert "d-speed" in body or "audit" in body

        conv_id = actions[0]["conversation_id"]
        merchant_reply = client.post(
            "/v1/reply",
            json={
                "conversation_id": conv_id,
                "merchant_id": merchant_id,
                "customer_id": None,
                "from_role": "merchant",
                "message": "Got it doc - need help auditing my X-ray setup. We have an old D-speed film unit.",
                "received_at": _now(),
                "turn_number": 2,
            },
        )
        assert merchant_reply.status_code == 200
        merchant_reply_json = merchant_reply.json()
        assert merchant_reply_json["action"] == "send"
        merchant_body = merchant_reply_json["body"].lower()
        assert "audit" in merchant_body or "compliance" in merchant_body
        assert "x-ray" in merchant_body or "film" in merchant_body or "d-speed" in merchant_body

        slot_reply = client.post(
            "/v1/reply",
            json={
                "conversation_id": f"real_replay_slot_{run_id}",
                "merchant_id": merchant_id,
                "customer_id": None,
                "from_role": "merchant",
                "message": "Yes please book me for Wed 5 Nov, 6pm.",
                "received_at": _now(),
                "turn_number": 1,
            },
        )
        assert slot_reply.status_code == 200
        slot_json = slot_reply.json()
        assert slot_json["action"] == "send"
        assert "confirmed" in slot_json["body"].lower()
        assert "whatsapp message" not in slot_json["body"].lower()
        assert "google post" not in slot_json["body"].lower()

        auto_reply = client.post(
            "/v1/reply",
            json={
                "conversation_id": f"real_replay_auto_{run_id}",
                "merchant_id": merchant_id,
                "customer_id": None,
                "from_role": "merchant",
                "message": "Thank you for contacting us. We will get back to you shortly.",
                "received_at": _now(),
                "turn_number": 1,
            },
        )
        assert auto_reply.status_code == 200
        assert auto_reply.json()["action"] == "end"
