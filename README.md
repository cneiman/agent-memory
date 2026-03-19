# Moonshine 🌙

Time-aware memory system for Goober's long-term memory.

## Features

- **Temporal query parsing** — natural language time expressions in search queries
  - "what happened yesterday?" → filters to yesterday's date
  - "decisions last week" → Monday-to-Sunday range
  - "since March 10" → everything after March 10
  - "3 days ago" → that specific day
  - "between March 1 and March 15" → date range
- **Seamless integration** — temporal filters AND with existing FTS5 + semantic search
- **Zero false positives** — "the last item" won't trigger temporal parsing
- **CLI support** — `--since` and `--before` flags for explicit date filtering

## Architecture

The temporal parser lives at `core/temporal.py` and integrates into:
- `memory/mcp-server.py` — the MCP tool server (9 tools, temporal in `memory_search`)
- `memory/mem.py` — the CLI (`./mem search "query" --since "last week"`)

Source of truth: `~/goober-brain/memory/` (files here are symlinks).

## Usage

```bash
# Natural language (auto-detected)
./mem search "what did we discuss last Tuesday"
./mem search "decisions this week"

# Explicit flags
./mem search "deployment" --since "last week"
./mem search "errors" --since "2026-03-10" --before "2026-03-15"

# MCP tool (from any MCP client)
memory_search(query="changes since last Friday")
memory_search(query="meetings", after="2026-03-10")
```

## Tests

```bash
cd ~/goober-brain/memory
python3 test_temporal.py -v    # 43 tests
```
