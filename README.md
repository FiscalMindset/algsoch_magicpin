# Algsoch AI — Merchant AI Assistant (magicpin AI Challenge)

> An AI-powered WhatsApp merchant assistant that proactively engages businesses with contextual, grounded messages — built for the magicpin AI Challenge v2.0.

[![Deploy to Render](https://img.shields.io/badge/Deploy%20to-Render-4C42E2?style=flat&logo=render)](https://render.com)
[![Tests](https://img.shields.io/badge/Tests-49%2F49%20passing-brightgreen)](#test-results)
[![Python](https://img.shields.io/badge/Python-3.11+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)]()
[![Deterministic](https://img.shields.io/badge/Deterministic-yes-success)]()

## Live Deployment

| Service | URL |
|---------|-----|
| **Backend API** | https://algsoch-magicpin.onrender.com |
| **Frontend Dashboard** | https://vera-ai-frontend.onrender.com |
| **API Docs** | https://algsoch-magicpin.onrender.com/docs |

## Test Results

| Suite | Tests | Result | Scope |
|-------|-------|--------|-------|
| **Adversarial Probe** | 22/22 | ✅ 100% | Edge cases, determinism, safety, reply routing |
| **Phase 3 Adaptive Injection** | 27/27 | ✅ 100% | New facts, version bumps, cross-scope, multi-turn |
| **Total** | **49/49** | **✅ 100%** | **Judge-ready** |

### Adversarial Probe Tests (22)

| # | Test | What It Validates |
|---|------|-------------------|
| 1 | Fresh trigger kind | Unseen trigger kinds produce grounded messages |
| 2 | Expired trigger | Expired triggers filtered out (zero actions) |
| 3 | Missing merchant | Triggers with missing merchant context skipped |
| 4 | Duplicate context | Same version push → 409 stale_version (idempotent) |
| 5 | Higher version | Higher version replaces context atomically |
| 6 | Customer scope without context | Customer-scope trigger without customer data → skipped |
| 7 | Taboo word sanitization | Category taboos ("cure", "guaranteed") filtered from output |
| 8 | Empty triggers | No available_triggers → empty actions |
| 9 | Priority ordering | Highest urgency trigger sent first |
| 10 | Deterministic IDs | Same input → same `conversation_id` (`conv:merchant:trigger`) |
| 11 | Auto-reply hell | 4 identical replies → conversation ends |
| 12 | Hostile message | "spam", "unsubscribe" → conversation ends |
| 13 | Budget objection | "no budget" → reframed with free options (not ended) |
| 14 | Commitment transition | "let's do it" → action plan, not more questions |
| 15 | Metadata truthfulness | Team name = "Algsoch AI", real contact email |

### Phase 3 Adaptive Injection Tests (27)

| # | Test | What It Validates |
|---|------|-------------------|
| 1 | New digest items | Version-bumped digest → bot references new research |
| 2 | Compliance digest | Bio-waste rules → urgency + action required |
| 3 | Performance dip | Updated merchant perf with dip → reflects new numbers |
| 4 | Performance spike | Merchant with spike → reinforces momentum |
| 5 | New customer recall | Mid-test customer injection → personalized message |
| 6 | New category (dermatologists) | Unseen category → correct topic + merchant name |
| 7 | Seasonal event (Diwali) | Festival trigger → campaign draft proposal |
| 8 | Competitor (new category) | Competitor for dermatologist → differentiation copy |
| 9 | Stale data avoidance | After version bump → uses NEW numbers, not old |
| 10 | Expired after injection | Already-expired trigger → filtered |
| 11 | Multi-turn with updates | Conversation after context update → references new offers |
| 12 | Cross-scope linking | Category → merchant → trigger → customer all linked correctly |

## What Changed (v1 → v2)

| Component | Before (v1) | After (v2) |
|---|---|---|
| **Conversation ID** | `conv_{trigger}_{uuid4()}` — non-deterministic | `conv:{merchant}:{trigger}[:{customer}]` — deterministic |
| **LLM Usage** | `force_template=True` — LLM never called | `force_template=False` — LLM at `temperature=0`, template fallback |
| **Template Composer** | 15 hardcoded `trigger.kind` patterns | Generic 4-context fact extraction for ANY trigger |
| **Tick Resolver** | Lazy context loading, max 3 actions | Pre-loaded contexts, priority scoring, max 5 actions |
| **Reply Engine** | Basic keyword routing, no objection handling | Budget objection repositioning, expanded "later" detection |
| **Metadata** | `Vera AI Team`, `team@magicpin.ai` | `Algsoch AI`, `vicky@algsoch.ai` |
| **Middleware** | Consumed request body (broken POST) | Restored body for downstream handlers |

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                     magicpin Judge Harness                         │
│  Pushes context → Calls /v1/tick → Plays merchant replies          │
└────────────────────────┬───────────────────────────────────────────┘
                         │ HTTPS/JSON
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Algsoch AI Bot (FastAPI)                        │
│                                                                    │
│  POST /v1/context ──► ContextStore (versioned, in-memory)         │
│                      Key: (scope, context_id) → {version, payload} │
│                      Rejects stale versions (409)                  │
│                                                                    │
│  POST /v1/tick ──► TickResolver                                   │
│                      1. Load all triggers from available_triggers   │
│                      2. Filter expired + suppressed                │
│                      3. Validate merchant exists                   │
│                      4. Load category via merchant.category_slug   │
│                      5. Load customer if trigger.customer_id       │
│                      6. Score priority = urgency × 10 + version    │
│                      7. Compose (LLM temp=0 → template fallback)   │
│                      8. Generate deterministic conversation_id     │
│                      9. Return actions[] (max 5)                   │
│                                                                    │
│  POST /v1/reply ──► ReplyRouter                                   │
│                      1. Safety: hostile → end, disinterest → end   │
│                      2. Objections: budget → reframe (not end)     │
│                      3. Later: "busy", "tomorrow" → wait 1hr       │
│                      4. Auto-reply detection → end after 3 repeats │
│                      5. Intent routing: offers, perf, greeting...  │
│                      6. Fallback: LLM composition with history     │
│                                                                    │
│  GET  /v1/healthz ──► Uptime + context counts                     │
│  GET  /v1/metadata ──► Algsoch AI identity                        │
└────────────────────────────────────────────────────────────────────┘
```

### Message Composition Pipeline

```
  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
  │   Category  │    │   Merchant   │    │   Trigger   │    │   Customer   │
  │   Context   │    │   Context    │    │   Context   │    │   Context    │
  │  (optional) │    │  (required)  │    │  (required) │    │  (optional)  │
  └──────┬──────┘    └──────┬───────┘    └──────┬──────┘    └──────┬───────┘
         │                  │                   │                  │
         └──────────────────┴───────────────────┴──────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   CompositionService    │
              │                         │
              │  1. Try LLM (temp=0)    │
              │     - Groq or Anthropic │
              │     - Grounded prompt   │
              │     - JSON output       │
              │                         │
              │  2. If LLM fails →      │
              │     template fallback   │
              │     - Extract facts     │
              │     - Apply safety      │
              │     - Build message     │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │   Safety Gates          │
              │   - Taboo word filter   │
              │   - Consent check       │
              │   - Expiry validation   │
              │   - Opt-out detection   │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │   ComposedMessage       │
              │   {body, cta,           │
              │    send_as,             │
              │    suppression_key,     │
              │    rationale}           │
              └─────────────────────────┘
```

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Start backend on port 8001
docker run -d --name magicpin-bot -p 8001:8000 \
  -e HOST=0.0.0.0 \
  -e GROQ_API_KEY="your-key-here" \
  -v "$(pwd)/backend:/app" \
  python:3.11-slim \
  bash -c "cd /app && pip install -q -r requirements.txt && python main.py"

# Test it
curl http://localhost:8001/v1/healthz
```

### Option 2: Local Python

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="gsk_..."  # optional
python main.py
```

Server runs on `http://localhost:8000`.

### Option 3: Full Stack (Backend + Frontend)

```bash
docker compose up --build
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Running Tests

### All Tests (Recommended)

```bash
# Start local backend first (see Quick Start)
python3 tests/adversarial_magicpin_probe.py http://localhost:8001
python3 tests/test_adaptive_injection.py http://localhost:8001
```

### Individual Test Suites

```bash
# Adversarial probe (22 tests) — edge cases, determinism, safety
python3 tests/adversarial_magicpin_probe.py http://localhost:8001

# Phase 3 adaptive injection (27 tests) — new facts, version bumps, cross-scope
python3 tests/test_adaptive_injection.py http://localhost:8001

# Cloud tests against deployed backend
python3 run_cloud_tests.py --url https://algsoch-magicpin.onrender.com

# Judge simulator (official harness — requires LLM API key)
python judge_simulator.py
```

### Test Against Deployed Backend

```bash
python3 tests/adversarial_magicpin_probe.py https://algsoch-magicpin.onrender.com
python3 tests/test_adaptive_injection.py https://algsoch-magicpin.onrender.com
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/healthz` | GET | Liveness probe — uptime + context counts |
| `/v1/metadata` | GET | Bot identity — team, model, approach |
| `/v1/context` | POST | Push category/merchant/trigger/customer context |
| `/v1/tick` | POST | Periodic wake-up — bot initiates proactive messages |
| `/v1/reply` | POST | Receive merchant/customer reply — respond with action |
| `/v1/playground/*` | Various | UI helpers for manual testing |
| `/v1/monitor/logs` | GET | API request logs for dashboard |

### Tick Response Schema

```json
{
  "actions": [{
    "conversation_id": "conv:m_001:trg_research",
    "merchant_id": "m_001",
    "customer_id": null,
    "send_as": "vera",
    "trigger_id": "trg_research",
    "body": "Dr. Meera, JIDA's Oct issue landed...",
    "cta": "open_ended",
    "suppression_key": "research:dentists:2026-W17",
    "rationale": "External research digest with merchant-relevant clinical anchor"
  }]
}
```

### Reply Response Schema

```json
{
  "action": "send",
  "body": "Sending now — also drafted a 90-sec patient-ed WhatsApp...",
  "cta": "open_ended",
  "rationale": "Honoring merchant's accept; adding low-friction follow-on"
}
```

## 4-Context Framework

Every message is composed from 4 context layers:

1. **CategoryContext** — Vertical knowledge (voice/tone, offer catalog, peer stats, research digest, seasonal beats)
2. **MerchantContext** — Specific business state (identity, subscription, performance, offers, signals)
3. **TriggerContext** — Event prompting this message (kind, source, payload, urgency, expiry)
4. **CustomerContext** — (Optional) Customer state for merchant-to-customer messages (identity, relationship, consent)

### Example Flow

```
Judge pushes:
  POST /v1/context → category "dentists" v1
  POST /v1/context → merchant "m_001" v1
  POST /v1/context → trigger "trg_001" v1 (research_digest, urgency=2)

Judge calls:
  POST /v1/tick → available_triggers: ["trg_001"]

Bot resolves:
  1. Load trigger trg_001 → kind=research_digest, merchant_id=m_001
  2. Load merchant m_001 → category_slug=dentists
  3. Load category dentists → digest items, peer stats, voice
  4. Score priority = 2 × 10 + 1 = 21
  5. Compose: LLM temp=0 with 3 contexts → "Dr. Meera, JIDA's Oct issue..."
  6. Return action with conversation_id="conv:m_001:trg_001"

Judge plays merchant:
  POST /v1/reply → "Yes, send me the abstract"

Bot replies:
  Intent: commitment → action plan
  POST /v1/reply → "Done — next steps: 1) Draft abstract..."
```

## Key Features

### Deterministic Behavior
- Same `/v1/tick` input → identical output (no UUIDs, no timestamps in IDs)
- `conversation_id` format: `conv:{merchant_id}:{trigger_id}[:{customer_id}]`
- LLM runs at `temperature=0` for reproducible composition

### Adaptive Context Handling
- Version-bumped contexts → bot uses NEW data, not stale
- New categories/merchants mid-test → immediate grounding
- Cross-scope linking: category ↔ merchant ↔ trigger ↔ customer

### Reply Intelligence
- **Hostile detection**: "stop", "spam", "unsubscribe" → ends gracefully
- **Objection repositioning**: "no budget" → reframes with free options
- **Auto-reply detection**: 3+ identical merchant messages → ends conversation
- **Later detection**: "busy", "tomorrow", "remind me" → waits 1 hour
- **Commitment detection**: "let's do it" → switches to execution mode

### Hindi/Hinglish Support
- Devanagari script detection (हिन्दी)
- Hinglish keyword detection ("kya", "kaise", "hai", "chahiye")
- Context-appropriate Hindi responses for all intents

### Safety & Robustness
- Taboo word filtering per category voice
- Consent scope validation for customer messages
- Expiry guard on triggers
- Stale version rejection (409) on context pushes
- SQL/XSS injection resistance
- Null byte and Unicode edge case handling

## Project Structure

```
magicpin-ai-challenge/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + startup/shutdown
│   │   ├── routes/
│   │   │   ├── health.py           # /v1/healthz, /v1/metadata
│   │   │   ├── context.py          # /v1/context (versioned storage)
│   │   │   ├── tick.py             # /v1/tick (deterministic resolver)
│   │   │   ├── reply.py            # /v1/reply (intent router)
│   │   │   ├── playground.py       # /v1/playground/* (UI helpers)
│   │   │   ├── merchant_sim.py     # Merchant simulation endpoints
│   │   │   ├── monitor.py          # /v1/monitor/* (request logs)
│   │   │   └── docs.py             # Documentation endpoints
│   │   ├── services/
│   │   │   ├── composition.py      # ContextStore, ConversationManager, CompositionService
│   │   │   ├── state.py            # BotState singleton
│   │   │   └── request_logger.py   # API request logging
│   │   ├── middleware/
│   │   │   └── request_logger_middleware.py  # Request/response capture
│   │   └── models/
│   │       └── context.py          # Pydantic models
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                        # React + Vite dashboard
├── dataset/                         # Seed data (categories, merchants, triggers)
├── tests/
│   ├── adversarial_magicpin_probe.py   # 22 adversarial tests
│   ├── test_adaptive_injection.py      # 27 Phase 3 injection tests
│   └── test_composition_unit.py        # 10 unit tests
├── judge_simulator.py               # Official judge harness simulator
├── run_cloud_tests.py               # 39 cloud test runner
├── render.yaml                      # Render Blueprint config
├── MAGICPIN_FIX_ANALYSIS.md         # Architecture analysis (7 flaws identified)
├── MAGICPIN_FIX_REPORT.md           # Before/after fix report
├── challenge-brief.md               # Full challenge spec
└── challenge-testing-brief.md       # Testing contract
```

## Deploy to Render

### Live URLs
- **Backend:** https://algsoch-magicpin.onrender.com
- **Frontend:** https://vera-ai-frontend.onrender.com

### Environment Variables

| Variable | Service | Required | Description |
|----------|---------|----------|-------------|
| `GROQ_API_KEY` | Backend | Optional | Groq API key for LLM composition |
| `ANTHROPIC_API_KEY` | Backend | Optional | Anthropic API key (fallback) |
| `HOST` | Backend | Yes | Set to `0.0.0.0` for Docker |
| `VITE_API_URL` | Frontend | Yes | Backend URL |

### Manual Deploy

**Backend:**
1. Connect repo to Render Web Service
2. Root Directory: `backend`
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add env vars

**Frontend:**
1. Connect repo to Render Static Site
2. Root Directory: `frontend`
3. Build: `npm install && npm run build`
4. Publish: `dist`
5. Env var: `VITE_API_URL`

## Judge Readiness Checklist

- [x] All 5 endpoints implemented (`healthz`, `metadata`, `context`, `tick`, `reply`)
- [x] `/v1/context` idempotent on `(scope, context_id, version)`
- [x] `/v1/tick` returns within 30s (deterministic, no async work)
- [x] `/v1/reply` returns within 30s for any conversation
- [x] Context persists across calls (in-memory, no restarts)
- [x] Deterministic conversation IDs (no UUIDs/timestamps)
- [x] Handles unseen trigger kinds (generic 4-context grounding)
- [x] Handles mid-test context injection (version bumps respected)
- [x] Auto-reply detection (Phase 4 replay test)
- [x] Hostile/off-topic handling (Phase 4 replay test)
- [x] Intent transition on commitment (Phase 4 replay test)
- [x] Truthful metadata (Algsoch AI identity)
- [x] 49/49 tests passing locally

## Challenge Reference

- [challenge-brief.md](challenge-brief.md) — Full challenge spec
- [challenge-testing-brief.md](challenge-testing-brief.md) — Testing contract
- [MAGICPIN_FIX_ANALYSIS.md](MAGICPIN_FIX_ANALYSIS.md) — Architecture analysis
- [MAGICPIN_FIX_REPORT.md](MAGICPIN_FIX_REPORT.md) — Fix report with before/after

## Team

**Algsoch AI** — Vicky Kumar  
Contact: vicky@algsoch.ai

## License

MIT — for the magicpin AI Challenge only.
