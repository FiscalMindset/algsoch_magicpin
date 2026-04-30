#!/usr/bin/env python3
"""
Custom Stress Tests for Vera AI Bot
=====================================
These tests are DESIGNED TO FAIL initially. Each test targets a known weakness
or edge case that the bot should handle but likely won't on first pass.

Usage:
  python custom_stress_tests.py [--bot-url http://localhost:8000]

Each test prints PASS/FAIL and a detailed reason. The goal is to iterate
until all tests pass.
"""

import json
import sys
import time
import argparse
from datetime import datetime, timezone
from urllib import request as urlrequest, error as urlerror

BOT_URL = "http://localhost:8000"
TIMEOUT = 30

class Colors:
    HEADER = '\033[95m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def print_pass(text):
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} {text}")

def print_success(text):
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {text}")

def print_fail(text):
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {text}")

def print_info(text):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {text}")

def print_warn(text):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {text}")

def bot_request(method, path, body_dict=None, timeout=TIMEOUT):
    url = f"{BOT_URL.rstrip('/')}{path}"
    body = json.dumps(body_dict).encode("utf-8") if body_dict else None
    headers = {"Content-Type": "application/json"}
    req = urlrequest.Request(url, data=body, method=method, headers=headers)
    try:
        resp = urlrequest.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8")), None
    except urlerror.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8")), None
        except:
            return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)

def push_context(scope, cid, version, payload):
    return bot_request("POST", "/v1/context", {
        "scope": scope, "context_id": cid, "version": version,
        "payload": payload, "delivered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    })

def send_reply(conv_id, merchant_id, message, turn):
    return bot_request("POST", "/v1/reply", {
        "conversation_id": conv_id, "merchant_id": merchant_id, "customer_id": None,
        "from_role": "merchant", "message": message,
        "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "turn_number": turn
    })

def load_seed_data():
    """Load seed data from dataset directory."""
    import os
    from pathlib import Path
    dataset_dir = Path(__file__).parent / "dataset"
    merchants = {}
    triggers = {}
    categories = {}

    merch_path = dataset_dir / "merchants_seed.json"
    if merch_path.exists():
        data = json.load(open(merch_path))
        for m in data.get("merchants", []):
            merchants[m["merchant_id"]] = m

    trig_path = dataset_dir / "triggers_seed.json"
    if trig_path.exists():
        data = json.load(open(trig_path))
        for t in data.get("triggers", []):
            triggers[t["id"]] = t

    cat_dir = dataset_dir / "categories"
    if cat_dir.exists():
        for f in cat_dir.glob("*.json"):
            data = json.load(open(f))
            categories[data.get("slug", f.stem)] = data

    return categories, merchants, triggers

def setup_contexts():
    """Push base contexts to the bot."""
    categories, merchants, triggers = load_seed_data()
    version = int(time.time())

    for slug, cat in categories.items():
        push_context("category", slug, version, cat)

    for mid, merch in merchants.items():
        push_context("merchant", mid, version, merch)

    for tid, trig in triggers.items():
        push_context("trigger", tid, version, trig)

    return categories, merchants, triggers

# ============================================================================
# STRESS TESTS
# ============================================================================

def test_repetition_detection():
    """
    TEST: Bot should detect when it sends the SAME message body twice in same conversation.
    EXPECTED FAIL: Bot may not have anti-repetition logic in /v1/reply.
    """
    print(f"\n{Colors.BOLD}--- TEST: Repetition Detection ---{Colors.RESET}")

    categories, merchants, triggers = load_seed_data()
    mid = "m_001_drmeera_dentist_delhi"
    conv_id = "conv_repetition_test"

    # Send a neutral message first
    data, err = send_reply(conv_id, mid, "Hi, what's new?", 1)
    if err:
        print_fail(f"Bot unreachable: {err}")
        return False

    body1 = data.get("body", "") if data else ""

    # Send the exact same merchant reply again
    time.sleep(0.5)
    data, err = send_reply(conv_id, mid, "Hi, what's new?", 2)
    if err:
        print_fail(f"Bot unreachable: {err}")
        return False

    body2 = data.get("body", "") if data else ""
    action2 = data.get("action", "") if data else ""

    if action2 == "end":
        print_pass("Bot detected repetition and ended conversation")
        return True

    if body1 and body2 and body1.strip() == body2.strip():
        print_fail(f"Bot sent EXACT same response twice: '{body1[:50]}...'")
        return False

    print_warn(f"Bot sent different responses (body1='{body1[:30]}...', body2='{body2[:30]}...') - may not be detecting repetition")
    return False

def test_language_switch():
    """
    TEST: Merchant switches from English to Hindi mid-conversation.
    EXPECTED FAIL: Bot may not adapt language to merchant's switch.
    """
    print(f"\n{Colors.BOLD}--- TEST: Language Switch (EN → HI) ---{Colors.RESET}")

    categories, merchants, triggers = load_seed_data()
    mid = "m_001_drmeera_dentist_delhi"
    conv_id = "conv_lang_switch"

    # First message in English
    data, err = send_reply(conv_id, mid, "Hello, I want to know about my profile", 1)
    if err:
        print_fail(f"Bot unreachable: {err}")
        return False

    body1 = data.get("body", "") if data else ""

    # Switch to Hindi
    time.sleep(0.5)
    data, err = send_reply(conv_id, mid, "मुझे अपनी profile के बारे में जानना है", 2)
    if err:
        print_fail(f"Bot unreachable: {err}")
        return False

    body2 = data.get("body", "") if data else ""
    action2 = data.get("action", "") if data else ""

    if action2 == "end":
        print_warn("Bot ended conversation on Hindi input")
        return False

    # Check if body2 contains any Hindi characters or Hindi-friendly phrasing
    has_hindi = any('\u0900' <= c <= '\u097F' for c in body2)
    if has_hindi:
        print_pass(f"Bot adapted to Hindi: '{body2[:60]}...'")
        return True

    print_warn(f"Bot did NOT switch to Hindi (still English): '{body2[:60]}...'")
    print_info("IDEAL: Bot should respond in Hindi or Hindi-English mix")
    return False

def test_curveball_question():
    """
    TEST: Merchant asks completely unrelated question (e.g., about taxes).
    Bot should not give detailed GST advice.
    """
    print(f"\n{Colors.BOLD}--- TEST: Curveball Question (GST) ---{Colors.RESET}")

    categories, merchants, triggers = load_seed_data()
    mid = "m_001_drmeera_dentist_delhi"
    conv_id = "conv_curveball"

    data, err = send_reply(conv_id, mid, "Can you also help me file my GST returns?", 1)
    if err:
        print_fail(f"Bot unreachable: {err}")
        return False

    body = data.get("body", "").lower() if data else ""
    action = data.get("action", "") if data else ""

    if action == "end":
        print_warn("Bot ended conversation on curveball question")
        return True

    # Should NOT give detailed GST filing advice
    gst_advice_markers = ["file gst", "gst return", "itr form", "gst portal", "gst registration"]
    has_advice = any(m in body for m in gst_advice_markers)

    if has_advice:
        print_fail(f"Bot may be giving GST filing advice: '{body[:80]}...'")
        return False

    # Pass if bot responded at all (deflection or polite response)
    if len(body) > 10:
        print_pass(f"Bot handled curveball: '{body[:80]}...'")
        return True

    print_warn(f"Bot response too short: '{body[:50]}'")
    return False

def test_multiple_hostile_escalation():
    """
    TEST: Merchant gets progressively more hostile across turns.
    EXPECTED FAIL: Bot may not end conversation fast enough.
    """
    print(f"\n{Colors.BOLD}--- TEST: Escalating Hostility ---{Colors.RESET}")

    mid = "m_001_drmeera_dentist_delhi"
    conv_id = "conv_escalation"

    hostile_messages = [
        "I'm not interested.",
        "Stop bothering me!",
        "This is absolute waste of my time. Block me.",
        "I will report you for harassment.",
    ]

    ended_turn = None
    for i, msg in enumerate(hostile_messages, 1):
        data, err = send_reply(conv_id, mid, msg, i)
        if err:
            print_fail(f"Bot unreachable on turn {i}: {err}")
            return False

        action = data.get("action", "") if data else ""

        if action == "end":
            ended_turn = i
            break

    if ended_turn is None:
        print_fail(f"Bot never ended after {len(hostile_messages)} hostile messages")
        return False

    if ended_turn <= 2:
        print_pass(f"Bot ended on turn {ended_turn} (fast response to hostility)")
        return True

    print_warn(f"Bot ended on turn {ended_turn} (should have ended by turn 2)")
    return False

def test_empty_context_compose():
    """
    TEST: Tick with zero triggers should return empty actions, not crash.
    EXPECTED FAIL: Bot may return malformed response or crash.
    """
    print(f"\n{Colors.BOLD}--- TEST: Empty Tick (No Triggers) ---{Colors.RESET}")

    data, err = bot_request("POST", "/v1/tick", {
        "now": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "available_triggers": []
    })

    if err:
        print_fail(f"Bot error: {err}")
        return False

    actions = data.get("actions", None) if data else None

    if actions is None:
        print_fail("Bot returned no 'actions' key in response")
        return False

    if not isinstance(actions, list):
        print_fail(f"Bot returned non-list actions: {type(actions)}")
        return False

    if len(actions) == 0:
        print_pass("Bot correctly returned empty actions for no triggers")
        return True

    print_warn(f"Bot returned {len(actions)} actions with no triggers (may be ok if contexts warrant)")
    return True

def test_malformed_context_push():
    """
    TEST: Push malformed context — bot should reject (accepted=false or 4xx).
    """
    print(f"\n{Colors.BOLD}--- TEST: Malformed Context Push ---{Colors.RESET}")

    data, err = bot_request("POST", "/v1/context", {
        "scope": "invalid_scope",
        "context_id": "test",
        "version": 1,
        "payload": {},
        "delivered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    })

    if err and ("400" in err or "422" in err):
        print_pass(f"Bot rejected malformed context with HTTP error: {err}")
        return True

    # Check response body for rejection
    if data:
        accepted = data.get("accepted")
        detail = data.get("detail", {})
        if isinstance(detail, dict):
            accepted = detail.get("accepted", accepted)
        if accepted is False:
            print_pass("Bot correctly rejected malformed context (accepted=false)")
            return True

    print_fail(f"Bot accepted malformed context: {data}")
    return False

def test_concurrent_conversations():
    """
    TEST: Two merchants talking simultaneously — bot should keep contexts separate.
    EXPECTED FAIL: Bot may mix up merchant contexts.
    """
    print(f"\n{Colors.BOLD}--- TEST: Concurrent Conversations ---{Colors.RESET}")

    categories, merchants, _ = load_seed_data()
    mid1 = "m_001_drmeera_dentist_delhi"
    mid2 = "m_003_studio11_salon_hyderabad"

    conv1 = "conv_concurrent_1"
    conv2 = "conv_concurrent_2"

    # Start both conversations with specific merchant references
    data1, err1 = send_reply(conv1, mid1, "Tell me about my dental practice performance", 1)
    data2, err2 = send_reply(conv2, mid2, "Tell me about my salon performance", 1)

    if err1 or err2:
        print_fail(f"Bot errors: conv1={err1}, conv2={err2}")
        return False

    body1 = data1.get("body", "").lower() if data1 else ""
    body2 = data2.get("body", "").lower() if data2 else ""

    # Check responses are merchant-specific
    dentist_markers = ["dental", "dr", "meera", "teeth", "clinic"]
    salon_markers = ["salon", "studio", "hair", "lakshmi"]

    conv1_correct = any(m in body1 for m in dentist_markers)
    conv2_correct = any(m in body2 for m in salon_markers)

    if conv1_correct and conv2_correct:
        print_pass("Bot kept conversations separate with correct merchant context")
        return True

    if not conv1_correct:
        print_fail(f"Conv1 (dentist) got wrong context: '{body1[:60]}...'")
    if not conv2_correct:
        print_fail(f"Conv2 (salon) got wrong context: '{body2[:60]}...'")

    return False

def test_very_long_merchant_message():
    """
    TEST: Merchant sends a very long rambling message.
    EXPECTED FAIL: Bot may timeout or return garbage.
    """
    print(f"\n{Colors.BOLD}--- TEST: Very Long Merchant Message ---{Colors.RESET}")

    mid = "m_001_drmeera_dentist_delhi"
    conv_id = "conv_long_msg"

    long_msg = "Hi Vera, I've been thinking about my practice for a while now and I have so many questions. " * 20

    data, err = send_reply(conv_id, mid, long_msg, 1)
    if err:
        print_fail(f"Bot error: {err}")
        return False

    action = data.get("action", "") if data else ""
    body = data.get("body", "") if data else ""

    if action in ["send", "wait", "end"]:
        print_pass(f"Bot handled long message with action={action}")
        return True

    print_fail(f"Bot returned unexpected action: {action}")
    return False

def test_unicode_and_emoji():
    """
    TEST: Merchant sends message with Unicode and emoji.
    EXPECTED FAIL: Bot may crash on Unicode handling.
    """
    print(f"\n{Colors.BOLD}--- TEST: Unicode and Emoji ---{Colors.RESET}")

    mid = "m_001_drmeera_dentist_delhi"
    conv_id = "conv_unicode"

    data, err = send_reply(conv_id, mid, "🙏 Please help me with my profile 🦷✨", 1)
    if err:
        print_fail(f"Bot error: {err}")
        return False

    action = data.get("action", "") if data else ""

    if action in ["send", "wait", "end"]:
        print_pass(f"Bot handled Unicode/emoji with action={action}")
        return True

    print_fail(f"Bot failed on Unicode/emoji: {data}")
    return False

def test_commitment_without_prior_context():
    """
    TEST: Merchant says 'let's do it' without any prior conversation — should handle gracefully.
    EXPECTED FAIL: Bot may try to compose with missing context.
    """
    print(f"\n{Colors.BOLD}--- TEST: Commitment Without Prior Context ---{Colors.RESET}")

    mid = "m_005_pizzajunction_restaurant_delhi"
    conv_id = "conv_orphan_commitment"

    data, err = send_reply(conv_id, mid, "Ok let's do it! What's next?", 1)
    if err:
        print_fail(f"Bot error: {err}")
        return False

    action = data.get("action", "") if data else ""
    body = data.get("body", "") if data else ""

    if action == "end":
        print_warn("Bot ended conversation (may be correct for orphaned commitment)")
        return True

    if action == "send" and body:
        # Check it doesn't hallucinate
        if len(body) > 10:
            print_pass(f"Bot handled orphan commitment: '{body[:60]}...'")
            return True

    print_fail(f"Unexpected response: action={action}, body='{body[:50]}'")
    return False

def test_context_version_conflict():
    """
    TEST: Push stale version (lower than current) — should be rejected.
    EXPECTED FAIL: Bot may accept stale version.
    """
    print(f"\n{Colors.BOLD}--- TEST: Stale Version Rejection ---{Colors.RESET}")

    categories, merchants, _ = load_seed_data()
    mid = "m_001_drmeera_dentist_delhi"

    # Push fresh version
    push_context("merchant", mid, 999, merchants[mid])

    # Push stale version
    data, err = bot_request("POST", "/v1/context", {
        "scope": "merchant", "context_id": mid, "version": 100,
        "payload": merchants[mid],
        "delivered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    })

    if err:
        print_pass(f"Bot rejected stale version with error: {err}")
        return True

    accepted = data.get("accepted") if data else None
    if accepted is False:
        print_pass("Bot correctly rejected stale version")
        return True

    print_fail("Bot accepted stale version (should have rejected)")
    return False

def test_reply_after_conversation_ended():
    """
    TEST: Send reply to an already-ended conversation.
    EXPECTED FAIL: Bot may crash or send again.
    """
    print(f"\n{Colors.BOLD}--- TEST: Reply After Conversation Ended ---{Colors.RESET}")

    mid = "m_001_drmeera_dentist_delhi"
    conv_id = "conv_ended_reply"

    # End conversation with hostile message
    data, err = send_reply(conv_id, mid, "Stop messaging me. This is spam.", 1)
    if err:
        print_fail(f"Bot error: {err}")
        return False

    action1 = data.get("action", "") if data else ""
    if action1 != "end":
        print_fail(f"First message didn't end conversation: action={action1}")
        return False

    # Try to reply again
    time.sleep(0.5)
    data, err = send_reply(conv_id, mid, "Actually, never mind, tell me more", 2)
    if err:
        print_fail(f"Bot error on second reply: {err}")
        return False

    action2 = data.get("action", "") if data else ""

    # Should either end again or gracefully handle
    if action2 == "end":
        print_pass("Bot correctly kept conversation ended")
        return True

    print_warn(f"Bot responded after end: action={action2} (may be acceptable)")
    return True

def test_healthz_consistency():
    """
    TEST: Call healthz multiple times — should return consistent, increasing uptime.
    EXPECTED FAIL: Uptime may not increase or may reset.
    """
    print(f"\n{Colors.BOLD}--- TEST: Healthz Consistency ---{Colors.RESET}")

    data1, err1 = bot_request("GET", "/v1/healthz")
    time.sleep(2)
    data2, err2 = bot_request("GET", "/v1/healthz")

    if err1 or err2:
        print_fail(f"Healthz errors: {err1}, {err2}")
        return False

    uptime1 = data1.get("uptime_seconds", 0) if data1 else 0
    uptime2 = data2.get("uptime_seconds", 0) if data2 else 0

    if uptime2 >= uptime1:
        print_pass(f"Uptime increased: {uptime1}s → {uptime2}s")
        return True

    print_fail(f"Uptime decreased: {uptime1}s → {uptime2}s")
    return False

def test_metadata_presence():
    """
    TEST: Metadata endpoint should have all required fields.
    EXPECTED FAIL: May be missing fields.
    """
    print(f"\n{Colors.BOLD}--- TEST: Metadata Completeness ---{Colors.RESET}")

    data, err = bot_request("GET", "/v1/metadata")
    if err:
        print_fail(f"Bot error: {err}")
        return False

    required = ["team_name", "model", "approach", "contact_email"]
    missing = [k for k in required if k not in (data or {})]

    if not missing:
        print_pass(f"Metadata complete: team={data.get('team_name')}, model={data.get('model')}")
        return True

    print_fail(f"Missing metadata fields: {missing}")
    return False

# ============================================================================
# MAIN
# ============================================================================

def main():
    global BOT_URL
    parser = argparse.ArgumentParser(description="Vera AI Custom Stress Tests")
    parser.add_argument("--bot-url", default=BOT_URL, help="Bot URL (default: http://localhost:8000)")
    parser.add_argument("--test", default="all", help="Specific test to run (default: all)")
    args = parser.parse_args()

    BOT_URL = args.bot_url

    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'  Vera AI — Custom Stress Tests  '.center(70)}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.RESET}\n")

    print_info(f"Bot URL: {BOT_URL}")
    print_info("These tests are DESIGNED TO FAIL — iterate until they pass!\n")

    # Check bot is alive
    data, err = bot_request("GET", "/v1/healthz")
    if err:
        print_fail(f"Bot unreachable at {BOT_URL}: {err}")
        print_info("Start the bot first: cd backend && python main.py")
        sys.exit(1)
    print_success(f"Bot alive (uptime: {data.get('uptime_seconds', '?')}s)")

    # Setup contexts
    print_info("Loading and pushing contexts...")
    setup_contexts()
    print_success("Contexts loaded\n")

    tests = {
        "repetition": test_repetition_detection,
        "language": test_language_switch,
        "curveball": test_curveball_question,
        "hostility": test_multiple_hostile_escalation,
        "empty_tick": test_empty_context_compose,
        "malformed": test_malformed_context_push,
        "concurrent": test_concurrent_conversations,
        "long_msg": test_very_long_merchant_message,
        "unicode": test_unicode_and_emoji,
        "orphan_commitment": test_commitment_without_prior_context,
        "stale_version": test_context_version_conflict,
        "reply_after_end": test_reply_after_conversation_ended,
        "healthz": test_healthz_consistency,
        "metadata": test_metadata_presence,
    }

    if args.test != "all":
        if args.test not in tests:
            print_fail(f"Unknown test: {args.test}")
            print_info(f"Available: {', '.join(tests.keys())}")
            sys.exit(1)
        tests = {args.test: tests[args.test]}

    results = {}
    for name, fn in tests.items():
        try:
            results[name] = fn()
        except Exception as e:
            print_fail(f"{name} crashed: {e}")
            results[name] = False

    # Summary
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{'  TEST SUMMARY  '.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {status}  {name}")

    print(f"\n  {Colors.BOLD}Total: {passed}/{total} passed ({passed/total*100:.0f}%){Colors.RESET}")

    if passed < total:
        print(f"\n  {Colors.YELLOW}These tests failed — fix the bot and run again!{Colors.RESET}")

    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
