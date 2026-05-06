#!/bin/bash
# kitty_token_analytics.sh — token analytics via jq/awk (not LLM calls)
# Usage: bash scripts/kitty_token_analytics.sh

TOKEN_LOG="${1:-data/kitty_token_log.jsonl}"
OUTPUT="${2:-/dev/stdout}"

if [ ! -f "$TOKEN_LOG" ]; then
    echo "No token log found at $TOKEN_LOG" >&2
    exit 1
fi

echo "# Kitty Token Analytics" > "$OUTPUT"
echo "" >> "$OUTPUT"

# Top costs by model
echo "## By Model (total tokens, calls, avg, max)" >> "$OUTPUT"
jq -s 'group_by(.model) | map({
  model: .[0].model,
  total: (map(.tokens) | add),
  calls: length,
  avg: ((map(.tokens) | add) / length),
  max: (map(.tokens) | max)
}) | sort_by(-.total)' "$TOKEN_LOG" >> "$OUTPUT"

# Top 5 most expensive single calls
echo "" >> "$OUTPUT"
echo "## Top 5 Most Expensive Calls" >> "$OUTPUT"
jq -s 'sort_by(-.tokens) | .[0:5] | .[] | "\(.tokens) tokens | \(.model) | \(.purpose // "unknown")"' "$TOKEN_LOG" >> "$OUTPUT"

# Daily totals (last 7 days)
echo "" >> "$OUTPUT"
echo "## Daily Totals (last 7 days)" >> "$OUTPUT"
jq -s 'map(select(.timestamp != null)) | map({
  day: (.timestamp | split("T")[0],
  tokens: .tokens
}) | group_by(.day) | map({
  day: .[0].day,
  total: (map(.tokens) | add)
}) | sort_by(.day) | reverse | .[0:7])' "$TOKEN_LOG" >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "Report written to $OUTPUT"
