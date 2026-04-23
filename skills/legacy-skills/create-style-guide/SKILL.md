---
name: create-style-guide
description: Generate a comprehensive STYLE_GUIDE.md for projects covering color palette, typography, spacing, component styles, and design tokens. Use when asked to create a style guide, design system, or UI standards document.
---

## Purpose

Generate a production-quality `STYLE_GUIDE.md` that documents the visual design system of a project. Covers colors, typography, spacing, components, animations, and Tailwind/CSS usage patterns.

## When to Activate

Invoke this skill when the user asks to:
- "Create a style guide"
- "Generate STYLE_GUIDE.md"
- "Document our design system"
- "Set up UI standards"
- "Define design tokens"
- "Create a component style reference"

## Detection

Look for these indicators to auto-activate:
- Project has `tailwind.config.js`, `theme.ts`, or CSS custom properties
- Project has component files with inline styles lacking documentation
- User mentions "consistent styling" or "design system"

## Process

### Step 1: Analyze the Project

```bash
# Detect CSS/design files
ls -la tailwind.config.* theme.* tokens.* style-dictionary.* 2>/dev/null
ls -la styles/ themes/ design-tokens/ 2>/dev/null

# Detect color usage patterns
grep -rn '#[0-9a-fA-F]\{6\}\|#[0-9a-fA-F]\{3\}' --include='*.{css,js,ts,jsx,tsx,vue,svelte}' . 2>/dev/null | head -40

# Detect font families
grep -rn 'font-family\|font:' --include='*.css' . 2>/dev/null | head -20

# Detect spacing values
grep -rn 'margin\|padding\|gap' --include='*.css' . 2>/dev/null | head -40

# Detect existing component library
grep -rn 'import.*from.*@radix\|import.*from.*@shadcn\|import.*from.*@mui\|import.*from.*chakra\|import.*from.*antd' --include='*.{js,ts,jsx,tsx}' . 2>/dev/null | head -10
```

### Step 2: Extract Design Tokens

```bash
# Extract all unique hex/rgb/hsl colors from source
grep -roh '#[0-9a-fA-F]\{6\}' --include='*.{css,js,ts,jsx,tsx,vue,svelte}' . 2>/dev/null | sort -u

# Extract CSS custom properties (design tokens)
grep -rn '--[a-z]' --include='*.css' . 2>/dev/null | grep -E '^\s+--'

# Extract Tailwind theme configuration
cat tailwind.config.* 2>/dev/null || echo "No tailwind config found"

# Extract viewport breakpoints
grep -rn '@media\|min-width\|max-width\|container' --include='*.css' . 2>/dev/null
```

### Step 3: Generate Style Guide

Write a `STYLE_GUIDE.md` with these sections:

| Section | Description |
|---------|-------------|
| Overview | Project name, design philosophy, target platforms |
| Color Palette | Primary, secondary, accent, neutral, semantic colors with hex values and usage rules |
| Typography | Font stack, scale/sizes, weights, line heights, usage per element |
| Spacing System | Base unit, spacing scale (4/8/12/16/24/32/48/64), when to use each |
| Component Styles | Buttons, inputs, cards, modals — variants, states, sizes |
| Shadows & Elevation | Box-shadow values for each elevation level |
| Animations & Transitions | Durations, easing curves, when to animate |
| Border Radius | Scale, when to use each value (sm/md/lg/full) |
| Opacity & Transparency | Disabled, overlay, backdrop values |
| Breakpoints | Screen sizes, responsive strategy |
| Tailwind Usage | Custom extensions, conventions, do/don't examples |

### Step 4: Generate Design Token File (Optional)

If the project uses Tailwind, generate or update token definitions:

```bash
# Create or update tailwind.config.* with documented tokens
# Extract design decisions from the STYLE_GUIDE.md and write config
```

### Step 5: Present Results

```
## 📋 Style Guide Created

### Files Generated
- `STYLE_GUIDE.md` — [N] sections, [M] tokens documented

### Design Tokens Extracted
- Colors: [count]
- Typography scale: [count] sizes
- Spacing values: [count]
- Components documented: [count]

### 🎨 Key Design Decisions
1. [Color palette rationale]
2. [Typography choice rationale]
3. [Spacing system rationale]

### 📐 Usage Rules
- [Do/don't conventions]
- [Component variant rules]
- [Responsive behavior]
```

## Cross-References

This skill is part of the Open Code system:
- **Orchestrator**: `skills/open-code/SKILL.md`
- **UI development**: `skills/visual-web-app-development/SKILL.md` — consumes this style guide
- **Documentation**: `skills/technical-documentation/SKILL.md` — can reference design decisions

## Principles

- **Extract, don't invent**: Derive design tokens from actual code, not assumptions
- **Be prescriptive**: Every token should have a usage rule (when to use, when not to)
- **Consistency > creativity**: Document the system that exists, even if imperfect
- **Component-driven**: Buttons, inputs, and modals are the highest-value documentation
- **Accessibility first**: Document contrast ratios and focus states
