---
name: code-optimization
description: Analyze code for performance bottlenecks, security vulnerabilities, and potential issues. Use when asked to optimize, profile, or review code quality.
---

## Purpose

Systematically analyze code to find and fix performance issues, security vulnerabilities, and hidden problems before they reach production.

## When to Activate

Invoke this skill when the user asks you to:
- "Optimize this code"
- "Find performance issues"
- "Profile or benchmark"
- "Security review"
- "Check for vulnerabilities"
- Any code review focused on quality/performance

Also activated automatically as Stage 2 of the Open Code pipeline (`skills/open-code/SKILL.md`).

## Analysis Process

### Step 1: Determine Scope

- If the user specified files/directories → focus there
- If not → use `git status`, `git diff`, or inspect recent changes to determine scope
- Identify file types and applicable optimization strategies

### Step 2: Performance Analysis

Detect issues using language-specific grep patterns and tools.

**Algorithmic Efficiency**

```bash
# Detect O(n²) patterns — nested loops over same collection
# Improved: uses awk to find actual nesting (loop-inside-loop) not just files with two loops
for lang_pattern in '*.py' '*.js' '*.ts' '*.go' '*.rs'; do
  find . -name "$lang_pattern" -type f 2>/dev/null | while read -r f; do
    awk '
    /for |while / { depth++; if (depth > 1) { print FILENAME ":" NR ": nested loop: " $0; found=1 } }
    /^\}/ || /^end/ || /^    / && depth>0 { if (/^\}/) depth-- }
    END { if (!found) exit 1 }
    ' "$f" 2>/dev/null
  done
done

# Detect membership tests on lists (should be set)
grep -rn 'if.* in \[\]\|if.* in list\|if.* in \(\[\]\)' --include='*.py'
grep -rn '\.includes(\|\.indexOf(' --include='*.{js,ts}'  # O(n) on large arrays

# Detect redundant calculations inside loops
# Look for the same function call or attribute access being re-evaluated
```

**Memory & Resource Management**

```bash
# Detect unclosed resources in Python
grep -rn 'open(' --include='*.py' | grep -v 'with open\|\.close()'

# Detect missing cleanup (file handles, connections, listeners)
# Look for: open(), connect(), listen(), addEventListener() without close/disconnect/removeEventListener

# Detect unbounded collections growing without limit
# Look for: .append()/.push() in loops without size management
```

**I/O & Network**

```bash
# Detect N+1 query patterns in Python (Django/SQLAlchemy)
grep -rn 'for.* in.*\.all()' --include='*.py' -A5 | grep -E '\.(get|filter|all)\('

# Detect synchronous I/O in async functions
grep -rn 'async def' --include='*.py' -A20 | grep -E '^\s+(time\.sleep|requests\.|open\()'
grep -rn 'async function' --include='*.{js,ts}' -A20 | grep -E '^\s+(await\s+)?(readFileSync|writeFileSync)'
```

**Language-Specific Patterns**

| Language | Anti-Pattern | Pattern |
|----------|-------------|---------|
| Python | Repeated attribute lookup in hot loop | `grep -rn 'for.*:.*\.' --include='*.py'` |
| Python | Not using f-strings | `grep -rn "'\.format(\|\"\.format(" --include='*.py'` |
| React | Missing key prop in list | Check for `.map()` without `key=` prop |
| React | Unnecessary re-renders | Check for inline function/object props |
| Go | Defer in hot loop | `grep -rn 'for.*{.*defer' --include='*.go'` |
| Go | fmt.Sprintf over strings.Builder | In tight loops, strings.Builder is faster |
| General | Repeated constant computation in loop | Move loop-invariant expressions outside |
| General | Bundle size bloat | See bundle analysis below |

**Bundle Size Analysis**

```bash
# JavaScript/TypeScript — analyze bundle composition
npx source-map-explorer dist/main.js                    # Visualize bundle contents
npx webpack-bundle-analyzer dist/stats.json              # Webpack-specific
npx vite-bundle-visualizer                                # Vite-specific

# Check for duplicate dependencies
npx yarn-deduplicate --list                               # Yarn duplicates
npm ls --depth=0                                          # Top-level deps
npx madge --circular --extensions ts,js src/              # Circular imports
```

**Runtime Profiling**

```bash
# Python profiling
python -m cProfile -o profile.stats script.py && python -m pstats profile.stats
python -m memory_profiler script.py                       # Line-by-line memory

# Node.js profiling
node --cpu-prof --heap-prof --trace-gc script.js          # CPU + heap profile
node --prof-process --preprocess -j isolate*.log          # Process V8 logs

# Go profiling (add _ = "net/http/pprof" import)
go tool pprof -http=:8080 http://localhost:6060/debug/pprof/heap
go tool pprof -http=:8080 http://localhost:6060/debug/pprof/profile

# Rust profiling
cargo instruments --template alloc                        # Allocation tracking (macOS)
perf record --call-graph dwarf ./target/release/binary    # Linux perf
```

**Dependency Health**

```bash
# Check for deprecated/unmaintained packages
npm outdated                                              # Check for updates
npx npm-check-updates                                     # Interactive upgrade
npx depcheck                                              # Unused dependencies

# Python dependency analysis
pip list --outdated                                       # Outdated packages
pipdeptree --warn silence                                 # Dependency tree
safety check --full-report                                # Known vulnerabilities
```

---

**Frontend Performance**

Check for render-blocking resources, layout shifts, and runtime performance issues:

```bash
# Detect large inline styles/scripts in HTML
grep -rn '<style\|<script' --include='*.html' | grep -v 'src=\|href='

# Detect images without dimensions (causes layout shift / CLS)
grep -rn '<img' --include='*.{html,jsx,tsx}' | grep -v 'width\|height\|aspect-ratio'

# Detect missing lazy loading on below-fold images
grep -rn '<img' --include='*.{html,jsx,tsx}' | grep -v 'loading="lazy"'

# Detect excessive DOM size (10k+ nodes triggers painting issues)
find . -name '*.html' -type f -exec sh -c 'echo "$(grep -o "<" "$1" | wc -l) tags: $1"' _ {} \;

# Detect CSS in JS runtime injection (slower than static CSS)
grep -rn 'css={`\|styles={`\|styled\.\|css-in-js' --include='*.{js,ts,jsx,tsx}' | head -20
```

**Core Web Vitals checklist**:
| Metric | Target | Detection |
|--------|--------|-----------|
| LCP | ≤ 2.5s | Check largest image/text paint — lazy loading, preload hero images |
| FID/INP | ≤ 100ms / ≤ 200ms | Check for long tasks, heavy JS on interaction handlers |
| CLS | ≤ 0.1 | Check images without dimensions, dynamic content insertion, font swaps |
| TTFB | ≤ 800ms | Check server response time, CDN cache, redirect chains |

**CSS Performance**:
```bash
# Detect expensive selectors
grep -rn '\[.*=.*\]\s*{' --include='*.css' 2>/dev/null  # Attribute selectors are slow
grep -rn '::before\|::after\|::nth-child\|::nth-of-type' --include='*.css' 2>/dev/null

# Detect unused CSS rules (requires PurgeCSS or similar)
# npx purgecss --css build/static/*.css --content public/index.html src/**/*.jsx

# Detect !important usage (override chain)
grep -rn '!important' --include='*.css' | head -20
```

**Image Optimization**:
```bash
# Check for raster images that should be WebP/AVIF
find . -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -type f | head -10
# Check image sizes
find . -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -type f -exec sh -c 'echo "$(identify -format "%wx%h %f" "$1" 2>/dev/null || stat -f"%z" "$1"): $1"' _ {} \;
```

---

**Database Optimization**

Detect common database anti-patterns:

```bash
# N+1 queries in ORMs (Python)
grep -rn 'for.* in.*\.all()' --include='*.py' -A5 | grep -E '\.(get|filter|all|first)\('

# N+1 queries in JavaScript ORMs (Prisma, TypeORM, Sequelize)
grep -rn 'for.* of.*\.find\|for.* of.*\.findMany' --include='*.{js,ts}' -A5 | grep -E '\.(find|findMany|findFirst)\('

# Missing indexes (look for sequential scans)
grep -rn 'WHERE.*LIKE\|ORDER BY.*RAND\|WHERE.*NOT IN' --include='*.sql' 2>/dev/null

# Unpaginated queries (no LIMIT on large tables)
grep -rn 'SELECT.*FROM' --include='*.sql' | grep -v 'LIMIT\|TOP\|FETCH' | head -10

# Connection pool misconfiguration
grep -rn 'pool\|createPool\|create_engine\|connection_string' --include='*.{py,js,ts,go,rs,yaml,yml}' | head -10

# SELECT * in production queries (over-fetching)
grep -rn 'SELECT \*' --include='*.sql' 2>/dev/null
```

**General database rules**:
- Use indexes on columns used in WHERE, JOIN, ORDER BY
- Favor bulk operations over row-by-row processing
- Keep transactions short — don't include network I/O inside transactions
- Use connection pooling with reasonable max (typically 5-20 per app instance)
- Avoid SELECT N+1: eager-load related data with JOIN or batch loading

---

**Caching Strategy**

Check for missing or suboptimal caching:

```bash
# Detect missing HTTP caching headers (Node.js/Express)
grep -rn 'res\.send\|res\.json\|res\.render' --include='*.{js,ts}' | head -10

# Detect slow queries that should be cached
# Look for: complex database queries called frequently with same parameters

# Detect missing memoization on expensive function calls
# Look for: deterministic pure functions called multiple times with same args

# Check for in-memory cache without TTL or eviction policy
grep -rn 'new Map\|new WeakMap\|new LRU\|new NodeCache\|cache\.set\|@cached' --include='*.{py,js,ts,go,rs}' | head -10
```

**Caching layers to evaluate**:
| Layer | Tool/Pattern | Check |
|-------|-------------|-------|
| Browser/Client | `Cache-Control`, `ETag` headers | Are static assets cacheable? |
| CDN | CloudFront, Cloudflare, Fastly | Are API responses cacheable? |
| Application | Redis, Memcached, in-memory | Is hot data cached? |
| Database | Query cache, materialized views | Are expensive queries cached? |
| Build-time | Static generation, ISR | Are pages pre-built? |

**Service Worker check** (PWA):
```bash
# Detect if service worker is used for offline caching
find . -name 'service-worker*' -o -name 'sw.js' 2>/dev/null

# Check for cache-first strategy on static assets
# Look for: 'Cache-First', 'network-first', 'stale-while-revalidate' patterns
```

---

**API Design Optimization**

```bash
# Detect large responses being returned (no pagination)
grep -rn '\.find()\|\.all()\|\.findMany()\|SELECT.*FROM' --include='*.{py,js,ts,go,rs,sql}' | grep -v 'LIMIT\|skip\|take\|page\|offset' | head -10

# Detect serialization of excessive data
grep -rn 'return.*\.json\|Response\.json\|JSON\.stringify' --include='*.{py,js,ts,go}' | head -10

# Detect missing compression
# Check if Content-Encoding headers are set
grep -rn 'Content-Encoding\|compression\|gzip\|brotli' --include='*.{py,js,ts,go}' | head -5

# Detect chatty API patterns (multiple round-trips instead of batch)
# Look for: sequential API calls in a loop
grep -rn 'for.*fetch\|for.*axios\|for.*await.*fetch' --include='*.{js,ts}' | head -10
grep -rn 'for.*requests\|for.*session\.get' --include='*.py' | head -10

# Check rate limiting
grep -rn 'rate.limit\|rate_limit\|throttle\|429\|TOO_MANY' --include='*.{py,js,ts,go}' | head -5
```

**GraphQL-specific**:
```bash
# Detect over-fetching (selecting all fields when few needed)
# Look for: default field resolvers that load joins unnecessarily

# Detect N+1 in GraphQL resolvers (DataLoader needed)
grep -rn 'parent\.\|root\.\|\.load(' --include='*.{js,ts}' | grep -v 'dataloader\|DataLoader' | head -10
```

---

**Docker & Image Optimization**

```bash
# Detect large base images
grep -rn 'FROM' --include='Dockerfile*' | grep -v 'alpine\|slim\|scratch\|distroless'

# Detect missing multi-stage builds
grep -rn 'FROM.*AS' --include='Dockerfile*' | head -5
# If only one FROM, suggest multi-stage

# Detect apt-get without cleanup (layer bloat)
grep -rn 'apt-get install' --include='Dockerfile*' | grep -v 'rm -rf /var/lib/apt/lists'

# Detect COPY of entire directories when specific files would do
grep -rn 'COPY . ' --include='Dockerfile*' 2>/dev/null

# Missing .dockerignore
if [ ! -f .dockerignore ]; then
  echo "❌ No .dockerignore found — build context may include node_modules, .git, etc."
fi

# Unpinned base image versions (risks supply chain)
grep -rn 'FROM.*:latest\|FROM.*:stable\|FROM.*:[0-9]\+$' --include='Dockerfile*' 2>/dev/null
```

---

**WebSocket / SSE Optimization**

```bash
# Detect missing backpressure handling (message queue overflow)
grep -rn 'ws\.send\|websocket\.send\|socket\.emit' --include='*.{js,ts,py}' | head -10

# Detect reconnection logic (poor UX without it)
grep -rn 'WebSocket\|new WebSocket' --include='*.{js,ts}' | grep -v 'reconnect\|onclose\|onerror' | head -10

# Detect unbounded event listeners (memory leak)
grep -rn '\.on(\|\.addEventListener(' --include='*.{js,ts}' | grep -v '\.off(\|\.removeEventListener(' | head -10
```

---

**Performance Budgets**

When performance is critical, establish and check against budgets:

| Category | Good | Needs Improvement | Poor |
|----------|------|-------------------|------|
| Time to Interactive | < 3.5s | 3.5-5.8s | > 5.8s |
| First Contentful Paint | < 1.8s | 1.8-3.0s | > 3.0s |
| Largest Contentful Paint | < 2.5s | 2.5-4.0s | > 4.0s |
| JavaScript bundle size | < 200KB | 200-500KB | > 500KB |
| Total page weight | < 500KB | 500KB-2MB | > 2MB |
| Number of HTTP requests | < 25 | 25-50 | > 50 |

```bash
# Measure bundle size
if [ -d dist ] || [ -d build ]; then
  TARGET_DIR="dist"
  [ -d build ] && TARGET_DIR="build"
  echo "📦 Bundle sizes ($TARGET_DIR):"
  find "$TARGET_DIR" -name '*.js' -type f -exec sh -c 'echo "  $(wc -c < "$1") bytes - $1"' _ {} \; | sort -rn | head -10
fi

# Measure page weight (requires URL)
# curl -sI https://example.com | grep -i 'content-length\|content-encoding'
```

---

### Step 3: Security Analysis

Run automated scanners and grep for known patterns.

**SAST Scanners** (run if available):
| Language | Tool | Command |
|----------|------|---------|
| Python | bandit | `bandit -r [dir] -f json` |
| Python | safety | `safety check` (dependencies) |
| JavaScript/TypeScript | npm audit | `npm audit --json` |
| Go | gosec | `gosec ./...` |
| Rust | cargo-audit | `cargo audit` |
| General | semgrep | `semgrep --config=auto [dir]` |

**Manual Pattern Detection**:

```bash
# Hardcoded secrets
grep -rn 'password\s*=\|api_key\s*=\|secret\s*=\|token\s*=\|credential' --include='*.{py,js,ts,go,rs}' | grep -v 'os\.\|env\|\.env\|config'

# SQL injection
grep -rn 'execute(\|cursor\.execute(\|raw(' --include='*.py' | grep -v '\.pyc' | grep -E 'f"?\'?\|\.format(\|%\(|+'
grep -rn 'db\.query\|\.exec(' --include='*.{js,ts}' | grep -E 'f"\|+\|`.*\${'

# Command injection
grep -rn 'os\.system(\|subprocess\.call(\|subprocess\.Popen(\|exec(\|child_process' --include='*.{py,js,ts}' | grep -v '\["\|\[.'  # Static args only

# Path traversal
grep -rn 'open(\|read(\|write(' --include='*.{py,js,ts}' | grep -E 'user_input\|request\|req\.\|params\[' | grep -v 'basename\|normpath\|abspath'

# Unsafe deserialization
grep -rn 'pickle\.loads\|yaml\.load(\|eval(\|marshal\.load' --include='*.py'
grep -rn 'JSON\.parse\|eval(\|new Function(' --include='*.{js,ts}' | grep -v 'JSON\.parse(.*JSON\.stringify'
```

### Step 4: Hidden Issues

**Error Handling Gaps**

```bash
# Bare except in Python (catches everything)
grep -rn 'except:' --include='*.py'

# Empty except blocks (silent failures)
grep -rn 'except.*:\s*$\|except.*:\s*pass\s*$' --include='*.py'

# Missing error handling in Go
grep -rn 'if err != nil {' --include='*.go' | grep -E '^\s+return$\|^\s+log\.'
grep -rn '_, _ = \|\.\w+(\.\w+)*(' --include='*.go' | grep -v 'if err'

# Unhandled promise rejections
grep -rn '\.then(' --include='*.{js,ts}' | grep -v '\.catch(\|await '
```

**Edge Cases**

```bash
# Empty/null input handling
# Check functions that accept collections/strings — look for guards

# Race conditions
grep -rn 'async def\|async function' --include='*.{py,js,ts}' | grep -B5 'global\|nonlocal\|self\.\|shared'

# Boundary conditions
# Look for: loops with `<=`, off-by-one in range(), array[i+1], max values
grep -rn '<=\|i\+1\|i-1\||\w+|\s*\+\s*1' --include='*.{py,js,ts,go,rs}'
```

**Maintainability**

```bash
# Dead code / unused imports (from code-cleanup stage)
# Check for functions/classes defined but never called

# Code duplication
# Use: grep for identical multi-line blocks, or pdiff

# High cyclomatic complexity
# Count if/else/elif/for/while/and/or/case/match statements per function
```

### Step 5: Common Optimization Patterns (Before/After)

Apply these patterns when fixing performance issues found above.

**1. Nested Loop → Dictionary/Set Lookup** (O(n²) → O(n))

```python
# ❌ Before: O(n²) — nested loop searching
def find_duplicates(items):
    dupes = []
    for i, a in enumerate(items):
        for j, b in enumerate(items):
            if i != j and a == b and a not in dupes:
                dupes.append(a)
    return dupes

# ✅ After: O(n) — single pass with set
def find_duplicates(items):
    seen, dupes = set(), set()
    for item in items:
        if item in seen:
            dupes.add(item)
        seen.add(item)
    return list(dupes)
```

**2. Repeated Computation → Cache/Memoize**

```javascript
// ❌ Before: repeatCount called N times inside loop
function processUsers(users) {
  const results = [];
  for (const user of users) {
    const count = expensiveCount(user.department);  // Same dept → same result
    results.push({ user, count });
  }
  return results;
}

// ✅ After: memoize by department
function processUsers(users) {
  const cache = new Map();
  const results = [];
  for (const user of users) {
    if (!cache.has(user.department)) {
      cache.set(user.department, expensiveCount(user.department));
    }
    results.push({ user, count: cache.get(user.department) });
  }
  return results;
}
```

**3. N+1 Query → Batch/Eager Load**

```python
# ❌ Before: N+1 queries
def get_orders_with_items():
    orders = Order.objects.all()
    results = []
    for order in orders:
        items = OrderItem.objects.filter(order_id=order.id)  # N queries
        results.append({"order": order, "items": items})
    return results

# ✅ After: single batch query
def get_orders_with_items():
    orders = Order.objects.all()
    order_ids = [o.id for o in orders]
    items = OrderItem.objects.filter(order_id__in=order_ids)  # 1 query
    items_by_order = {}
    for item in items:
        items_by_order.setdefault(item.order_id, []).append(item)
    return [{"order": o, "items": items_by_order.get(o.id, [])} for o in orders]
```

**4. Synchronous I/O → Async/Concurrent**

```python
# ❌ Before: sequential HTTP calls
def fetch_all(urls):
    results = []
    for url in urls:
        results.append(requests.get(url).json())  # ~300ms each
    return results

# ✅ After: concurrent fetch
import asyncio
import aiohttp

async def fetch_one(session, url):
    async with session.get(url) as resp:
        return await resp.json()

async def fetch_all(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one(session, url) for url in urls]
        return await asyncio.gather(*tasks)
```

**5. Large Bundle → Code Splitting**

```javascript
// ❌ Before: monolithic import
import { Chart, Table, Map, Calendar, Form } from 'big-ui-lib';

// ✅ After: dynamic imports / tree-shakeable imports
import Chart from 'big-ui-lib/Chart';
import Table from 'big-ui-lib/Table';

// Route-level code splitting (React)
const Dashboard = React.lazy(() => import('./Dashboard'));
const Settings = React.lazy(() => import('./Settings'));
```

**6. Unbounded Array → Bounded/Streaming**

```python
# ❌ Before: loads all data into memory
def process_logs(filepath):
    with open(filepath) as f:
        lines = f.readlines()  # Entire file in memory
    return [process(line) for line in lines]

# ✅ After: streaming, constant memory
def process_logs(filepath):
    with open(filepath) as f:
        for line in f:  # Line by line
            yield process(line)
```

### Step 6: Present Results

Format findings as:

```
## 📋 Optimization Analysis

### Scope
- Files: [list]
- Languages: [detected]
- Lines analyzed: [count]

### ⚡ Performance
| Severity | Issue | Location | Fix |
|----------|-------|----------|-----|
| 🔴 | [Critical performance bug] | file:line | [fix] |
| 🟡 | [Optimization opportunity] | file:line | [fix] |
| 🟢 | [Minor improvement] | file:line | [recommendation] |

### 🔒 Security
| Severity | Issue | Location | Fix |
|----------|-------|----------|-----|
| 🚨 | [Critical vulnerability] | file:line | [fix] |
| 🛡️ | [Hardening opportunity] | file:line | [fix] |

### ⚠️ Edge Cases & Error Handling
- [Issue]: [Scenario] → [Fix]

### 🎯 Priority Recommendations
1. **[P0 - Must Fix]** [Why it matters]
2. **[P1 - Should Fix]** [Why it matters]
3. **[P2 - Nice to Have]** [Why it matters]
```

## Principles

- **Fix real bottlenecks**, not speculative optimizations
- **Security by design** — fix patterns, not symptoms
- **Proactive prevention** — catch problems before they ship
- **Measurable improvements** — focus on changes with tangible benefit
- Never sacrifice readability or correctness for performance
- **Evidence over intuition**: Back every recommendation with a concrete pattern match or benchmark

## Cross-References

This skill is part of the Open Code system:
- **Orchestrator**: `skills/open-code/SKILL.md` — runs this as Stage 2
- **Previous stage**: `skills/code-cleanup/SKILL.md` — cleans code before analysis
- **Next stage**: `skills/deployment-safety-review/SKILL.md` — reviews optimized code for deployment risk
- **TypeScript deep dive**: `skills/typescript-code-review/SKILL.md` — 300+ checkpoints for TS projects (Stage 2.5)
- **Execution tool**: `skills/ai-app-improvement-loop/SKILL.md` — uses this skill during Step 5 (Implement)

## Severity Taxonomy

When reporting findings, use this unified severity scale shared across all Open Code skills:

| Severity | Label | Action | Example |
|----------|-------|--------|---------|
| P0 - CRITICAL | 🚨 | Blocking — must fix | SQL injection, hardcoded secrets, O(n²) on hot path |
| P1 - MAJOR | 🔴 | Strongly recommended | Missing input validation, N+1 queries, unbounded memory |
| P2 - MINOR | 🟡 | Fix if in area | Unused imports, .format() over f-strings, missing docstrings |
| P3 - INFO | ⚪ | Note for later | Style inconsistencies, minor refactoring opportunities |
