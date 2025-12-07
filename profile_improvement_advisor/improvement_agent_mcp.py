# profile_improvement_advisor/improvement_agent_mcp.py

from typing import List

from agents.mcp import MCPServerStdio


# ======================================
# MCP SERVER HELPERS (unchanged)
# ======================================

def researcher_mcp_stdio_servers(
    client_session_timeout_seconds: int = 300,
) -> List[MCPServerStdio]:
    servers: List[MCPServerStdio] = []

    # ✅ Fetch MCP (Python, robust)
    servers.append(
        MCPServerStdio(
            name="fetch_mcp",
            params={
                "command": "python",
                "args": ["-m", "mcp_server_fetch"],
            },
            client_session_timeout_seconds=client_session_timeout_seconds,
        )
    )

    # ✅ DuckDuckGo MCP (already working)
    servers.append(
        MCPServerStdio(
            name="ddg_mcp",
            params={
                "command": "ddg-search-mcp",
                "args": [],
            },
            client_session_timeout_seconds=client_session_timeout_seconds,
        )
    )

    return servers
