#!/bin/bash
# generate-context.sh — Build dynamic CONTEXT.md from moonshine data
#
# Generates the warm tier (CONTEXT.md) from SQLite memories, git activity,
# and daily session logs. Zero LLM cost — pure data assembly.
#
# Usage:
#   MOONSHINE_WORKSPACE=/path/to/workspace ./generate-context.sh
#
# Run on a timer (cron, LaunchAgent, systemd timer) for auto-refresh.
# Recommended: every 30 minutes during active hours.

set -euo pipefail

WORKSPACE="${MOONSHINE_WORKSPACE:-$(pwd)}"
CONTEXT_FILE="${WORKSPACE}/CONTEXT.md"
MEM_CLI="${MOONSHINE_MEM_CLI:-${WORKSPACE}/core/mem}"
TODAY=$(date +%Y-%m-%d)
WEEK_AGO=$(date -v-7d +%Y-%m-%d 2>/dev/null || date -d '7 days ago' +%Y-%m-%d)

{
echo "# CONTEXT.md — Dynamic Session Context"
echo "> Auto-generated $(date '+%Y-%m-%d %H:%M %Z'). Do not edit manually."
echo ""

# --- Recent Key Events (from SQLite) ---
echo "## 🗓️ Recent Events (Last 7 Days)"
if [ -x "$MEM_CLI" ]; then
  "$MEM_CLI" list --type event --since "$WEEK_AGO" --limit 15 2>/dev/null || echo "_No recent events_"
else
  echo "_mem CLI not available — run install.sh first_"
fi
echo ""

# --- Active Lessons (high importance) ---
echo "## 🧠 Active Lessons"
if [ -x "$MEM_CLI" ]; then
  "$MEM_CLI" list --type lesson --min-importance 4 --limit 10 2>/dev/null || echo "_No high-importance lessons_"
fi
echo ""

# --- Active Projects (from MEMORY.md if it exists) ---
echo "## 🚀 Active Projects"
MEMORY_FILE="${WORKSPACE}/MEMORY.md"
if [ -f "$MEMORY_FILE" ]; then
  sed -n '/^## Active Projects/,/^## [^#]/p' "$MEMORY_FILE" | sed '1d;$d' | head -30
else
  echo "_No MEMORY.md found_"
fi
echo ""

# --- Recent Git Activity ---
echo "## 🔀 Recent Git Activity"
if [ -d "${WORKSPACE}/.git" ]; then
  cd "$WORKSPACE"
  echo '```'
  git log --oneline --since="3 days ago" 2>/dev/null | head -10 || echo "No recent commits"
  echo '```'
else
  echo "_Not a git repository_"
fi
echo ""

# --- Today's Daily File (section headers only) ---
DAILY="${WORKSPACE}/memory/${TODAY}.md"
if [ -f "$DAILY" ]; then
  echo "## 📝 Today's Session Log"
  echo "Sections:"
  grep "^## " "$DAILY" | sed 's/^## /- /' || echo "- (empty)"
  echo ""
fi

# --- Pending Tasks ---
echo "## ✅ Pending Follow-ups"
if [ -x "$MEM_CLI" ]; then
  "$MEM_CLI" search "pending followup todo" --limit 5 2>/dev/null || echo "_No pending items_"
fi

} > "$CONTEXT_FILE"

echo "✅ CONTEXT.md generated ($(wc -c < "$CONTEXT_FILE" | tr -d ' ') chars)"
