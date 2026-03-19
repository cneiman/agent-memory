# Cursor Adapter

Connect moonshine to [Cursor](https://cursor.sh/) via MCP.

## Setup

1. Open Cursor Settings → MCP Servers

2. Add a new MCP server with these values:
   ```json
   {
     "moonshine": {
       "command": "python3",
       "args": ["/absolute/path/to/moonshine/core/mcp-server.py"],
       "env": {
         "MOONSHINE_DB": "/absolute/path/to/memories.db",
         "MOONSHINE_WORKSPACE": "/absolute/path/to/workspace/"
       }
     }
   }
   ```

   Or copy the config file:
   ```bash
   cp adapters/cursor/mcp-config.json ~/.cursor/mcp.json
   ```
   Then edit the paths.

3. Restart Cursor. The MCP server starts automatically when Cursor's agent needs it.

## Available Tools

Once connected, Cursor has access to 9 memory tools:

| Tool | Description |
|------|-------------|
| `memory_context` | Load relevant memories at session start |
| `memory_search` | Hybrid FTS5 + semantic + graph search |
| `memory_save` | Persist memories with auto-embedding |
| `memory_briefing` | Structured session briefing (no LLM cost) |
| `memory_surface` | Proactive memory surfacing via entity graph |
| `memory_entities` | List/query knowledge graph entities |
| `memory_connect` | Create typed edges between memories |
| `memory_neighbors` | Graph neighbor traversal |
| `memory_consolidate` | Find contradictions, merge duplicates |

## Requirements

- Python 3.8+
- `requests` library (`pip install requests`)
- [Ollama](https://ollama.ai/) running locally with `nomic-embed-text` for semantic search
  ```bash
  ollama pull nomic-embed-text
  ```

## Tips

- Cursor's agent mode will automatically discover MCP tools
- Keyword search (FTS5) works without Ollama — semantic search is optional
- Add memory instructions to your `.cursorrules` to guide when the agent saves/searches
