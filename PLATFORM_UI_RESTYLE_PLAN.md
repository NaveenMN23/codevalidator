# platform-ui — restyle + Problems screen + Workspace (IDE) rebuild

## Context

Consolidated requirements spec for `platform-ui` (React 19 + Vite 6 + Tailwind CSS v4, npm, Node 20/22). Covers three things:

1. Run the frontend **without Docker**.
2. Restyle with a cool, dev-friendly palette (**teal accent**) across **dark + light** themes.
3. Turn the current Dashboard into a real **Problems screen** (`/problems`) and rebuild the buggy **Workspace (IDE)** into a fluid VS Code / Cursor-style layout.

This document is the agreed spec; it is intentionally detailed enough to execute. Theme lives in `src/index.css` (CSS custom properties + Tailwind v4 `@theme` block), toggled by `data-theme` on `<html>` from Zustand (`src/store.ts`), default `dark`. The UI proxies `/api` → `http://localhost:8080` (Java backend). WebContainers were removed — execution is server-side.

**Decisions locked during iteration:**
- Accent color: **teal `#2DD4BF`** (replaces coral; cooler, less flashy). Dark stays primary.
- `/` **redirects to `/problems`**; `/problems` is a real route.
- Editor **scrolls horizontally by default**, with a **word-wrap toggle**.
- Timer stays and must work; **at 0:00 → editor read-only + "Time's up" banner, Submit still available**.
- File locking uses a **convention** now (backend `lockedFiles` later).
- **"Zoom in" = larger font size across the whole Workspace page** (not a `transform: scale()`, not one pane).
- Several placeholder/dead features are **kept, not removed**, and moved to Future scope for real-API integration.

---

## Part A — Run without Docker

```bash
cd /Users/kmeenakshisundaram/Downloads/codevalidator-main/platform-ui
npm install            # if React 19 peer-dep errors: npm install --legacy-peer-deps
npm run dev            # Vite → http://localhost:5173
```

- **Problems** (`GET /api/v1/problems`) shows a themed error state without the backend.
- **Workspace** is behind `ProtectedRoute` → needs login + a challenge id.

To see both screens populated without Docker: run the Java backend on `:8080`, or use mock data for the Future-scope widgets (§3).

---

## 0. Accent color (`src/index.css`)

Replace the current accent (`#000000` light / `#ffffff` dark → these read as "no accent") and any coral with **teal**. Keep variable **names** so all `bg-primary` / `text-primary` / `border-primary` utilities and inline `var(--*)` usages inherit automatically.

| Token | Value |
|---|---|
| `--accent-color` | `#2DD4BF` |
| `--accent-hover` | `#22B8A6` |
| `--accent-strong` | `#14B8A6` (filled buttons) |
| `--accent-soft` | `rgba(45,212,191,0.14)` (tinted hover/active fills) |
| on-accent text | `#06231D` (dark text on teal fills) |

- `@theme`: `--color-primary: var(--accent-color)` (already present). Keep `--color-secondary: #10B981`.
- Audit and replace hardcoded fills: `#000`/`#fff` CTAs, `bg-primary text-white`/`text-background`, active tab borders, difficulty dots/badges.
- Dark theme (`#1e1e1e` base, VS Code palette) stays primary; light theme (`#f4f4f6`) mirrors it.

---

## 1. Problems screen (`/problems`)

Ref for right rail: https://www.hellointerview.com/dashboard. File: `src/features/dashboard/components/Dashboard.tsx`.

**Routing & nav**
- `/problems` is a real route; **`/` redirects to `/problems`** (`src/App.tsx`).
- Add **Pricing** and **Refer** nav items + stub pages (`src/components/ui/Navbar.tsx`).
- Professional, themed navbar (teal accents, no hardcoded `#000`).

**Left sidebar**
- Rename **Challenges → Topics**; list topics (e.g. Concurrency, Databases). *(mock now → codegen taxonomy later)*
- Sidebar is **collapsible**.
- Clicking a topic shows its scenarios as a **content gist** (summary preview), not "Scenario 1 / Scenario 2".

**Main list (replaces the tile grid)**
- **One problem per row**; chevron **expands to a gist** (short description), collapsible.
- **No Start button** — **clicking the row opens** `/workspace/:id`.
- Difficulty shown as a dot/badge (use difficulty tokens, not raw hex `DIFF_META`).

**Right rail** — **Streak** widget + **Newly-released** content as themed cards. *(mock now → real API later)*

**Top** — **Greeting** header ("Good morning / Welcome back"), personalized with the user's name.

**Font note:** Problems listing font is **already correctly sized — validated, leave as-is** (titles 15px, body/badges/sidebar 13px). No font changes here.

---

## 2. Workspace screen (IDE)

Files: `Workspace.tsx`, `Terminal.tsx`, `FileExplorer.tsx`, `FeedbackDisplay.tsx`, `Workspace.css`, `src/index.css`.

### Bugs being fixed (root causes)
1. **Terminal fit bug** — terminal is hidden via a `hidden`/0-size `react-split` pane while still mounted; `FitAddon.fit()` on a 0-dimension node garbles/blanks xterm and never re-fits on show. Fix: don't zero-size the pane; re-fit on show/resize only when the container has non-zero size.
2. **Fragile nested splits** — sizes flip `[25,75]↔[0,100]`; a fixed-width panel outside the split plus an inner vertical split → jumpy toggling. Rebuild so panels reflow smoothly.
3. **Invisible light-mode hovers** — `bg-white/10`, `hover:bg-white/[0.07]` in FileExplorer/Workspace are invisible on the light theme. Replace with a theme-aware hover token.
4. **Duplicate CSS** — `.gutter`, `.prose*`, scrollbar rules risk drifting between `index.css` and `Workspace.css`; keep one owner.

### Layout & chrome
- **Increase font size across the whole Workspace page** ("zoom in"). Today: `text-[9px]` (status bar, timer label, meta), `text-[10px]`/`text-[11px]` (tabs, explorer headers, run/submit buttons), `text-[12px]`/`text-xs` (file tabs, timer value), editor + terminal at `fontSize: 13`. Bump ~one step (9→11, 10→12, 11→12/13, editor & terminal 13→14/15); scale paddings to match.
- **Top navbar redesign:** timer **centered** horizontally; themed; **remove the title/lang/"Node.js Framework" heading block** (`Workspace.tsx` ~427–431).
- **Fix expand/collapse glitch** — rebuild the nested `react-split` (bugs #1/#2).
- **Cursor pointer** on the file-tab close (×) icon (`Workspace.tsx` ~590 — add `cursor-pointer`).

### Editor (Monaco)
- **Horizontal scroll by default**, plus a **word-wrap toggle** (`wordWrap: 'off' ↔ 'on'`). Fixes: typing past the right edge doesn't scroll to the caret.
- **Collapsible method/outline navigator** — list the file's methods/symbols (Monaco document symbols); **click jumps to the method**.
- **File locking (convention, now):** `tests/**`, `pom.xml`, `package.json`, `README.md` → Monaco `readOnly` + 🔒 badge on tab/explorer + excluded from autosave/draft diff. *(→ backend `lockedFiles` metadata later)*

### Terminal & run flow
- Replace **"Sending code to the Execution Service…" → "Validating the code…"** (`Workspace.tsx` `handleRun`, ~243).
- Terminal refits cleanly on show/hide (`Terminal.tsx` — guarded `refit()`; called on show + split `onDragEnd`).

### Problem statement (markdown)
- **Strip the "How to Build and Run" section** from the rendered README before display.
- **Worked examples** — show **expected output + explanation**. *(example content authored via codegen later)*

### Feedback (`FeedbackDisplay.tsx`)
- Surface the worked examples (expected output + explanation) alongside AI feedback.

### Timer
- Accurate wall-clock countdown (no `setInterval` drift); persists/resumes with drafts (`pendingTime`); centered display.
- **At 0:00 → editor becomes read-only + "Time's up" banner; Submit still available.**

---

## 3. Future work (codegen + real APIs)

UI is built against mocks/stubs now; these get wired to real data later. **Kept, not removed.**

- **Topics taxonomy** — generated in `platform-codegen`; UI swaps mock → real endpoint.
- **Streak & Newly-released** — real backend endpoints; UI swaps mock → real.
- **Worked examples** — authored into challenge READMEs via codegen (expected output + explanation).
- **File-lock list** — from challenge metadata (`lockedFiles`) replacing the convention.
- **Google / SSO login** — keep the existing buttons; integrate a real OAuth/SSO API.
- **Dev auto-login** — **kept as-is** (visible in all environments; on backend error it fabricates a session with a hardcoded id + empty token). *Note for record: this allows entering with a fake session in production; retained per explicit decision.*
- **Leaderboard & Profile** — keep the routes/nav links; build real pages backed by data (currently one-word placeholders).

---

## 4. Cosmetic fixes done now (not API work)

- Theme the hardcoded auth colors that break on dark: login/signup **error banner** (`#dc2626` on `#fee2e2`, `Login.tsx` ~137 / `Signup.tsx` ~105) and **icon circles** (`#000`/`#fff`, `Login.tsx` ~124 / `Signup.tsx` ~92) → theme tokens (`--accent-color` / `--bg-main`, danger token for errors).

---

## Affected files (reference)

- `src/index.css` — teal accent tokens, keep single owner of gutter/prose/scrollbar
- `src/App.tsx` — `/problems` + `/` redirect, Pricing/Refer routes
- `src/components/ui/Navbar.tsx` — Pricing, Refer, teal restyle
- `src/features/dashboard/components/Dashboard.tsx` — Problems list rows + expand gist; Topics sidebar; collapsible; right rail (streak/new); greeting; click-row-to-start; difficulty tokens
- `src/features/workspace/components/Workspace.tsx` — font-size bump, centered timer, remove heading, expand/collapse fix, close-icon cursor, editor scroll+wrap toggle, method outline, file locking, "Validating the code…", timer 0:00 behavior, strip "How to Build and Run", examples
- `src/features/workspace/components/Terminal.tsx` — guarded refit on show; larger font
- `src/features/workspace/components/FileExplorer.tsx` — theme-aware hover/selection; 🔒 badge
- `src/features/workspace/components/FeedbackDisplay.tsx` — examples / expected output
- `src/features/workspace/components/Workspace.css` — layout/gutters
- `src/features/auth/components/Login.tsx`, `Signup.tsx` — theme error banner + icon circles (§4)

## Verification

- Run: `cd platform-ui && npm install && npm run dev` → http://localhost:5173.
- `/` redirects to `/problems`; topic sidebar collapses; rows expand to a gist; clicking a row opens the workspace; Pricing/Refer nav present.
- Theme toggle: dark (near-black + teal) and light (neutral + teal) both clean; no invisible hovers; difficulty badges legible in both.
- Workspace: fonts noticeably larger and comfortable; timer centered and counting correctly; 0:00 locks editor + shows banner (Submit still works); expand/collapse smooth; hide/show terminal re-fits with no garbling; locked files read-only with 🔒; method outline jumps; editor scrolls then wraps on toggle; terminal shows "Validating the code…"; no "How to Build and Run"; worked examples render.
- Auth: error banner + icon circles theme-aware in both modes.
- `npm run build` → no TS/Vite regressions.
