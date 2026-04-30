# Vera AI Dashboard — Frontend

React-based dashboard for the Vera AI merchant assistant bot.

## Structure

```
frontend/
├── src/
│   ├── components/       # Reusable UI components (each with .css file)
│   ├── pages/            # Page components (each with .css file)
│   ├── hooks/            # Custom React hooks
│   ├── services/         # API and utility services
│   ├── utils/            # Helper functions
│   ├── assets/           # Images, icons, etc.
│   ├── styles/           # Global styles
│   ├── App.jsx           # Main app component
│   └── main.jsx          # Entry point
├── index.html            # HTML template
├── package.json          # Dependencies
├── vite.config.js        # Vite configuration
└── tailwind.config.js    # Tailwind CSS config
```

## File-Based Styling Approach

Every component and page has its own dedicated `.css` file:

- **Global styles**: `src/styles/globals.css`
- **Component styles**: `src/components/ComponentName.css`
- **Page styles**: `src/pages/PageName.css`

This approach ensures:
- ✅ Style isolation (no naming conflicts)
- ✅ Easy maintenance (style is co-located with component)
- ✅ Scalability (add new components independently)
- ✅ Performance (only load needed styles)

## Setup

```bash
cd frontend
npm install
npm run dev
```

## Pages

1. **Dashboard** — System status, metrics, activity
2. **Conversations** — Active and historical conversations
3. **Analytics** — Performance metrics and insights
4. **Settings** — Bot configuration and team info

## Components

### Core Components
- `Header` — Top navigation bar
- `Sidebar` — Left navigation menu
- `Layout` — Page wrapper
- `Card` — Generic card container
- `StatBox` — Metric display box

### Customization

To add a new page:
1. Create `src/pages/NewPage.jsx`
2. Create `src/pages/NewPage.css`
3. Add route in `App.jsx`
4. Add menu item in `Sidebar.jsx`

To add a new component:
1. Create `src/components/NewComponent.jsx`
2. Create `src/components/NewComponent.css`
3. Import and use in pages

