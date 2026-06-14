# Frontend Coding Standards
### React + Vite + TypeScript

> This document is the single source of truth for frontend architecture, styling, and coding conventions across all projects. All contributors must follow these standards. PRs that deviate without documented justification will be rejected.

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Project Structure](#2-project-structure)
3. [TypeScript Standards](#3-typescript-standards)
4. [Component Standards](#4-component-standards)
5. [Methods & Functions](#5-methods--functions)
6. [Styling Architecture](#6-styling-architecture)
7. [State Management](#7-state-management)
8. [Data Fetching](#8-data-fetching)
9. [Forms](#9-forms)
10. [Performance](#10-performance)
11. [Vite Configuration](#11-vite-configuration)
12. [Testing](#12-testing)
13. [Accessibility](#13-accessibility)
14. [Git & PR Standards](#14-git--pr-standards)

---

## 1. Tech Stack

| Concern | Tool | Reason |
|---|---|---|
| Framework | React 18 | Industry standard, concurrent features |
| Build tool | Vite | Fast HMR, native ESM, first-class TS |
| Language | TypeScript (strict) | Correctness at scale |
| Styling | Tailwind CSS v4 | Utility-first, fast prototyping, unified theme config |
| Animation | Framer Motion | Smooth, declarative animations for UI feedback |
| State (server) | TanStack Query v5 | Cache, invalidation, background sync |
| State (global) | Zustand | Minimal API, no boilerplate |
| State (forms) | React Hook Form + Zod | Performance, schema-driven validation |
| Routing | React Router v6 | Mature, nested routes, lazy loading |
| HTTP | Axios (wrapped) | Interceptors, typed responses |
| Testing (unit) | Vitest + Testing Library | Shares Vite config, fast |
| Testing (E2E) | Playwright | Reliable, Vite-native |
| Linting | ESLint + `@typescript-eslint` | Enforced in CI |
| Formatting | Prettier | Non-negotiable, no manual formatting |
| Git hooks | Husky + lint-staged | Block bad commits at source |

---

## 2. Project Structure

```
src/
├── assets/                   # Static files only (images, fonts, icons)
│   ├── fonts/
│   ├── icons/
│   └── images/
│
├── components/               # Shared, reusable, domain-agnostic components
│   └── ui/                   # Primitives: Button, Input, Modal, Badge, etc.
│       ├── Button/
│       │   ├── Button.tsx
│       │   ├── Button.module.scss
│       │   ├── Button.test.tsx
│       │   └── index.ts
│       └── ...
│
├── features/                 # Domain-driven feature slices
│   └── auth/                 # Each feature is self-contained
│       ├── components/       # Components used only in this feature
│       ├── hooks/            # Hooks used only in this feature
│       ├── stores/           # Zustand slices scoped to this feature
│       ├── api.ts            # API calls for this feature
│       ├── auth.types.ts     # Types scoped to this feature
│       ├── auth.utils.ts     # Pure utility functions
│       └── index.ts          # Public barrel export — only expose public API
│
├── hooks/                    # Global shared hooks (useDebounce, useMediaQuery)
├── lib/                      # Third-party wrappers and configured instances
│   ├── axios.ts              # Configured Axios instance
│   ├── queryClient.ts        # TanStack Query client config
│   └── i18n.ts               # i18n setup if applicable
│
├── pages/                    # Route-level components only — thin wrappers
│   ├── DashboardPage.tsx
│   └── ...
│
├── router/                   # Route definitions and lazy imports
│   └── index.tsx
│
├── stores/                   # Global Zustand stores (cross-feature state)
│
├── styles/                   # Global SCSS (NOT component styles)
│   ├── tokens.scss           # Design tokens: colors, spacing, radii, shadows
│   ├── reset.scss            # CSS reset/normalize
│   ├── typography.scss       # Global type styles, font-face declarations
│   ├── utilities.scss        # Reusable utility classes (use sparingly)
│   ├── animations.scss       # Keyframe animations
│   └── index.scss            # Entry point — imports all of the above
│
├── types/                    # Shared TypeScript types and interfaces
│   └── api.types.ts
│
└── utils/                    # Pure functions — NO React imports, NO side effects
    ├── format.utils.ts
    └── date.utils.ts
```

### Naming Rules

| Thing | Convention | Example |
|---|---|---|
| Component files | `PascalCase.tsx` | `UserCard.tsx` |
| Hook files | `camelCase.ts` prefixed `use` | `useAuthUser.ts` |
| Utility files | `camelCase.utils.ts` | `format.utils.ts` |
| Type files | `camelCase.types.ts` | `api.types.ts` |
| SCSS modules | `ComponentName.module.scss` | `Button.module.scss` |
| Global SCSS | `lowercase.scss` | `tokens.scss` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Directories | `camelCase` | `features/userProfile/` |

---

## 3. TypeScript Standards

**Strict mode is mandatory.** `tsconfig.json` must include:

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "exactOptionalPropertyTypes": true
  }
}
```

### Rules

```ts
// ✅ Use interface for object shapes
interface UserProfile {
  id: string
  email: string
  role: 'admin' | 'editor' | 'viewer'
  createdAt: Date
}

// ✅ Use type for unions, intersections, aliases
type ApiStatus = 'idle' | 'loading' | 'success' | 'error'
type AdminUser = UserProfile & { permissions: string[] }

// ❌ Never use `any` — use `unknown` and narrow it
function processData(input: any) { ... }         // bad
function processData(input: unknown) { ... }     // good

// ❌ Never use non-null assertion carelessly
const name = user!.profile!.name                 // bad — hides runtime errors
const name = user?.profile?.name ?? 'Anonymous'  // good

// ✅ Enums: use const enums or plain string unions — avoid regular enums
// (regular enums compile to IIFEs and bloat bundles)
const ROUTES = {
  HOME: '/',
  DASHBOARD: '/dashboard',
} as const
type Route = typeof ROUTES[keyof typeof ROUTES]
```

### Path Aliases

Configure in both `tsconfig.json` and `vite.config.ts`:

```json
// tsconfig.json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@components/*": ["./src/components/*"],
      "@features/*": ["./src/features/*"],
      "@styles/*": ["./src/styles/*"]
    }
  }
}
```

Use `vite-tsconfig-paths` plugin — no duplication needed in Vite config.

---

## 4. Component Standards

### Structure

Every component file follows this exact order:

```tsx
// 1. External imports (React, libraries)
import { useState, useCallback } from 'react'
import clsx from 'clsx'

// 2. Internal imports (features, components, hooks, utils)
import { useAuthUser } from '@features/auth'
import { Avatar } from '@components/ui/Avatar'
import { formatDate } from '@/utils/format.utils'

// 3. Type/style imports
import type { UserProfile } from '@/types/api.types'
import styles from './UserCard.module.scss'

// 4. Props interface — directly above the component
interface UserCardProps {
  user: UserProfile
  isCompact?: boolean
  onSelect: (id: string) => void
}

// 5. Named export — never anonymous default exports
export function UserCard({ user, isCompact = false, onSelect }: UserCardProps) {
  // 5a. Hooks first
  const { currentUser } = useAuthUser()

  // 5b. Derived state / computed values
  const isOwnProfile = currentUser?.id === user.id

  // 5c. Handlers (named functions — never inline in JSX)
  const handleSelect = useCallback(() => {
    onSelect(user.id)
  }, [onSelect, user.id])

  // 5d. Early returns for loading/error/empty states
  if (!user) return null

  // 5e. JSX return
  return (
    <div className={clsx(styles.card, { [styles.compact]: isCompact })}>
      <Avatar src={user.avatar} alt={user.email} />
      <p className={styles.name}>{user.email}</p>
      <button type="button" onClick={handleSelect}>
        {isOwnProfile ? 'View my profile' : 'View profile'}
      </button>
    </div>
  )
}
```

### Rules

- **One component per file.** File name must match component name exactly.
- **150 line soft limit.** If a component exceeds this, extract sub-components or a custom hook.
- **Never define components inside other components.** It breaks React reconciliation and creates new function references every render.
- **Never use `React.FC`.** Typing props directly gives better inference and avoids implicit `children`.
- **Keep pages thin.** Pages fetch data and compose features. No UI logic, no direct API calls in page files.
- **Default exports are banned** for components. Named exports only — they improve refactoring and search.

```tsx
// ❌ Bad — anonymous, default export
export default () => <div />

// ❌ Bad — component inside component
function Parent() {
  function InnerChild() { return <span /> }  // re-created every render
  return <InnerChild />
}

// ✅ Good — named, typed, exported correctly
export function ProductCard({ product }: ProductCardProps) { ... }
```

---

## 5. Methods & Functions

This is where most consistency issues arise. Follow these rules without exception.

### No Inline Functions in JSX

Inline functions create a new reference on every render, defeating memoization and making code harder to read.

```tsx
// ❌ Bad — inline arrow function in JSX
<button onClick={() => handleDelete(item.id)}>Delete</button>

// ❌ Bad — inline object in JSX
<Component style={{ marginTop: 8 }} />

// ✅ Good — named handler, defined in the component body
const handleDeleteClick = useCallback(() => {
  handleDelete(item.id)
}, [handleDelete, item.id])

<button type="button" onClick={handleDeleteClick}>Delete</button>
```

**Exception:** Trivial refs and stable primitives are acceptable:
```tsx
// Acceptable — stable reference, no computation
<input ref={(el) => (inputRef.current = el)} />
```

### Handler Naming Convention

All event handlers follow the `handle[Subject][Event]` pattern:

```ts
// ✅ Correct naming
const handleFormSubmit = () => { ... }
const handleUserSelect = (id: string) => { ... }
const handleModalClose = () => { ... }
const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => { ... }

// ❌ Incorrect
const onClick = () => { ... }       // too generic
const submit = () => { ... }        // missing "handle" prefix
const doDelete = () => { ... }      // "do" prefix is meaningless
```

Props that accept handlers are named `on[Subject][Event]`:

```tsx
interface TableProps {
  onRowSelect: (id: string) => void   // ✅
  onSortChange: (col: string) => void // ✅
  onClick?: () => void                // ❌ too generic — be specific
}
```

### Function Placement Rules

```ts
// RULE 1: Pure utility functions → src/utils/ (not inside components)
// These have zero React dependencies

// src/utils/format.utils.ts
export function formatCurrency(amount: number, currency = 'INR'): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(amount)
}

// RULE 2: Hooks that use React APIs → src/hooks/ or feature/hooks/
// src/hooks/useDebounce.ts
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debouncedValue
}

// RULE 3: Component-specific handlers → defined inside the component,
// wrapped in useCallback only when passed as props or used as hook dependencies

// RULE 4: API calls → src/features/[feature]/api.ts (never inline in components)
```

### useCallback and useMemo Rules

Only add these when you can explain *why*:

```ts
// ✅ useCallback — handler is passed as prop to a memoized child
const handleRowClick = useCallback((id: string) => {
  navigate(`/users/${id}`)
}, [navigate])

// ✅ useMemo — expensive computation (sorting/filtering large arrays)
const sortedItems = useMemo(
  () => [...items].sort((a, b) => a.name.localeCompare(b.name)),
  [items]
)

// ❌ useMemo/useCallback — no expensive work, not passed to memoized child
const fullName = useMemo(() => `${user.firstName} ${user.lastName}`, [user])
// Just write: const fullName = `${user.firstName} ${user.lastName}`
```

---

## 6. Styling Architecture

### Decision: Tailwind CSS v4 + Framer Motion

We formally use **Tailwind CSS v4** as the primary styling system and **Framer Motion** for animations.

- **Utility-First** — Rapid prototyping and built-in consistency via Tailwind.
- **Glassmorphism** — Heavy use of backdrop-blur, semi-transparent backgrounds (`bg-background/50`), and subtle borders.
- **Animations** — Declarative animations using Framer Motion (`<motion.div>`) for layout transitions and micro-interactions.

We do **not** use:
- SCSS Modules or standard CSS (except for strict overrides).
- CSS-in-JS libraries (Styled Components, Emotion).

### File Locations

- `src/index.css`: Global Tailwind entry point and deep dark mode configuration.
- `tailwind.config.js`: Centralized theme tokens.


## 7. State Management

### Decision Tree

```
Is this state only used in one component?
  └─ Yes → useState / useReducer

Is this state shared across siblings (but within a feature)?
  └─ Yes → lift state up, or a feature-scoped Zustand slice

Is this state rarely updated shared config (theme, locale, auth)?
  └─ Yes → React Context

Is this data from a server?
  └─ Yes → TanStack Query. Period. Never useState.

Is this high-frequency cross-feature client state?
  └─ Yes → Zustand global store
```

### Zustand Store Pattern

```ts
// src/stores/uiStore.ts
import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

interface UiStore {
  sidebarOpen: boolean
  openSidebar: () => void
  closeSidebar: () => void
  toggleSidebar: () => void
}

export const useUiStore = create<UiStore>()(
  devtools(
    (set) => ({
      sidebarOpen: false,
      openSidebar:  () => set({ sidebarOpen: true },  false, 'ui/openSidebar'),
      closeSidebar: () => set({ sidebarOpen: false }, false, 'ui/closeSidebar'),
      toggleSidebar: () => set(
        (state) => ({ sidebarOpen: !state.sidebarOpen }),
        false,
        'ui/toggleSidebar'
      ),
    }),
    { name: 'UiStore' }
  )
)
```

---

## 8. Data Fetching

### Query Key Factory

All query keys live in one file per feature. Never inline string arrays in `useQuery`:

```ts
// src/features/users/queryKeys.ts
export const userKeys = {
  all:    ()         => ['users']                    as const,
  lists:  ()         => [...userKeys.all(), 'list']  as const,
  list:   (filter: UserFilter) => [...userKeys.lists(), filter] as const,
  detail: (id: string) => [...userKeys.all(), id]   as const,
}
```

### Custom Query Hooks

Wrap every `useQuery` and `useMutation` in a custom hook. Components never call TanStack Query directly:

```ts
// src/features/users/hooks/useUser.ts
import { useQuery } from '@tanstack/react-query'
import { userKeys } from '../queryKeys'
import { fetchUser } from '../api'

export function useUser(id: string) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn:  () => fetchUser(id),
    staleTime: 5 * 60 * 1000,  // 5 minutes
    enabled:   Boolean(id),
  })
}
```

```ts
// src/features/users/hooks/useUpdateUser.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { userKeys } from '../queryKeys'
import { updateUser } from '../api'

export function useUpdateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: updateUser,
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: userKeys.detail(variables.id) })
    },
  })
}
```

### API Layer

```ts
// src/features/users/api.ts
import { apiClient } from '@/lib/axios'
import type { User, UpdateUserPayload } from './auth.types'

export async function fetchUser(id: string): Promise<User> {
  const { data } = await apiClient.get<User>(`/users/${id}`)
  return data
}

export async function updateUser(payload: UpdateUserPayload): Promise<User> {
  const { data } = await apiClient.patch<User>(`/users/${payload.id}`, payload)
  return data
}
```

---

## 9. Forms

All forms use **React Hook Form** with **Zod** validation. No exceptions.

```ts
// src/features/auth/components/LoginForm.tsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

// 1. Define schema first — TypeScript type is inferred from it
const loginSchema = z.object({
  email:    z.string().email('Enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

type LoginFormValues = z.infer<typeof loginSchema>

export function LoginForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  // Named handler — never inline in JSX
  const handleFormSubmit = async (values: LoginFormValues) => {
    await login(values)
  }

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      <div>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" {...register('email')} />
        {errors.email && <p role="alert">{errors.email.message}</p>}
      </div>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  )
}
```

---

## 10. Performance

### Memoization: When to Apply

| Hook | Use when | Do NOT use when |
|---|---|---|
| `useMemo` | Computation takes >1ms or returns a new object passed to a memoized child | Simple concatenation, formatting, boolean checks |
| `useCallback` | Function is passed as prop to `React.memo` component or is a `useEffect` dependency | Handler only used in the current component's JSX |
| `React.memo` | Component re-renders frequently with identical props | Default — profile first |

**Always profile before adding memoization.** Use React DevTools Profiler.

### Code Splitting

```tsx
// src/router/index.tsx — all routes are lazy loaded
import { lazy, Suspense } from 'react'
import { PageLoader } from '@components/ui/PageLoader'

const DashboardPage = lazy(() => import('@pages/DashboardPage'))
const SettingsPage  = lazy(() => import('@pages/SettingsPage'))

export function AppRouter() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/settings"  element={<SettingsPage />} />
      </Routes>
    </Suspense>
  )
}
```

Also lazy-load heavy UI: rich text editors, chart libraries, date pickers.

### List Rendering

```tsx
// ✅ Stable keys — never array index for dynamic lists
{users.map((user) => (
  <UserCard key={user.id} user={user} onSelect={handleUserSelect} />
))}

// ✅ Virtualize large lists
import { useVirtualizer } from '@tanstack/react-virtual'
// Use when list length > 100 items
```

---

## 11. Vite Configuration

```ts
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'   // SWC for faster builds
import tsconfigPaths from 'vite-tsconfig-paths' // Resolves @/ aliases
import checker from 'vite-plugin-checker'       // TS errors in dev overlay

export default defineConfig({
  plugins: [
    react(),
    tsconfigPaths(),
    checker({ typescript: true }),
  ],

  css: {
    preprocessorOptions: {
      scss: {
        // Automatically available in every .module.scss — no manual @use needed
        additionalData: `@use "@styles/tokens" as t; @use "@styles/mixins" as m;`,
      },
    },
  },

  build: {
    target: 'es2020',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react':  ['react', 'react-dom'],
          'vendor-router': ['react-router-dom'],
          'vendor-query':  ['@tanstack/react-query'],
          'vendor-forms':  ['react-hook-form', 'zod', '@hookform/resolvers'],
        },
      },
    },
  },

  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },

  preview: {
    port: 4000,
  },
})
```

### Environment Variables

```bash
# .env              — defaults, safe to commit
VITE_APP_NAME=MyApp

# .env.local        — overrides, NEVER committed
VITE_API_URL=http://localhost:8080

# .env.production   — production values
VITE_API_URL=https://api.myapp.com
```

- Prefix with `VITE_` to expose to client code
- Access via `import.meta.env.VITE_*`
- **Never** put secrets (API keys, tokens) in `VITE_*` — they're bundled into the client

---

## 12. Testing

### Philosophy

Test **behavior**, not implementation. Ask: "If I refactor this without changing behavior, do my tests still pass?" If no, the test is testing implementation.

### Vitest + Testing Library

```ts
// src/components/ui/Button/Button.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { Button } from './Button'

describe('Button', () => {
  it('calls onPress when clicked', async () => {
    const handlePress = vi.fn()
    render(<Button onPress={handlePress}>Save changes</Button>)

    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(handlePress).toHaveBeenCalledOnce()
  })

  it('is disabled and non-interactive when disabled prop is set', async () => {
    const handlePress = vi.fn()
    render(<Button onPress={handlePress} disabled>Save changes</Button>)

    await userEvent.click(screen.getByRole('button'))

    expect(handlePress).not.toHaveBeenCalled()
  })
})
```

### Coverage Targets

| Type | Target |
|---|---|
| Utility functions | 90%+ |
| Custom hooks | 80%+ |
| UI primitives | 80%+ |
| Feature components | 60%+ |
| Pages | E2E coverage |

---

## 13. Accessibility

These are not optional. Every component ships accessible.

- **Keyboard navigation** — every interactive element is reachable and operable via keyboard
- **Focus rings** — never `outline: none` without a visible replacement. Use the `focus-ring` mixin.
- **Semantic HTML** — use `<button>` for actions, `<a>` for navigation, `<nav>` for navigation regions. Never `<div onClick>`.
- **ARIA labels** — icon-only buttons require `aria-label`. Dynamic content uses `aria-live`.
- **Color contrast** — minimum 4.5:1 for body text, 3:1 for large text and UI components.
- **`alt` text** — all `<img>` elements. Decorative images use `alt=""`.
- **Form labels** — every input has a visible `<label>` with matching `htmlFor`/`id`.
- **Error messages** — use `role="alert"` so screen readers announce them immediately.
- **Touch targets** — minimum 44×44px on mobile.

---

## 14. Git & PR Standards

### Commit Messages (Conventional Commits)

```
<type>(<scope>): <short summary>

feat(auth): add OAuth2 login flow
fix(dashboard): correct revenue calculation for partial months
refactor(ui): extract Button variant logic into separate hook
chore(deps): upgrade TanStack Query to v5
docs: update CSS architecture section in README
test(users): add missing edge cases for useUser hook
```

Types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `style`, `perf`

### PR Checklist

Before requesting review, confirm:

- [ ] TypeScript compiles with zero errors (`tsc --noEmit`)
- [ ] ESLint passes with zero errors (`eslint src/`)
- [ ] All new components have tests
- [ ] No `console.log` left in code
- [ ] No inline styles added (unless genuinely dynamic)
- [ ] No new hardcoded color/spacing values outside `tokens.scss`
- [ ] New API calls go through the `api.ts` layer, not directly in components
- [ ] Accessibility: keyboard navigable, has ARIA where needed

### Branch Naming

```
feat/user-profile-page
fix/cart-total-rounding
refactor/button-component
chore/upgrade-react-18
```

---

## Quick Reference Card

```
New UI component?
  → src/components/ui/ComponentName/
    ├── ComponentName.tsx       (named export, props interface above)
    ├── ComponentName.module.scss  (@use tokens + mixins, no hardcoded values)
    ├── ComponentName.test.tsx
    └── index.ts

New feature?
  → src/features/featureName/
    ├── components/
    ├── hooks/         (useQuery/useMutation wrapped in custom hooks)
    ├── api.ts         (all fetch calls here, nowhere else)
    ├── queryKeys.ts   (TanStack Query key factories)
    ├── stores/        (Zustand slice if needed)
    ├── featureName.types.ts
    └── index.ts       (public barrel — export only what consumers need)

New design value?
  → src/styles/tokens.scss ONLY
  → Reference via @use and t.$token-name

New handler in a component?
  → Named function: const handleUserSelect = useCallback(...)
  → NEVER inline: onClick={() => ...}
```

---