# File-Based CSS Styling Reference

## Philosophy

Every component and page has its own dedicated CSS file. This approach:

✅ **Eliminates naming conflicts** — Use generic class names like `.card`, `.header`
✅ **Keeps styles co-located** — CSS lives right next to the component
✅ **Scales easily** — Add new components without worrying about existing styles
✅ **Enables easy debugging** — Find what's styling a component immediately
✅ **Maintains performance** — Only load styles that are needed

## Examples

### Component Pairing

```
components/
├── Card.jsx
├── Card.css          ← Styles for Card component
├── StatBox.jsx
└── StatBox.css       ← Styles for StatBox component
```

**Card.jsx:**
```jsx
function Card({ title, children }) {
  return (
    <div className="card">
      {title && <h3 className="card-title">{title}</h3>}
      <div className="card-body">{children}</div>
    </div>
  );
}
```

**Card.css:**
```css
.card {
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.card-title {
  font-weight: 600;
  color: #1e293b;
}

.card-body {
  padding: 1.5rem;
}
```

### Page Pairing

```
pages/
├── Dashboard.jsx
├── Dashboard.css     ← All Dashboard-specific styles
├── Conversations.jsx
└── Conversations.css ← All Conversations-specific styles
```

**Dashboard.jsx:**
```jsx
import './Dashboard.css';

function Dashboard() {
  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>Dashboard</h2>
      </div>
      <div className="stats-grid">
        {/* content */}
      </div>
    </div>
  );
}
```

**Dashboard.css:**
```css
.dashboard {
  animation: fadeIn 0.3s ease-in;
}

.dashboard-header {
  margin-bottom: 2rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
}

/* Responsive design */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
```

## Naming Conventions

### Use the Component Name as Prefix

```css
/* ✅ Good - prefixed with component name */
.card { ... }
.card-header { ... }
.card-title { ... }
.card-body { ... }

/* ❌ Bad - too generic, risks conflicts */
.header { ... }
.title { ... }
.body { ... }
```

### Use BEM-style Modifiers

```css
/* ✅ Good - clear hierarchy */
.button { ... }
.button-primary { ... }
.button-secondary { ... }

.status { ... }
.status-active { ... }
.status-inactive { ... }

/* ❌ Bad - unclear */
.btn { ... }
.btn1 { ... }
.btn2 { ... }
```

## Utility Classes with Tailwind

Mix Tailwind utilities with component styles:

```jsx
<div className="card p-6 rounded-lg shadow-sm">
  {/* Component structure */}
</div>
```

Or define utilities in CSS:

```css
.card {
  @apply bg-white rounded-lg shadow-sm;
}
```

## Global vs Component Styles

### Global Styles (`src/styles/globals.css`)

```css
/* Only truly global styles here */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #root {
  height: 100%;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', ...;
  background-color: #f8fafc;
}
```

### Component Styles (e.g., `Card.css`)

```css
/* All component-specific styles here */
.card {
  background: white;
  /* ... */
}
```

## Scale Example

As you add components, each gets its own file:

```
Growing codebase:
├── components/
│   ├── Header.jsx      ✅ Styled in Header.css
│   ├── Header.css
│   ├── Card.jsx        ✅ Styled in Card.css
│   ├── Card.css
│   ├── Modal.jsx       ✅ Styled in Modal.css
│   ├── Modal.css
│   ├── Button.jsx      ✅ Styled in Button.css
│   ├── Button.css
│   ├── Form.jsx        ✅ Styled in Form.css
│   └── Form.css

No style conflicts! 🎉
```

## Responsive Design Pattern

```css
.component {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
}

@media (max-width: 768px) {
  .component {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
}
```

## Animation Utilities

Keep animations near their components:

```css
/* In Card.css */
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.card {
  animation: slideIn 0.3s ease-out;
}
```

## Dark Mode Ready

Prepare for dark mode from the start:

```css
.card {
  background: white;
  color: #1e293b;
}

@media (prefers-color-scheme: dark) {
  .card {
    background: #1e293b;
    color: white;
  }
}
```

## Performance Tips

1. **Keep CSS files small** — One CSS file per component
2. **Use CSS modules** (optional) — If you want even more isolation
3. **Avoid duplicate styles** — Use component composition
4. **Leverage Tailwind** — For utility classes, reduces custom CSS
5. **Tree-shaking** — Only loaded CSS for mounted components

## Summary

This approach gives you:
- ✅ **Maintainability** — Easy to find and update styles
- ✅ **Scalability** — Add components without conflicts
- ✅ **Clarity** — Clear relationship between code and styles
- ✅ **Performance** — Load only needed styles
- ✅ **Teamwork** — No merge conflicts on CSS files

**The key principle:** Each file (JSX) + its styles (CSS) = one unit of code.
