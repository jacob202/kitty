---
name: visual-web-app-development
description: Modern, responsive web application development with focus on UI/UX design, accessibility, and performance. Use when asked to build a web app, landing page, dashboard, or interactive UI.
---

## Purpose

Develop visually appealing, production-quality web applications using modern frontend patterns. Covers project scaffolding, component architecture, responsive design, accessibility, and performance optimization.

## When to Activate

Invoke this skill when the user asks to:
- "Build a web app"
- "Create a landing page"
- "Design a dashboard"
- "Make an interactive UI"
- "Develop a frontend"
- "Build a visual interface"

## Detection

Look for these indicators to auto-activate:
- Request involves HTML/CSS/JS output
- UI component creation
- Responsive design requirements
- Interactive elements (forms, modals, animations)

## Process

### Step 1: Choose Tech Stack

| Stack | Use Case | Init Command |
|-------|----------|-------------|
| Next.js + Tailwind | Full-stack, SSR, production | `npx create-next-app@latest . --ts --tailwind --app` |
| Vite + React + Tailwind | SPA, fast dev | `npm create vite@latest . -- --template react-ts` |
| Astro + Tailwind | Content sites, static | `npm create astro@latest . -- --template basics` |
| SvelteKit + Tailwind | Lightweight, reactive | `npm create svelte@latest .` |
| Vanilla HTML/CSS/JS | Simple pages | Create `index.html`, `style.css`, `app.js` |

### Step 2: Scaffold Structure

```
project/
├── src/
│   ├── components/        # Reusable UI components
│   │   ├── ui/            # Base primitives (Button, Input, Card)
│   │   └── layout/        # Layout components (Header, Sidebar, Footer)
│   ├── pages/             # Page-level components / routes
│   ├── hooks/             # Custom React hooks
│   ├── utils/             # Utility functions
│   ├── styles/            # Global styles, CSS variables
│   └── types/             # TypeScript types
├── public/                # Static assets
├── STYLE_GUIDE.md         # (if create-style-guide was run)
└── package.json
```

### Step 3: Implement Core UI

```bash
# Analyze existing style guide (if exists)
cat STYLE_GUIDE.md 2>/dev/null && echo "📐 Using existing style guide"

# Check for component library usage
grep -rn 'import.*from.*@radix\|import.*shadcn\|import.*@mui' --include='*.{ts,tsx}' src/ 2>/dev/null

# Install common utilities
npm install clsx tailwind-merge class-variance-authority  # Class management
npm install lucide-react @radix-ui/react-icons            # Icons
npm install framer-motion                                 # Animations
```

**Base Component Template:**

```tsx
// src/components/ui/Button.tsx
import { cva, type VariantProps } from "class-variance-authority";

const button = cva(
  "inline-flex items-center justify-center rounded-lg font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-blue-600 text-white hover:bg-blue-700",
        secondary: "bg-gray-100 text-gray-900 hover:bg-gray-200",
        ghost: "hover:bg-gray-100",
        danger: "bg-red-600 text-white hover:bg-red-700",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);
```

### Step 4: Responsive Design

Apply responsive patterns using Tailwind breakpoints:

```tsx
// Mobile-first responsive layout
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4 lg:p-8">
  <Card />
  <Card />
  <Card />
</div>
```

| Breakpoint | Min Width | Target |
|-----------|-----------|--------|
| sm | 640px | Large phones |
| md | 768px | Tablets |
| lg | 1024px | Desktop |
| xl | 1280px | Wide |
| 2xl | 1536px | Ultra-wide |

### Step 5: Accessibility

```bash
# Check for accessibility issues
grep -rn '<button\|<a\|onClick' --include='*.{tsx,jsx}' src/ | grep -v 'aria-label\|role='

# Ensure all interactive elements have accessible names
# Check: buttons with only icons need aria-label
# Check: form inputs need associated labels
# Check: images need alt text
# Check: focus styles are visible (focus-visible:ring-2)
```

### Step 6: Performance

```bash
# Check bundle size
npx vite-bundle-visualizer 2>/dev/null || npx source-map-explorer dist/assets/*.js

# Check image optimization
grep -rn '<img' --include='*.{tsx,jsx}' src/ | grep -v 'loading="lazy"\|next/image\|gatsby-image'

# Check for render-blocking issues
grep -rn 'import.*\.css' --include='*.{tsx,jsx}' src/ | head -10

# Lazy load below-fold components
# Use: dynamic(() => import('./HeavyComponent'), { ssr: false })
```

### Step 7: Present Results

```
## 🌐 Web Application

### Tech Stack
- Framework: [framework + version]
- Styling: [Tailwind / CSS Modules / styled-components]
- State: [React Context / Zustand / Redux]
- Routing: [Next.js / React Router / none]

### Components Built
- [count] UI primitives
- [count] layout components
- [count] page components

### Accessibility
- ✅ Semantic HTML
- ✅ ARIA labels on icon buttons
- ✅ Focus visible styles
- ⚠️ [remaining issues]

### Performance
- Bundle size: [N] KB (gzip)
- Lighthouse score: estimated [score]
- Lazy loaded: [component list]

### Next Steps
1. [Suggested improvement]
2. [Suggested improvement]
```

## Cross-References

This skill is part of the Open Code system:
- **Orchestrator**: `skills/open-code/SKILL.md`
- **Style guide**: `skills/create-style-guide/SKILL.md` — consume design tokens
- **Code quality**: `skills/code-cleanup/SKILL.md` — run after scaffold
- **Documentation**: `skills/technical-documentation/SKILL.md` — document the built app

## Principles

- **Mobile-first**: Design for small screens first, then enhance for larger
- **Accessible by default**: Every component must work with keyboard + screen reader
- **Component isolation**: Each component owns its styling (no leaking)
- **Performance budget**: Bundle under 200KB (gzip) for initial load
- **Progressive enhancement**: Core functionality works without JS
