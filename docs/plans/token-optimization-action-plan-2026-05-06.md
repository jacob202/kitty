# Token Optimization Action Plan

Based on: `docs/optimizer/token-optimization-research-2026-05-06.md`

## Phase 1: High-Impact, Low-Effort (Today)

### 1.1 Prompt Caching Infrastructure
- **File**: `src/core/prompt_cache.py` (new)
- **Action**: Implement provider-native cache control for system prompts and tool schemas
- **Expected**: 50-90% savings on repeated calls
- **Time**: 1-2 hours

### 1.2 Semantic Response Caching
- **File**: `src/core/semantic_cache.py` (new)
- **Action**: Hash-based response cache (provider + model + prompt_hash) → SQLite
- **Expected**: 31% reduction, lower latency
- **Time**: 2-3 hours

### 1.3 Token-Aware Truncation
- **File**: `src/core/truncation.py` (new)
- **Action**: Add `limit` + `offset` params to tool outputs, hard limits on file reads (2K lines / 50KB)
- **Expected**: Prevent context overflow
- **Time**: 2 hours

### 1.4 Firecrawl Token Budgeting
- **File**: `scripts/kitty_builder.py` (modify)
- **Action**: Add `trimToTokenLimit()` for extractions, prefer `scrape()` over `crawl()` for single pages
- **Expected**: Up to 80% reduction
- **Time**: 1 hour

## Phase 2: Mini-Agent Tier (This Week)

### 2.1 Local Model Routing
- **File**: `src/core/model_router.py` (new)
- **Action**: Route simple queries (`--quick` flag, status checks, calculations) to smaller/cheaper model
- **Expected**: Instant cost reduction for lightweight tasks
- **Time**: 1-2 days

### 2.2 `--quick` Mode Implementation
- **Files**: `src/cli/`, `src/services/`
- **Action**: Add flag that bypasses cloud models for deterministic operations
- **Expected**: Reduced big-model calls
- **Time**: 1 day

## Phase 3: Medium-Term (Next Week)

### 3.1 TwoTrim Proxy Integration
- **Action**: Deploy as local proxy for dev environment
- **Expected**: 40-65% across general prompts
- **Time**: 2-3 days

### 3.2 Memory-Layered Architecture
- **Action**: Implement working + episodic + semantic (3-layer) memory (MemFlow-inspired)
- **Expected**: Reduced context bloat
- **Time**: 3-5 days

## Success Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| Token cost per session | Current | -50% |
| Cache hit ratio (semantic) | 0% | >40% |
| Context window utilization | Variable | <400K tokens |
| Mini-Agent routing | 0% | >30% of queries |

## Execution Order

1. ✅ Save research report (done)
2. 🔄 Create action plan (now)
3. ⏳ Implement prompt caching (next)
4. ⏳ Add semantic response cache
5. ⏳ Enable token-aware truncation
6. ⏳ Optimize Firecrawl usage
7. ⏳ Build mini-agent tier
