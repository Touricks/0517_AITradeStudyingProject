# AITrading Ability MCP

STDIO MCP adapter for the sibling `AITrading` backend.

This server is a STDIO MCP profile extraction adapter for agents. Its default
purpose is to let an agent read the user profile that AITrading already
generated after the user completed frontend assessment/testing.

By default it does not expose questionnaire submission, quick assessment,
behavior training, review, or orchestration tools. It never exposes order
placement, buy/sell recommendations, price targets, or trading signals.

## Run

Start the AITrading backend separately:

```bash
cd ../AITrading
python3 -m backend.app
```

Start the MCP server over stdio:

```bash
cd ../AITradingMCP
PYTHONPATH=src python3 -m aitrading_ability_mcp.server
```

The stdio transport uses MCP JSON-RPC messages as newline-delimited JSON.

Example MCP client config:

```json
{
  "mcpServers": {
    "aitrading-ability": {
      "command": "/usr/bin/python3",
      "args": ["-m", "aitrading_ability_mcp.server"],
      "cwd": "/Users/carrick/Hackerson/AITradingMCP",
      "env": {
        "PYTHONPATH": "/Users/carrick/Hackerson/AITradingMCP/src",
        "AITRADING_BACKEND_URL": "http://127.0.0.1:8000",
        "AITRADING_MCP_ENABLE_WRITE_TOOLS": "false"
      }
    }
  }
}
```

Optional environment:

```bash
AITRADING_BACKEND_URL=http://127.0.0.1:8000
AITRADING_MCP_TIMEOUT=20
AITRADING_MCP_DEFAULT_USER_ID=
AITRADING_MCP_ENABLE_WRITE_TOOLS=false
AITRADING_MCP_DEBUG_LOG=
```

Agents can call the default profile tools without `user_id` in a local
single-user setup. User resolution order:

1. Explicit `user_id` argument, if provided by the agent.
2. `AITRADING_MCP_DEFAULT_USER_ID`, if configured.
3. The only user id found in backend memory.

If multiple users are found, the tool returns `profile_status:
"ambiguous_user"` with candidate ids so the agent can ask the user which profile
to use.

## Tools

Default read-only profile tools:

- `aitrading_health_check`
- `aitrading_extract_user_profile`
- `aitrading_list_user_profile_sources`
- `aitrading_get_user_profile_raw`
- `aitrading_search_user_profile_memories`

Set `AITRADING_MCP_ENABLE_WRITE_TOOLS=true` only for local development/admin
workflows. This additionally exposes:

- `aitrading_get_memory_snapshot`
- `aitrading_get_user_profile`
- `aitrading_search_user_memories`
- `aitrading_list_questionnaires`
- `aitrading_get_questionnaire`
- `aitrading_submit_questionnaire_assessment`
- `aitrading_run_quick_assessment`
- `aitrading_check_behavior_plan`
- `aitrading_review_trade_record`
- `aitrading_search_public_research`
- `aitrading_orchestrate_message`

Tools that submit assessment, training, review, or orchestration requests write
memory in the backend and are hidden by default. Read-only tools state that
explicitly in their descriptions and normalized outputs.

## Verify

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/stdio_smoke.py
```
