# magicpin AI Challenge — Full Stack Solution

Complete implementation of the Vera AI merchant assistant for the magicpin AI challenge.

## 📁 Project Structure

```
magicpin-ai-challenge/
├── backend/                    # FastAPI server
│   ├── app/
│   │   ├── models/            # Pydantic models (contexts, responses)
│   │   ├── services/          # Business logic (composition, storage)
│   │   ├── routes/            # API endpoints (5 required endpoints)
│   │   └── main.py            # FastAPI app
│   ├── tests/                 # Unit and integration tests
│   ├── requirements.txt       # Python dependencies
│   └── README.md              # Backend documentation
│
├── frontend/                   # React dashboard
│   ├── src/
│   │   ├── components/        # Reusable components (file-based styling)
│   │   ├── pages/             # Dashboard pages (file-based styling)
│   │   ├── hooks/             # Custom React hooks
│   │   ├── services/          # API client
│   │   ├── utils/             # Helper functions
│   │   ├── styles/            # Global styles
│   │   ├── App.jsx            # Main component
│   │   └── main.jsx           # Entry point
│   ├── package.json           # Dependencies
│   ├── vite.config.js         # Vite bundler config
│   ├── tailwind.config.js     # Tailwind CSS config
│   └── README.md              # Frontend documentation
│
├── dataset/                    # Base dataset (provided)
├── examples/                   # Examples and case studies
├── engagement-design.md        # Engagement framework
├── challenge-brief.md          # Challenge specification
└── README.md                   # This file
```

## 🚀 Quick Start

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Backend runs on `http://localhost:8000`

**API Endpoints**:
- `GET /v1/healthz` — Liveness probe
- `GET /v1/metadata` — Bot identity
- `POST /v1/context` — Receive context push
- `POST /v1/tick` — Periodic wake-up
- `POST /v1/reply` — Reply to merchant/customer

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`

## 🏗️ Architecture

### Backend Architecture

```
Judge → HTTP/JSON → Bot (FastAPI)
         ↓
    Context Store (versioned)
         ↓
    Conversation Manager (auto-reply detection)
         ↓
    Composition Service (LLM + templates)
         ↓
    Response (action)
```

**Key Components**:
1. **ContextStore** — Idempotent, versioned context storage
2. **ConversationManager** — Multi-turn conversation tracking + auto-reply detection
3. **CompositionService** — Message composition with LLM (Claude Opus 4.7) fallback templates
4. **BotState** — Global state container

### Frontend Architecture

```
React App
├── Layout (Header + Sidebar)
├── Pages (Dashboard, Conversations, Analytics, Settings)
├── Components (Card, StatBox, etc.)
├── Hooks (useBot, etc.)
└── Services (API client)
```

**Features**:
- Real-time bot status monitoring
- Conversation history tracking
- Performance analytics
- Configuration management
- File-based CSS (no global CSS chaos)

## 🎯 Implementation Highlights

### Backend

✅ **5 Required Endpoints** — All implemented per challenge-testing-brief.md
✅ **Idempotent Storage** — Version-based context deduplication
✅ **Auto-reply Detection** — Graceful conversation exit
✅ **LLM Integration** — Claude Opus 4.7 for composition
✅ **Error Handling** — Comprehensive error handling with fallbacks
✅ **Async Ready** — FastAPI async/await pattern

### Frontend

✅ **File-Based Styling** — Each component/page has isolated CSS
✅ **Responsive Design** — Mobile-first with Tailwind CSS
✅ **Component Reusability** — Composable, modular architecture
✅ **Real-time Updates** — Auto-refresh bot status
✅ **Professional UI** — Clean, modern dashboard
✅ **Type Safety** — React best practices (hooks, props validation)

## 🔧 Configuration

### Environment Variables

Backend (`.env`):
```
PORT=8000
ANTHROPIC_API_KEY=sk-...
```

Frontend (`.env`):
```
VITE_API_URL=http://localhost:8000
```

## 📊 Data Flow

```
1. Judge sends context → POST /v1/context
2. Context stored → ContextStore
3. Judge sends tick → POST /v1/tick
4. Bot composes message → CompositionService
5. Returns action → Judge
6. Judge sends reply → POST /v1/reply
7. Bot responds → ConversationManager (with auto-reply detection)
```

## 🧪 Testing

Backend:
```bash
cd backend
pytest tests/
```

Frontend:
```bash
cd frontend
npm run lint
```

## 📝 Challenge Requirements Met

✅ All 5 endpoints implemented
✅ Idempotent context storage with versioning
✅ Auto-reply detection and graceful exit
✅ Multi-turn conversation management
✅ 4-context composition framework (category, merchant, trigger, customer)
✅ LLM-powered message composition
✅ Professional, full-stack solution
✅ File-based component styling (frontend)
✅ Comprehensive documentation

## 📚 Documentation

- [Backend README](./backend/README.md) — API, architecture, setup
- [Frontend README](./frontend/README.md) — Components, styling, setup
- [Challenge Brief](./challenge-brief.md) — Business requirements
- [Testing Brief](./challenge-testing-brief.md) — Technical API spec
- [Engagement Design](./engagement-design.md) — Composition framework

## 🎨 Styling Philosophy

**Frontend Styling Approach**:
- Each component has a `.jsx` file and matching `.css` file
- Global styles in `src/styles/globals.css`
- CSS Modules pattern (scoped by file name)
- Tailwind CSS for utility classes
- No single "styles.css" monolith
- Scalable, maintainable architecture

Example:
```
Card.jsx        (component logic)
Card.css        (component styles)
StatBox.jsx     (component logic)
StatBox.css     (component styles)
Dashboard.jsx   (page logic)
Dashboard.css   (page styles)
```

## 🔐 Security

- ✅ CORS enabled for frontend access
- ✅ Input validation on all endpoints
- ✅ No hardcoded secrets
- ✅ Async/await for safety
- ✅ Error messages don't leak internals

## 🚀 Deployment

### Backend Deployment
```bash
# Using Render, Railway, or similar
python main.py
```

### Frontend Deployment
```bash
# Build optimized production bundle
npm run build

# Deploy dist/ to Vercel, Netlify, or S3
```

## 📞 Support

For questions or issues:
1. Check the challenge briefs
2. Review component README files
3. Check API docs at `http://localhost:8000/docs` (when running)

---

**Built with** ❤️ **for the magicpin AI Challenge 2026**
