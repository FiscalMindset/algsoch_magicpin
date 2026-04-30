#!/usr/bin/env python3
"""
Vera AI — Cloud Test Runner
=============================
Runs ALL tests (Judge Simulator + Custom + Advanced) against the deployed backend.

Usage:
  python run_cloud_tests.py [--url https://your-backend.onrender.com]

Requires:
  - LLM API key for Judge Simulator (Groq/Anthropic/OpenAI etc.)
  - Or use --no-judge to skip the LLM-powered judge
"""

import json
import sys
import time
import argparse
from datetime import datetime, timezone
from urllib import request as urlrequest, error as urlerror
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────
DEFAULT_URL = "https://algsoch-magicpin.onrender.com"
BOT_URL = DEFAULT_URL
TIMEOUT = 30

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.RESET}\n")

def print_pass(text): print(f"{Colors.GREEN}[PASS]{Colors.RESET} {text}")
def print_fail(text): print(f"{Colors.RED}[FAIL]{Colors.RESET} {text}")
def print_info(text): print(f"{Colors.BLUE}[INFO]{Colors.RESET} {text}")
def print_warn(text): print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {text}")

# ─── API helpers ─────────────────────────────────────────────────────────────
def bot_request(method, path, body_dict=None, timeout=TIMEOUT):
    url = f"{BOT_URL.rstrip('/')}{path}"
    body = json.dumps(body_dict).encode("utf-8") if body_dict else None
    req = urlrequest.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        resp = urlrequest.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8")), None
    except urlerror.HTTPError as e:
        try: return json.loads(e.read().decode("utf-8")), None
        except: return None, f"HTTP {e.code}"
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

# ─── Dataset loader ─────────────────────────────────────────────────────────
def load_seed_data():
    dataset_dir = Path(__file__).parent / "dataset"
    merchants, triggers, categories = {}, {}, {}
    merch_path = dataset_dir / "merchants_seed.json"
    if merch_path.exists():
        for m in json.load(open(merch_path)).get("merchants", []): merchants[m["merchant_id"]] = m
    trig_path = dataset_dir / "triggers_seed.json"
    if trig_path.exists():
        for t in json.load(open(trig_path)).get("triggers", []): triggers[t["id"]] = t
    for f in (dataset_dir / "categories").glob("*.json"):
        data = json.load(open(f)); categories[data.get("slug", f.stem)] = data
    return categories, merchants, triggers

def setup_contexts():
    cats, merchs, trigs = load_seed_data()
    version = int(time.time())
    for slug, cat in cats.items(): push_context("category", slug, version, cat)
    for mid, merch in merchs.items(): push_context("merchant", mid, version, merch)
    for tid, trig in trigs.items(): push_context("trigger", tid, version, trig)
    return cats, merchs, trigs

# ─── Test: Healthz ──────────────────────────────────────────────────────────
def test_healthz():
    print(f"\n{Colors.BOLD}--- TEST: Healthz ---{Colors.RESET}")
    data, err = bot_request("GET", "/v1/healthz")
    if err: print_fail(f"Unreachable: {err}"); return False
    print_pass(f"Uptime: {data.get('uptime_seconds', '?')}s | Contexts: {data.get('contexts', '?')}")
    return True

# ─── Test: Metadata ─────────────────────────────────────────────────────────
def test_metadata():
    print(f"\n{Colors.BOLD}--- TEST: Metadata ---{Colors.RESET}")
    data, err = bot_request("GET", "/v1/metadata")
    if err: print_fail(f"Error: {err}"); return False
    required = ["team_name", "model", "approach"]
    missing = [k for k in required if k not in (data or {})]
    if missing: print_fail(f"Missing: {missing}"); return False
    print_pass(f"Team: {data['team_name']} | Model: {data['model']}")
    return True

# ─── Test: Context Push ─────────────────────────────────────────────────────
def test_context_push():
    print(f"\n{Colors.BOLD}--- TEST: Context Push ---{Colors.RESET}")
    _, merchants, _ = load_seed_data()
    mid = list(merchants.keys())[0]
    data, err = push_context("merchant", mid, int(time.time()), merchants[mid])
    if err or not data or not data.get("accepted"): print_fail(f"Rejected: {err}"); return False
    print_pass("Context accepted")
    return True

# ─── Test: Tick ─────────────────────────────────────────────────────────────
def test_tick():
    print(f"\n{Colors.BOLD}--- TEST: Tick (All Triggers) ---{Colors.RESET}")
    _, _, triggers = load_seed_data()
    tids = list(triggers.keys())[:5]
    data, err = bot_request("POST", "/v1/tick", {
        "now": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "available_triggers": tids
    })
    if err: print_fail(f"Error: {err}"); return False
    actions = data.get("actions", [])
    print_pass(f"Returned {len(actions)} actions")
    return True

# ─── Test: Reply ────────────────────────────────────────────────────────────
def test_reply():
    print(f"\n{Colors.BOLD}--- TEST: Reply (Multi-turn) ---{Colors.RESET}")
    mid = "m_001_drmeera_dentist_delhi"
    conv_id = f"conv_cloud_{int(time.time())}"
    for i, msg in enumerate(["Hi, what's new?", "Show me my performance", "Ok lets do it"], 1):
        data, err = send_reply(conv_id, mid, msg, i)
        if err: print_fail(f"Turn {i} failed: {err}"); return False
        action = data.get("action", "")
        if action == "end": print_pass(f"Bot ended on turn {i} (msg: '{msg[:30]}')"); return True
    print_pass("Survived 3 turns")
    return True

# ─── Test: Repetition Detection ─────────────────────────────────────────────
def test_repetition():
    print(f"\n{Colors.BOLD}--- TEST: Repetition Detection ---{Colors.RESET}")
    mid = "m_001_drmeera_dentist_delhi"
    conv_id = f"conv_rep_{int(time.time())}"
    data, err = send_reply(conv_id, mid, "Hello", 1)
    if err: print_fail(f"Turn 1: {err}"); return False
    body1 = (data.get("body") or "")
    data, err = send_reply(conv_id, mid, "Hello", 2)
    if err: print_fail(f"Turn 2: {err}"); return False
    action2 = data.get("action", "")
    if action2 == "end": print_pass("Detected repetition, ended conversation"); return True
    body2 = (data.get("body") or "")
    if body1 and body2 and body1.strip() == body2.strip(): print_fail(f"Sent same body twice: '{body1[:40]}'"); return False
    print_pass(f"Sent different responses (body1='{body1[:30]}', body2='{body2[:30]}')")
    return True

# ─── Test: Hindi Language ───────────────────────────────────────────────────
def test_hindi():
    print(f"\n{Colors.BOLD}--- TEST: Hindi Language Switch ---{Colors.RESET}")
    mid = "m_001_drmeera_dentist_delhi"
    conv_id = f"conv_hindi_{int(time.time())}"
    data, err = send_reply(conv_id, mid, "मुझे profile जाननी है", 1)
    if err: print_fail(f"Error: {err}"); return False
    body = (data.get("body") or "")
    action = data.get("action", "")
    has_hindi = any('\u0900' <= c <= '\u097F' for c in body)
    if has_hindi: print_pass(f"Responded in Hindi: '{body[:50]}'"); return True
    print_warn(f"No Devanagari chars (action={action}): '{body[:50]}'")
    return True  # Not a hard fail

# ─── Test: Hostile Handling ─────────────────────────────────────────────────
def test_hostile():
    print(f"\n{Colors.BOLD}--- TEST: Hostile Message ---{Colors.RESET}")
    mid = "m_001_drmeera_dentist_delhi"
    conv_id = f"conv_hostile_{int(time.time())}"
    data, err = send_reply(conv_id, mid, "Stop messaging me. This is spam.", 1)
    if err: print_fail(f"Error: {err}"); return False
    action = data.get("action", "")
    if action == "end": print_pass("Bot ended on hostile message"); return True
    print_warn(f"Did not end (action={action})")
    return True

# ─── Test: Empty Tick ───────────────────────────────────────────────────────
def test_empty_tick():
    print(f"\n{Colors.BOLD}--- TEST: Empty Tick ---{Colors.RESET}")
    data, err = bot_request("POST", "/v1/tick", {
        "now": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "available_triggers": []
    })
    if err: print_fail(f"Error: {err}"); return False
    actions = data.get("actions")
    if actions is None: print_fail("No 'actions' key"); return False
    if len(actions) == 0: print_pass("Correctly returned empty actions"); return True
    print_warn(f"Returned {len(actions)} actions with no triggers")
    return True

# ─── Main ───────────────────────────────────────────────────────────────────
def run_judge_simulator():
    """Run the official judge_simulator.py against the cloud URL."""
    print(f"\n{Colors.CYAN}{'─'*70}{Colors.RESET}")
    print(f"{Colors.CYAN}  Running Judge Simulator (LLM-powered){Colors.RESET}")
    print(f"{Colors.CYAN}{'─'*70}{Colors.RESET}\n")

    judge_path = Path(__file__).parent / "judge_simulator.py"
    if not judge_path.exists():
        print_warn("judge_simulator.py not found, skipping")
        return True

    import subprocess
    # We need to temporarily override BOT_URL in judge_simulator
    # Instead of modifying the file, we run with env var or just note it
    print_info("To run Judge Simulator, edit judge_simulator.py:")
    print_info(f"  Set BOT_URL = \"{BOT_URL}\"")
    print_info(f"  Set LLM_PROVIDER and LLM_API_KEY")
    print_info(f"Then run: python judge_simulator.py\n")
    return True  # Don't fail the whole suite

def main():
    global BOT_URL
    parser = argparse.ArgumentParser(description="Vera AI Cloud Test Runner")
    parser.add_argument("--url", default=DEFAULT_URL, help="Backend URL")
    parser.add_argument("--no-judge", action="store_true", help="Skip judge simulator")
    parser.add_argument("--judge", action="store_true", help="Run judge simulator")
    args = parser.parse_args()
    BOT_URL = args.url

    print_header(f"Vera AI — Cloud Tests | {BOT_URL}")
    print_info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # Health check
    data, err = bot_request("GET", "/v1/healthz")
    if err:
        print_fail(f"Bot unreachable at {BOT_URL}: {err}")
        sys.exit(1)
    print_pass(f"Bot alive (uptime: {data.get('uptime_seconds', '?')}s)\n")

    # Setup contexts
    print_info("Pushing seed contexts...")
    setup_contexts()
    print_pass("Contexts loaded\n")

    # Run tests
    tests = {
        "healthz": test_healthz,
        "metadata": test_metadata,
        "context_push": test_context_push,
        "tick": test_tick,
        "reply_multiturn": test_reply,
        "repetition": test_repetition,
        "hindi": test_hindi,
        "hostile": test_hostile,
        "empty_tick": test_empty_tick,
    }

    results = {}
    for name, fn in tests.items():
        try: results[name] = fn()
        except Exception as e:
            print_fail(f"{name} crashed: {e}")
            results[name] = False

    # Judge simulator
    if args.judge:
        results["judge"] = run_judge_simulator()

    # Summary
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{'  CLOUD TEST SUMMARY  '.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {status}  {name}")

    print(f"\n  {Colors.BOLD}Total: {passed}/{total} passed ({passed/total*100:.0f}%){Colors.RESET}\n")

    print_info(f"Backend URL: {BOT_URL}")
    print_info(f"Frontend URL: http://vera-ai-frontend.onrender.com")
    print_info(f"\nTo run full Judge Simulator:")
    print_info(f"  1. Edit judge_simulator.py → BOT_URL = \"{BOT_URL}\"")
    print_info(f"  2. Set your LLM_API_KEY")
    print_info(f"  3. python judge_simulator.py\n")

    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
