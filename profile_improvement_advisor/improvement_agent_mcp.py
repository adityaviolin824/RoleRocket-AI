# profile_improvement_advisor/improvement_agent_mcp.py

from typing import List

from agents.mcp import MCPServerStdio


# ======================================
# MCP SERVER HELPERS (unchanged)
# ======================================

def researcher_mcp_stdio_servers(
    client_session_timeout_seconds: int = 300,
) -> List[MCPServerStdio]:
    """
    Build stdio MCP servers for:
      - mcp-server-fetch (web content extraction)
      - DuckDuckGo search (backup job search)
    The caller is responsible for using them in an async context.
    """
    servers: List[MCPServerStdio] = []

    servers.append(
        MCPServerStdio(
            name="fetch_mcp",
            params={
                "command": "uvx",
                "args": ["mcp-server-fetch"],
            },
            client_session_timeout_seconds=client_session_timeout_seconds,
        )
    )

    servers.append(
        MCPServerStdio(
            name="ddg_mcp",
            params={
                "command": "npx",
                "args": ["-y", "@oevortex/ddg_search@latest"],
            },
            client_session_timeout_seconds=client_session_timeout_seconds,
        )
    )

    return servers
