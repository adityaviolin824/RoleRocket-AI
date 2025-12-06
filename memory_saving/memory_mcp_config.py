# memory_saving/memory_mcp_config.py

from pathlib import Path
from typing import Dict, Any

# Single source of truth for the memory MCP config
MCP_PARAMS: Dict[str, Any] = {
    "command": "npx",
    "args": ["-y", "mcp-memory-libsql"],
    "env": {"LIBSQL_URL": "file:./memory/userprofile.db"},
}


def ensure_memory_dir(params: Dict[str, Any] | None = None) -> Path:
    """
    Make sure the directory that holds the LibSQL file exists.

    Returns the directory path.
    """
    if params is None:
        params = MCP_PARAMS

    db_path = Path(params["env"]["LIBSQL_URL"].replace("file:", ""))
    memory_dir = db_path.parent

    if not memory_dir.exists():
        memory_dir.mkdir(parents=True, exist_ok=True)
        print(f"[MCP] Created memory directory at: {memory_dir}")
    else:
        print(f"[MCP] Memory directory exists: {memory_dir}")

    return memory_dir
