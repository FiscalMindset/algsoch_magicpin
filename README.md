# Vera AI — Merchant AI Assistant (magicpin AI Challenge)

> An AI-powered WhatsApp merchant assistant that proactively engages businesses with contextual, actionable messages — built for the magicpin AI Challenge.

[![Deploy to Render](https://img.shields.io/badge/Deploy%20to-Render-4C42E2?style=flat&logo=render)](https://render.com)
[![Tests](https://img.shields.io/badge/Tests-39%2F39%20passing-brightgreen)](#test-results)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)]()
[![React](https://img.shields.io/badge/React-18+-61dafb)]()

## Live Deployment

| Service | URL |
|---------|-----|
| **Backend API** | https://algsoch-magicpin.onrender.com |
| **Frontend Dashboard** | https://vera-ai-frontend.onrender.com |
| **API Docs** | https://algsoch-magicpin.onrender.com/docs |

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| **Custom Stress Tests** | 14/14 | ✅ 100% |
| **Advanced Stress Tests** | 25/25 | ✅ 100% |
| **Judge Simulator** | 4/4 | ✅ 100% |
| **Total** | **43/43** | **✅ 100%** |

### What We Test

**Custom Tests (14):** Repetition detection, Hindi language switching, curveball (GST) handling, hostility escalation, empty ticks, malformed context rejection, concurrent conversations, long messages, Unicode/emoji, orphan commitments, stale version rejection, reply-after-end, healthz consistency, metadata completeness.

**Advanced Tests (25):** Empty/whitespace/emoji-only messages, JSON/SQL/XSS injection, 10-turn conversations, rapid-fire messages, Hindi-English code mixing, non-existent merchant IDs, special characters, context override attacks, null bytes, conversation ID collision, turn number manipulation, greeting→hostility switching, multiple commitments, 50KB payloads, Unicode edge cases (RTL, ZWJ, combining marks), conversation revival, negative performance queries, renewal urgency, trial/expired/unverified merchants.

## Quick Start

### Prerequisites
- **Node.js** ≥ 18 (frontend)
- **Python** ≥ 3.10 (backend)
- **Ollama** (optional, for merchant simulation)
- **Groq API Key** (optional, for LLM-powered composition)

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Optional: export GROQ_API_KEY="gsk_..." for LLM composition
python main.py
```

Server runs on `http://localhost:8000`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard opens at `http://localhost:5173`.

### 3. Run All Tests

```bash
# Quick cloud tests (runs against deployed backend)
python run_cloud_tests.py --url https://algsoch-magicpin.onrender.com

# Judge harness simulator (official — requires LLM API key)
python judge_simulator.py

# Custom stress tests (local)
python custom_stress_tests.py --bot-url http://localhost:8000

# Advanced stress tests (25 hard tests, local)
python advanced_stress_tests.py --bot-url http://localhost:8000
```

### About Ollama (Merchant Simulator)

The frontend includes an **Ollama Simulation toggle** that auto-generates merchant replies using a local LLM. This feature is **NOT available on the deployed frontend** because:

1. **Ollama requires a local server** (`http://localhost:11434`) running on your machine with models like `phi3:latest` or `llama3` installed.
2. **Render's free tier has no GPU** and cannot run Ollama — it would need a dedicated GPU instance.
3. **The toggle simulates a merchant** by sending random responses back to Vera, useful for testing multi-turn flows locally without a human clicking buttons.

For cloud testing, use `run_cloud_tests.py` which runs automated tests directly against the deployed API without needing Ollama.

## Architecture

```
┌────────────────────────────────────────────────────┐
│                Frontend (React + Vite)             │
│  Dashboard · Conversations · Playground · Chat    │
│  Premium dark UI · 10 merchants · Ollama sim      │
└──────────────────────┬─────────────────────────────┘
                       │ REST API
┌──────────────────────▼─────────────────────────────┐
│               Backend (FastAPI)                    │
│                                                    │
│  /v1/healthz    /v1/metadata    /v1/context        │
│  /v1/tick       /v1/reply       /v1/playground     │
│  /v1/simulate/* (Ollama merchant sim)              │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │  Intent Router (12+ handlers)                │ │
│  │  offers · performance · greeting · GST       │ │
│  │  profile · reviews · commitment · yes/no     │ │
│  │  + Hindi/Hinglish detection                  │ │
│  │  + Repetition detection (end on repeat)      │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │  Composition Service                         │ │
│  │  Template-based (deterministic, no halluc.)  │ │
│  │  Groq / Anthropic LLM (optional fallback)    │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │  State Management                            │ │
│  │  ContextStore (versioned, stale rejection)   │ │
│  │  ConversationManager (auto-reply detect)     │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────┬─────────────────────────────┘
                       │ LLM API
              ┌─────────▼──────────┐
              │ Groq / Anthropic   │
              │ or Ollama (local)  │
              └────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/healthz` | GET | Liveness probe with uptime + context counts |
| `/v1/metadata` | GET | Bot identity (team, model, approach) |
| `/v1/context` | POST | Push category/merchant/trigger/customer context |
| `/v1/tick` | POST | Periodic wake-up; bot initiates messages |
| `/v1/reply` | POST | Receive merchant/customer reply, respond with action |
| `/v1/simulate/*` | POST | Ollama merchant simulation endpoints |
| `/v1/playground/*` | Various | UI helpers for testing |

## Reply Action Contract

Every `/v1/reply` response follows this schema:

```json
{
  "action": "send",        // "send" | "wait" | "end"
  "body": "Message text",  // The WhatsApp message body
  "cta": "binary_yes_no",  // "open_ended" | "binary_yes_no" | "none"
  "rationale": "Why...",   // Decision explanation
  "wait_seconds": null     // Only for action="wait"
}
```

## 4-Context Framework

Every message is composed from 4 context layers:

1. **CategoryContext** — Vertical knowledge (voice, offers, peer stats, research digest)
2. **MerchantContext** — Specific business state (performance, offers, signals, history)
3. **TriggerContext** — Event prompting this message (research, perf dip, recall, etc.)
4. **CustomerContext** — (Optional) Customer state for merchant-to-customer messages

## Key Features

### Intent-Based Routing
12+ explicit intent handlers before falling back to composition:
- Offers queries → shows active offers or recommends new ones
- Performance queries → 30-day snapshot with peer comparison
- Greetings → contextual update based on available triggers
- GST/tax questions → polite deflection to core mission
- Profile/review queries → status + actionable next steps
- Commitment → switches to execution mode
- Yes/No → acknowledges and prepares next action or backs off

### Hindi/Hinglish Support
- Automatic detection of Devanagari script (हिन्दी)
- Hinglish detection (Hindi words in Latin script)
- Context-appropriate Hindi responses for all intents

### Repetition Detection
- Tracks last response per conversation
- Ends conversation gracefully when exact repetition detected
- Prevents spam-like behavior

### Safety & Robustness
- Auto-reply detection (canned WhatsApp responses)
- Hostile message handling (spam, unsubscribe, block)
- SQL/XSS injection resistance
- Null byte and Unicode edge case handling
- Conversation ID isolation across merchants
- Versioned context store with stale rejection

## Project Structure

```
magicpin-ai-challenge/
├── backend/                 # FastAPI server
│   ├── app/
│   │   ├── main.py          # FastAPI app + routers
│   │   ├── routes/          # API endpoints (reply, context, tick, sim)
│   │   ├── services/        # Composition, state management
│   │   └── models/          # Pydantic models
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # React + Vite dashboard
│   ├── src/
│   │   ├── pages/           # Dashboard, Playground, MerchantChat
│   │   └── components/      # Layout, Sidebar, Cards
│   └── package.json
├── dataset/                 # Seed data (categories, merchants, triggers)
├── judge_simulator.py       # Judge harness simulator
├── custom_stress_tests.py   # 14 stress tests
├── advanced_stress_tests.py # 25 advanced stress tests
└── render.yaml              # Render deployment config
```

## Deploy to Render

### Live URLs
- **Backend:** https://algsoch-magicpin.onrender.com
- **Frontend:** https://vera-ai-frontend.onrender.com

### One-Click Deploy
Use the included `render.yaml` for a blueprint deploy.

### Manual Deploy

**Backend (Web Service):**
1. Point to this repo
2. Build: `cd backend && pip install -r requirements.txt`
3. Start: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Env vars: `GROQ_API_KEY` (optional), `ANTHROPIC_API_KEY` (optional)

**Frontend (Static Site):**
1. Point to this repo
2. Build: `cd frontend && npm install && npm run build`
3. Publish: `frontend/dist`
4. Env var: `VITE_API_URL` — your backend Render URL

## Challenge Reference

- [challenge-brief.md](challenge-brief.md) — Full challenge spec
- [challenge-testing-brief.md](challenge-testing-brief.md) — Testing contract
- [engagement-design.md](engagement-design.md) — Vera engagement framework
- [engagement-research.md](engagement-research.md) — Current system research

## License

MIT — for the magicpin AI Challenge only.
