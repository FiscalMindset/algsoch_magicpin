# Vera AI Backend

FastAPI-based backend for the magicpin Vera AI merchant assistant challenge.

## Structure

```
backend/
├── app/
│   ├── models/          # Pydantic models for requests/responses
│   ├── services/        # Business logic (composition, storage, state)
│   ├── routes/          # API endpoints
│   ├── utils/           # Utilities
│   └── main.py          # FastAPI app
├── tests/               # Unit and integration tests
├── main.py              # Entry point
└── requirements.txt     # Python dependencies
```

## Setup

```bash
cd backend
pip install -r requirements.txt
python main.py
```

## API Endpoints

- `GET /v1/healthz` — Liveness probe
- `GET /v1/metadata` — Bot identity
- `POST /v1/context` — Receive context push
- `POST /v1/tick` — Periodic wake-up, proactive messages
- `POST /v1/reply` — Reply to merchant/customer message

## Architecture

### Core Components

1. **ContextStore** — In-memory versioned storage for category, merchant, customer, trigger contexts
2. **ConversationManager** — Manages active conversations, auto-reply detection, conversation history
3. **CompositionService** — Composes messages using LLM + fallback templates
4. **BotState** — Global state container

### Message Composition Flow

```
judge push → context store
     ↓
periodic tick → check available triggers
     ↓
compose message → LLM (4-context framework)
     ↓
return action → to judge
```

## Key Features

- ✅ Idempotent context storage with version checking
- ✅ Auto-reply detection and graceful exit
- ✅ Multi-turn conversation tracking
- ✅ LLM-powered composition with fallback templates
- ✅ CORS enabled for frontend integration
- ✅ Comprehensive error handling and logging

