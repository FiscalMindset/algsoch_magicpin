#!/bin/bash

# List the full directory structure
echo "📁 Vera AI Project Structure"
echo "=============================="
echo ""

tree -I 'node_modules|__pycache__|.git' -L 3 << 'EOF'
magicpin-ai-challenge/
├── backend/                           # 🔙 FastAPI Server
│   ├── app/
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── context.py            # Context schemas
│   │   │   └── composition.py        # Response schemas
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── composition.py        # Core logic (ContextStore, ConversationManager, CompositionService)
│   │   │   └── state.py              # Global state
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py             # GET /v1/healthz, GET /v1/metadata
│   │   │   ├── context.py            # POST /v1/context
│   │   │   ├── tick.py               # POST /v1/tick
│   │   │   └── reply.py              # POST /v1/reply
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   └── formatters.py
│   │   ├── __init__.py
│   │   └── main.py                   # FastAPI app definition
│   ├── tests/                        # Unit tests
│   ├── main.py                       # Entry point
│   ├── requirements.txt              # Python dependencies
│   ├── Dockerfile                    # Container config
│   ├── .env.example                  # Env template
│   ├── .gitignore
│   └── README.md
│
├── frontend/                          # 💻 React Dashboard
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx            # Top nav
│   │   │   ├── Header.css
│   │   │   ├── Sidebar.jsx           # Left menu
│   │   │   ├── Sidebar.css
│   │   │   ├── Layout.jsx            # Page wrapper
│   │   │   ├── Layout.css
│   │   │   ├── Card.jsx              # Generic card
│   │   │   ├── Card.css
│   │   │   ├── StatBox.jsx           # Metric box
│   │   │   ├── StatBox.css
│   │   │   └── index.js
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx         # Main dashboard
│   │   │   ├── Dashboard.css
│   │   │   ├── Conversations.jsx     # Conversations
│   │   │   ├── Conversations.css
│   │   │   ├── Analytics.jsx         # Analytics
│   │   │   ├── Analytics.css
│   │   │   ├── Settings.jsx          # Settings
│   │   │   ├── Settings.css
│   │   │   └── index.js
│   │   ├── hooks/
│   │   │   ├── useBot.js             # Bot status hook
│   │   │   └── index.js
│   │   ├── services/
│   │   │   ├── api.js                # API client
│   │   │   └── index.js
│   │   ├── utils/
│   │   │   ├── formatters.js
│   │   │   └── index.js
│   │   ├── styles/
│   │   │   └── globals.css           # Global styles
│   │   ├── assets/                   # Images, icons
│   │   ├── App.jsx                   # Main component
│   │   ├── App.css
│   │   └── main.jsx                  # Entry point
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── Dockerfile
│   ├── .env.example
│   ├── .gitignore
│   └── README.md
│
├── dataset/                           # Base dataset (provided)
├── examples/                          # Examples
├── challenge-brief.md                 # Business requirements
├── challenge-testing-brief.md         # API spec
├── engagement-design.md               # Engagement framework
├── engagement-research.md             # Research context
│
├── 📖 DOCUMENTATION FILES
├── QUICK-START.md                     # Start here! 🚀
├── README-FULL-STACK.md              # Full overview
├── DEVELOPMENT.md                     # Architecture & dev guide
├── .gitignore
│
├── 🐳 DOCKER & SCRIPTS
├── docker-compose.yml                 # Multi-container setup
├── setup.sh                           # Setup script
├── start.sh                           # Docker start script
└── cleanup.sh                         # Cleanup script

KEY FEATURES:
=============

✅ Backend (FastAPI):
   - 5 required HTTP endpoints
   - Idempotent context storage with versioning
   - Auto-reply detection
   - Multi-turn conversation tracking
   - LLM integration (Claude Opus 4.7)
   - Async/await patterns
   - Comprehensive error handling

✅ Frontend (React):
   - File-based CSS styling (no monolith!)
   - 4 main pages (Dashboard, Conversations, Analytics, Settings)
   - Responsive design (mobile-first)
   - Real-time bot monitoring
   - Professional UI with Tailwind CSS

✅ Infrastructure:
   - Docker & Docker Compose ready
   - Environment templates (.env.example)
   - Helper scripts for setup/teardown
   - Complete documentation

STYLING PHILOSOPHY:
===================

Each component has its own CSS file:
  ✅ Header.jsx + Header.css
  ✅ Card.jsx + Card.css
  ✅ Dashboard.jsx + Dashboard.css
  
No global CSS file = No naming conflicts = Scalable!

QUICK COMMANDS:
===============

# Setup
bash setup.sh

# Start with Docker
bash start.sh

# Start manually
cd backend && python main.py    # Terminal 1
cd frontend && npm run dev      # Terminal 2

# Access
Frontend: http://localhost:5173
API Docs: http://localhost:8000/docs

NEXT STEPS:
===========

1. Read QUICK-START.md
2. Run setup.sh or start.sh
3. Open http://localhost:5173
4. Check backend at http://localhost:8000/docs
5. Explore DEVELOPMENT.md for deep dive

Happy building! 🚀
EOF
