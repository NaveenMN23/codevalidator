# Platform Design System

Shared visual language for `platform-ui` and `admin-ui`.  
**Single source of truth: `platform-ui/src/index.css`**

---

## Color Tokens

All values live in `platform-ui/src/index.css`. Change them once — every screen updates.

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--bg-main` | `#f4f4f6` | `#0f0f17` | Page background |
| `--bg-panel` | `#ffffff` | `#16161f` | Cards, navbar, sidebar surfaces |
| `--bg-elevated` | `#f9f9fb` | `#1c1c28` | Inputs, code blocks, terminal bg |
| `--text-main` | `#0f172a` | `#f1f5f9` | Primary text |
| `--text-muted` | `#6b7280` | `#94a3b8` | Labels, subtitles, secondary text |
| `--border-main` | `#e5e7eb` | `#2d2d3d` | All borders |
| `--accent-color` | `#2563eb` | `#6366f1` | Primary CTA, links, active states |
| `--terminal-selection-bg` | `rgba(37,99,235,0.2)` | `rgba(99,102,241,0.2)` | xterm.js selection highlight |

---

## Tailwind Class Map

These Tailwind utilities resolve to the CSS tokens above.

| Class | Resolves to |
|-------|------------|
| `bg-background` | `--bg-main` |
| `bg-panel` | `--bg-panel` |
| `bg-bg-elevated` | `--bg-elevated` |
| `text-text-main` | `--text-main` |
| `text-text-muted` | `--text-muted` |
| `border-border-main` | `--border-main` |
| `bg-primary` / `text-primary` | `--accent-color` |

The `dark:` prefix works via `data-theme="dark"` on `<html>` (configured with `@custom-variant dark` in index.css).

---

## Typography

| Property | Value |
|----------|-------|
| Font family | `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif` |
| Base size | `14px` |
| Line height | `1.5` |
| Monospace (terminal/editor) | `'JetBrains Mono', 'Fira Code', monospace` |

---

## Component Patterns

### Page layout
```css
background: var(--bg-main);   /* gray page */
color: var(--text-main);
```

### Card / Panel
```css
background: var(--bg-panel);  /* white in light, #16161f in dark */
border: 1px solid var(--border-main);
border-radius: 16px;          /* login card */
border-radius: 8px;           /* standard card / glass-panel */
padding: 40px 36px;           /* login */
padding: 20px 24px;           /* standard */
```

### Input field
```css
background: var(--bg-elevated);
border: 1px solid var(--border-main);
border-radius: 8px;
padding: 10px 14px;
font-size: 14px;
color: var(--text-main);
outline: none;
box-sizing: border-box;
```

### Label
```css
font-size: 13px;
font-weight: 500;
color: var(--text-main);
margin-bottom: 6px;
display: block;
```

### Primary button (black CTA)
```css
background: #000;             /* stays black in both modes */
color: #fff;
border: none;
border-radius: 8px;
padding: 11px 0;
font-size: 14px;
font-weight: 600;
width: 100%;
```

### Outlined button
```css
background: var(--bg-panel);
border: 1px solid var(--border-main);
border-radius: 8px;
color: var(--text-main);
font-size: 14px;
font-weight: 500;
```

### Accent button (in Tailwind)
```
bg-primary text-white px-4 py-2 rounded-lg
```

---

## Dark Mode

Mechanism: `document.documentElement.setAttribute('data-theme', 'dark')`  
Persisted via Zustand `persist` middleware → `localStorage`.  
Toggle: Sun/Moon icon in Navbar.

Tailwind `dark:` classes are wired to `[data-theme=dark]` via:
```css
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));
```

---

## Scrollbars
```css
width: 4px; height: 4px;
track: transparent;
thumb: var(--border-main);
thumb:hover: var(--accent-color);
```

---

## Semantic Colors (intentional, not overridden by theme)

These are kept in components and are NOT part of the neutral palette.

| Use case | Color |
|----------|-------|
| Success / Beginner difficulty | `text-green-*`, `border-green-*` |
| Error / Advanced difficulty | `text-red-*`, `border-red-*` |
| Intermediate difficulty | `text-blue-*`, `border-blue-*` |
| Grading feedback: Efficiency | `text-blue-*` |
| Grading feedback: Correctness | `text-green-*` |
| Gamification: streak | `orange-*` |
| Gamification: rank | `blue-*` |
| Gamification: progress | `purple-*` |
| Status indicator: ready | `bg-green-500` |
| Status indicator: disconnected | `bg-red-500` |

---

## File Map — What to Change

| What you want to change | File |
|-------------------------|------|
| Any color, border, or surface | `platform-ui/src/index.css` ← **start here** |
| Terminal colors | automatically reads CSS vars — no separate change needed |
| Login / Signup layout | `platform-ui/src/features/auth/components/Login.tsx` / `Signup.tsx` |
| Navbar | `platform-ui/src/components/ui/Navbar.tsx` |
| Dashboard cards / badges | `platform-ui/src/features/dashboard/components/Dashboard.tsx` |
| Workspace IDE chrome | `platform-ui/src/features/workspace/components/Workspace.tsx` |
| IDE prose / scrollbar / gutter | `platform-ui/src/features/workspace/components/Workspace.css` |
| Auth page routing (hide navbar) | `platform-ui/src/App.tsx` |
| admin-ui colors | `admin-ui/src/index.css` (separate app, same token values) |

---

## Applying This Design to a New App (one-shot)

1. Copy the `:root` and `[data-theme='dark']` blocks from `platform-ui/src/index.css`
2. Add the `@custom-variant dark` directive for Tailwind `dark:` support
3. Set `font-family: var(--font-sans)` and `font-size: 14px` on body
4. Set dark mode via `document.documentElement.setAttribute('data-theme', theme)`
5. Any terminal/editor component reads CSS vars via `getComputedStyle(document.documentElement).getPropertyValue('--token-name').trim()`
