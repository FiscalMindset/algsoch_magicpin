# Vera AI — Development Guide

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Judge Harness (magicpin)                     │
│  Simulates merchant interactions over HTTP/JSON                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                ┌──────────┴──────────┐
                │   HTTP/JSON (5 EP) │
                ├──────────┬──────────┘
                │          │
        ┌───────▼────────┐ │
        │   Frontend     │ │
        │   (React)      │ │
        └────────────────┘ │
                │          │
        ┌───────▼──────────────────────────────────────┐
        │         Backend (FastAPI)                     │
        ├──────────────────────────────────────────────┤
        │                                               │
        │  Routes (5 endpoints):                       │
        │  ├── GET  /v1/healthz                        │
        │  ├── GET  /v1/metadata                       │
        │  ├── POST /v1/context                        │
        │  ├── POST /v1/tick                           │
        │  └── POST /v1/reply                          │
        │                                               │
        │  Services:                                    │
        │  ├── ContextStore (versioned contexts)       │
        │  ├── ConversationManager (state tracking)    │
        │  └── CompositionService (LLM)                │
        │                                               │
        │  Models:                                      │
        │  ├── CategoryContext                         │
        │  ├── MerchantContext                         │
        │  ├── TriggerContext                          │
        │  └── CustomerContext                         │
        │                                               │
        └──────────────────────────────────────────────┘
                │          │
        ┌───────▼────┐ ┌───▼──────────┐
        │ In-Memory  │ │   LLM API    │
        │   Store    │ │  (Anthropic) │
        └────────────┘ └──────────────┘
```

## 📁 Directory Structure

### Backend (`backend/`)

```
backend/
├── app/
│   ├── models/
│   │   ├── __init__.py           # Exports all models
│   │   ├── context.py            # Context schemas
│   │   └── composition.py        # Composition schemas
│   │
│   ├── services/
│   │   ├── __init__.py           # Service exports
│   │   ├── composition.py        # ContextStore, ConversationManager, CompositionService
│   │   └── state.py              # BotState (global state)
│   │
│   ├── routes/
│   │   ├── __init__.py           # Router exports
│   │   ├── health.py             # GET /v1/healthz, GET /v1/metadata
│   │   ├── context.py            # POST /v1/context
│   │   ├── tick.py               # POST /v1/tick
│   │   └── reply.py              # POST /v1/reply
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── formatters.py         # Helper functions
│   │
│   ├── __init__.py               # Package init
│   └── main.py                   # FastAPI app definition
│
├── tests/                        # Unit tests (to be implemented)
├── main.py                       # Entry point (uvicorn runner)
├── requirements.txt              # Dependencies
├── Dockerfile                    # Container config
├── .env.example                  # Environment template
├── .gitignore                    # Git ignore rules
└── README.md                     # Documentation
```

### Frontend (`frontend/`)

```
frontend/
├── src/
│   ├── components/
│   │   ├── index.js              # Component exports
│   │   ├── Header.jsx            # Top nav bar
│   │   ├── Header.css            # Header styles
│   │   ├── Sidebar.jsx           # Left nav menu
│   │   ├── Sidebar.css           # Sidebar styles
│   │   ├── Layout.jsx            # Page wrapper
│   │   ├── Layout.css            # Layout styles
│   │   ├── Card.jsx              # Generic card
│   │   ├── Card.css              # Card styles
│   │   ├── StatBox.jsx           # Metric box
│   │   └── StatBox.css           # StatBox styles
│   │
│   ├── pages/
│   │   ├── index.js              # Page exports
│   │   ├── Dashboard.jsx         # Main dashboard
│   │   ├── Dashboard.css         # Dashboard styles
│   │   ├── Conversations.jsx     # Conversations list
│   │   ├── Conversations.css     # Conversations styles
│   │   ├── Analytics.jsx         # Analytics page
│   │   ├── Analytics.css         # Analytics styles
│   │   ├── Settings.jsx          # Settings page
│   │   └── Settings.css          # Settings styles
│   │
│   ├── hooks/
│   │   ├── index.js              # Hook exports
│   │   └── useBot.js             # Bot status hook
│   │
│   ├── services/
│   │   ├── index.js              # Service exports
│   │   └── api.js                # API client
│   │
│   ├── utils/
│   │   ├── index.js              # Utils exports
│   │   └── formatters.js         # Format functions
│   │
│   ├── assets/                   # Images, icons
│   │
│   ├── styles/
│   │   └── globals.css           # Global styles
│   │
│   ├── App.jsx                   # Main App component
│   ├── App.css                   # App styles
│   └── main.jsx                  # React entry point
│
├── index.html                    # HTML template
├── package.json                  # Dependencies
├── vite.config.js                # Vite bundler
├── tailwind.config.js            # Tailwind CSS
├── postcss.config.js             # PostCSS config
├── Dockerfile                    # Container config
├── .env.example                  # Environment template
├── .gitignore                    # Git ignore rules
└── README.md                     # Documentation
```

## 🔄 Data Flow Examples

### Example 1: Context Push

```
Judge                          Backend
  │
  ├─ POST /v1/context
  │  (CategoryContext)
  │                         ContextStore.store_context()
  │                         ├─ Check version
  │                         ├─ Store if newer
  │                         └─ Return ack_id
  │◀────────────────────────
  │  200: {accepted: true}
```

### Example 2: Periodic Tick

```
Judge                          Backend
  │
  ├─ POST /v1/tick
  │  (now, available_triggers)
  │                         ├─ Get merchant contexts
  │                         ├─ Compose messages
  │                         ├─ CompositionService
  │                         │  ├─ Build prompt (4-context)
  │                         │  ├─ Call LLM
  │                         │  └─ Parse response
  │                         └─ Return actions[]
  │◀────────────────────────
  │  200: {actions: [...]}
```

### Example 3: Reply & Auto-reply Detection

```
Judge                          Backend
  │
  ├─ POST /v1/reply
  │  (conversation_id, message)
  │                         ConversationManager
  │                         ├─ Add turn
  │                         ├─ Detect auto-reply
  │                         │  (same message 3× in a row?)
  │                         ├─ If auto-reply
  │                         │  └─ Return action: "end"
  │                         ├─ Else compose reply
  │                         │  ├─ Get context
  │                         │  ├─ Call CompositionService
  │                         │  └─ Return action: "send"
  │                         └─ Return response
  │◀────────────────────────
  │  200: {action: "send"|"wait"|"end"}
```

## 🎯 Key Design Decisions

### Backend

**1. Idempotent Context Storage**
- Versioned by `(scope, context_id, version)`
- Re-posting same version = no-op
- Higher version replaces lower version atomically

**2. Auto-reply Detection**
- Tracks conversation history
- Detects pattern: same message 3+ times
- Gracefully exits conversation

**3. Composition Service**
- Primary: LLM (Claude Opus 4.7)
- Fallback: Template-based composition
- Separate from routing logic

**4. State Management**
- Global `BotState` container
- Three core services:
  - ContextStore (contexts)
  - ConversationManager (conversations)
  - CompositionService (composition)

### Frontend

**1. File-Based CSS**
- Each component/page has isolated CSS file
- No global CSS conflicts
- Easy to maintain and scale

**2. Component Hierarchy**
```
App
├── Layout
│   ├── Header
│   ├── Sidebar
│   └── Main
│       ├── Dashboard
│       ├── Conversations
│       ├── Analytics
│       └── Settings
```

**3. Styling Stack**
- Tailwind CSS (utility classes)
- CSS Files (component/page-specific)
- PostCSS (autoprefixer, etc.)

**4. State Management**
- React hooks (useState, useEffect)
- Custom hooks (useBot)
- API client (axios)

## 📝 Common Tasks

### Adding a New Context Type

1. Add schema to `backend/app/models/context.py`
2. Update `ContextStore` if needed
3. Handle in `POST /v1/context` route
4. Use in composition logic

Example:
```python
class NewContext(BaseModel):
    id: str
    # ... fields
```

### Adding a New Page

1. Create `frontend/src/pages/NewPage.jsx`
2. Create `frontend/src/pages/NewPage.css`
3. Add import in `App.jsx`
4. Add menu item in `Sidebar.jsx`

Example:
```jsx
// NewPage.jsx
import './NewPage.css';

function NewPage() {
  return <div className="new-page">...</div>;
}
```

### Adding a New Component

1. Create `frontend/src/components/NewComponent.jsx`
2. Create `frontend/src/components/NewComponent.css`
3. Import in component that uses it

Example:
```jsx
// NewComponent.jsx
import './NewComponent.css';

function NewComponent({ prop }) {
  return <div className="new-component">...</div>;
}
```

### Calling the API from Frontend

```jsx
import { botAPI } from '../services/api';

// In useEffect or event handler
const response = await botAPI.healthz();
console.log(response.data);
```

### Adding Logging to Backend

```python
import logging

logger = logging.getLogger(__name__)

# In route handler
logger.info(f"Received context: {context_id}")
logger.error(f"Failed to compose: {error}")
```

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest tests/
```

### Frontend Lint

```bash
cd frontend
npm run lint
```

## 🚀 Deployment

### Local Development

```bash
# Terminal 1: Backend
cd backend
python main.py

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Docker

```bash
docker-compose up --build
```

### Production Build

```bash
# Backend
# Just deploy backend/ folder with Dockerfile

# Frontend
cd frontend
npm run build
# Deploy dist/ to CDN/hosting
```

## 🔐 Security Considerations

1. **Input Validation**: All endpoints validate inputs
2. **CORS**: Enabled for development; restrict in production
3. **Error Messages**: Don't leak internal details
4. **Secrets**: Use .env files, never commit keys
5. **Rate Limiting**: Add if needed (e.g., via middleware)

## 📚 Reference

- Challenge Brief: `challenge-brief.md`
- Testing Brief: `challenge-testing-brief.md`
- Engagement Design: `engagement-design.md`
- Backend README: `backend/README.md`
- Frontend README: `frontend/README.md`

## 🆘 Troubleshooting

**Backend won't start**
- Check Python version (3.9+)
- Install requirements: `pip install -r requirements.txt`
- Check port 8000 is free

**Frontend won't connect to backend**
- Check `VITE_API_URL` in `.env.local`
- Backend must be running on `http://localhost:8000`
- Check CORS settings in `backend/app/main.py`

**Styles not loading**
- Check CSS file names match component names
- Verify import paths
- Check browser dev tools for 404s

**LLM not responding**
- Check `ANTHROPIC_API_KEY` is set
- Verify API key is valid
- Check rate limits

---

**Happy Coding! 🚀**
