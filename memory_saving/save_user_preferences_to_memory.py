import json
from typing import Dict, Any
from pathlib import Path
from agents.mcp import MCPServerStdio
from memory_saving.memory_mcp_config import MCP_PARAMS, ensure_memory_dir


async def save_intake_answers_to_memory(
    intake_answers: Dict[str, Any],
    params: Dict[str, Any] | None = None,
):
    """
    Save or overwrite the user's intake answers in the LibSQL memory DB.

    This stores the entire intake dict as one JSON observation under a
    dedicated entity named 'job_intake'.
    """
    if params is None:
        params = MCP_PARAMS

    # Ensure memory directory exists
    ensure_memory_dir(params)

    # Connect to MCP memory server
    async with MCPServerStdio(params=params, client_session_timeout_seconds=30) as mcp_server:

        # Delete previous intake entity if present so this acts like an overwrite
        try:
            await mcp_server.call_tool("delete_entity", {"name": "job_intake"})
            print("[Memory] Deleted existing job_intake entity")
        except Exception as e:
            print(f"[Memory] No previous job_intake found or delete failed: {e}")

        entities_arg = {
            "entities": [
                {
                    "name": "job_intake",
                    "entityType": "job_intake",
                    "observations": [json.dumps(intake_answers, indent=2)],
                }
            ]
        }

        result = await mcp_server.call_tool("create_entities", entities_arg)

        print("[Memory] Saved intake answers to memory")

        # -----------------------------
        # Debug Snapshot
        # -----------------------------
        print("\n================= INTAKE SNAPSHOT =================\n")
        for key, value in intake_answers.items():
            print(f"{key}: {value}")
        print("\n===================================================\n")

        return result
