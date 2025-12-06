# profile_improvement_advisor/profile_improvement_pipeline.py

import sys
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path

from dotenv import load_dotenv

from agents import Runner, trace
from utils.logger import logging
from utils.exception import CustomException

from profile_improvement_advisor.improvement_agent_mcp import (
    researcher_mcp_stdio_servers,
)
from profile_improvement_advisor.profile_improvement_agent import (
    profile_improvement_agent,
    build_profile_improvement_task,
)

from career_research.fetch_user_profile import fetch_user_profile_async

load_dotenv(override=True)

MEMORY_DB_PATH = "memory/userprofile.db"
USER_SELECTION_PATH = "input/user_selected_jobs.json"
PROFILE_IMPROVEMENT_MAX_TURNS = 2


# ---------------------------
# Helpers for safe cleanup
# ---------------------------
async def _safe_server_cleanup(server):
    """Best-effort cleanup for an MCP server; swallow CancelledError."""
    try:
        await server.cleanup()
        logging.info("Safe cleanup: server %s cleaned up", getattr(server, "name", "unknown"))
    except asyncio.CancelledError:
        logging.debug("Safe cleanup: server.cleanup() cancelled for %s", getattr(server, "name", "unknown"))
    except Exception as e:
        logging.debug("Safe cleanup: exception while cleaning server %s: %s", getattr(server, "name", "unknown"), e, exc_info=True)


async def _safe_runner_close(runner: Runner):
    """Best-effort runner close; swallow CancelledError."""
    try:
        await runner.aclose()
        logging.info("Safe cleanup: runner closed")
    except asyncio.CancelledError:
        logging.debug("Safe cleanup: runner.aclose() cancelled")
    except Exception as e:
        logging.debug("Safe cleanup: exception while closing runner: %s", e, exc_info=True)


# ---------------------------
# Core helpers
# ---------------------------
async def _load_user_profile_from_memory() -> Dict[str, Any]:
    """Load user profile from memory database."""
    try:
        memory_db_path = MEMORY_DB_PATH
        logging.info(
            "Attempting to fetch user profile from memory DB at %s",
            memory_db_path,
        )

        profile = await fetch_user_profile_async(memory_db_path)

        if not isinstance(profile, dict):
            logging.warning(
                "Fetched profile is not a dict (type=%s), using empty profile",
                type(profile),
            )
            return {}

        if "preferences" in profile and "intake" not in profile:
            profile["intake"] = profile.pop("preferences")

        return profile

    except Exception as e:
        logging.error(
            "Failed to fetch user profile from memory DB: %s",
            CustomException(e, sys),
        )
        return {}


def _load_user_selection() -> Dict[str, Any]:
    """
    Load user job selection from input/user_selected_jobs.json.

    Expected format:
    {
        "timestamp": "2025-12-05 20:06:02",
        "user_intent": "profile_improvement_guidance",
        "selected_count": 3,
        "selected_jobs": [...]
    }

    Returns empty dict if file not found or invalid.
    """
    try:
        selection_path = Path(USER_SELECTION_PATH)

        if not selection_path.exists():
            logging.warning(
                "User selection file not found at %s",
                USER_SELECTION_PATH,
            )
            return {}

        import json
        with open(selection_path, 'r', encoding='utf-8') as f:
            selection_data = json.load(f)

        logging.info(
            "Loaded user selection: %d jobs selected at %s",
            selection_data.get("selected_count", 0),
            selection_data.get("timestamp", "unknown time"),
        )

        return selection_data

    except Exception as e:
        logging.error(
            "Failed to load user selection from %s: %s",
            USER_SELECTION_PATH,
            CustomException(e, sys),
        )
        return {}


async def _run_advisor_for_job(
    job: Dict[str, Any],
    user_profile: Dict[str, Any],
    runner: Runner,
    active_mcp_servers: List[Any],
) -> Dict[str, Any]:
    """
    Run profile improvement advisor for a single job.

    Returns dict with:
        - job_title: str
        - company: str
        - summary_text: str (advisor output)
        - error: str (optional, if failed)
    """
    job_title = job.get("title", "Unknown")
    company = job.get("company", "Unknown")

    try:
        logging.info(
            "Running advisor for: %s at %s",
            job_title,
            company,
        )

        # Build task for this specific job
        task = build_profile_improvement_task(job, user_profile)

        # Run the agent
        with trace(f"Profile Improvement - {job_title}"):
            result = await runner.run(
                profile_improvement_agent,
                task,
                max_turns=PROFILE_IMPROVEMENT_MAX_TURNS,
            )

        raw_output = (getattr(result, "final_output", "") or "").strip()

        if not raw_output:
            logging.warning("Agent returned empty output for %s", job_title)
            return {
                "job_title": job_title,
                "company": company,
                "summary_text": "The advisor could not generate an improvement plan for this role.",
                "error": "empty_output",
            }

        logging.info("Successfully completed advisor for %s", job_title)
        return {
            "job_title": job_title,
            "company": company,
            "location": job.get("location_area", ""),
            "job_url": job.get("job_url", ""),
            "summary_text": raw_output,
        }

    except Exception as e:
        logging.error(
            "Failed to run advisor for %s: %s",
            job_title,
            CustomException(e, sys),
        )
        return {
            "job_title": job_title,
            "company": company,
            "summary_text": f"Error generating improvement plan: {str(e)}",
            "error": "execution_failed",
        }


async def run_profile_improvement_pipeline(
    runner: Optional[Runner] = None,
    mcp_client_session_timeout_seconds: int = 120,
    selection_data: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Loads user selection (unless provided via selection_data) and runs the Profile Improvement Advisor.

    If output_path is provided the pipeline will attempt to write a markdown report there
    (using a shielded threaded write so it completes even if cancellation occurs).
    The returned dict will include "output_path" when the file was written successfully.
    """
    #### print("#### PROFILE_IMPROVEMENT_PIPELINE: start") ####

    # Load user selection if not provided
    if selection_data is None:
        selection_data = _load_user_selection()

    if not selection_data:
        logging.error("No user selection data found")
        #### print("#### DEBUG: No selection_data found") ####
        return {
            "status": "failed",
            "error": "no_selection_data",
            "message": "Could not load user job selection from input/user_selected_jobs.json",
        }

    selected_jobs = selection_data.get("selected_jobs", [])
    if not selected_jobs:
        logging.warning("User selection contains no jobs")
        #### print("#### DEBUG: selection_data had zero jobs") ####
        return {
            "status": "failed",
            "error": "no_jobs_selected",
            "message": "User selection file contains no jobs",
        }

    # Load user profile
    user_profile = await _load_user_profile_from_memory()

    # Setup runner
    close_runner = False
    if runner is None:
        runner = Runner()
        close_runner = True

    original_tools = getattr(profile_improvement_agent, "tools", None)
    original_mcp_servers = getattr(profile_improvement_agent, "mcp_servers", None)
    active_mcp_servers: List[Any] = []

    try:
        logging.info(
            "Starting profile improvement pipeline for %d selected jobs",
            len(selected_jobs),
        )

        #### print(f"#### DEBUG: selected_jobs count = {len(selected_jobs)}") ####

        # Setup MCP servers (once for all jobs)
        try:
            servers = researcher_mcp_stdio_servers(
                client_session_timeout_seconds=mcp_client_session_timeout_seconds
            )

            for server in servers:
                try:
                    await server.connect()
                    active_mcp_servers.append(server)
                    logging.info(
                        "Connected MCP server %s",
                        getattr(server, "name", "unknown"),
                    )
                except asyncio.CancelledError:
                    logging.warning(
                        "Connection to MCP server %s was cancelled",
                        getattr(server, "name", "unknown"),
                    )
                    # do not re-raise here; allow outer flow to handle cancellation
                    return {
                        "status": "failed",
                        "error": "cancelled",
                        "message": "MCP server connection cancelled",
                    }
                except Exception as connect_exc:
                    logging.error(
                        "Failed to connect MCP server %s: %s",
                        getattr(server, "name", "unknown"),
                        CustomException(connect_exc, sys),
                    )

            if active_mcp_servers:
                profile_improvement_agent.mcp_servers = active_mcp_servers
                logging.info(
                    "Attached %d MCP servers to the agent",
                    len(active_mcp_servers),
                )
            else:
                logging.warning(
                    "No MCP servers active; running without MCP."
                )
        except Exception as e:
            logging.error("Failed to setup MCP servers: %s", CustomException(e, sys))

        # Process each job
        results: List[Dict[str, Any]] = []
        successful_count = 0

        for idx, job in enumerate(selected_jobs, 1):
            logging.info("Processing job %d/%d", idx, len(selected_jobs))

            result = await _run_advisor_for_job(
                job,
                user_profile,
                runner,
                active_mcp_servers,
            )

            results.append(result)

            if "error" not in result:
                successful_count += 1

        # Determine overall status
        if successful_count == len(selected_jobs):
            status = "success"
        elif successful_count > 0:
            status = "partial"
        else:
            status = "failed"

        logging.info(
            "Profile improvement pipeline completed: %d/%d successful",
            successful_count,
            len(selected_jobs),
        )

        result_dict: Dict[str, Any] = {
            "status": status,
            "timestamp": selection_data.get("timestamp", ""),
            "user_intent": selection_data.get("user_intent", ""),
            "total_jobs": len(selected_jobs),
            "successful": successful_count,
            "results": results,
        }

        # If caller requested writing markdown, build and write it here (safer)
        if output_path:
            try:
                outp = Path(output_path)
                outp.parent.mkdir(parents=True, exist_ok=True)

                #### print(f"#### DEBUG: Attempting to write markdown to {outp.resolve()}") ####

                # Build markdown from results
                markdown_output = f"# Profile Improvement Report\n\n"
                markdown_output += f"**Generated:** {result_dict.get('timestamp', '')}\n\n"
                markdown_output += f"**Jobs Analyzed:** {result_dict.get('total_jobs', 0)}\n\n"
                markdown_output += f"**Successful:** {result_dict.get('successful', 0)}\n\n"
                markdown_output += "---\n\n"
                for idx, job_result in enumerate(result_dict.get("results", []), 1):
                    markdown_output += f"## {idx}. {job_result.get('job_title', 'Unknown')}\n\n"
                    markdown_output += f"**Company:** {job_result.get('company', 'N/A')}\n\n"
                    markdown_output += f"**Location:** {job_result.get('location', 'N/A')}\n\n"
                    if job_result.get('job_url'):
                        markdown_output += f"**Link:** {job_result['job_url']}\n\n"
                    markdown_output += f"### Improvement Recommendations\n\n"
                    markdown_output += job_result.get('summary_text', 'No recommendations available')
                    markdown_output += "\n\n---\n\n"

                # Use asyncio.to_thread + shield to avoid cancellation killing the file write
                await asyncio.shield(asyncio.to_thread(outp.write_text, markdown_output, "utf-8"))
                logging.info("Wrote profile improvement markdown to %s", outp.resolve())
                #### print(f"#### DEBUG: WROTE file {outp.resolve()} size={outp.stat().st_size}") ####
                result_dict["output_path"] = str(outp.resolve())
            except Exception as e:
                logging.exception("Failed to write improvement markdown: %s", e)
                #### print(f"#### DEBUG: Exception while writing markdown: {e}") ####
                # attach note; don't fail the whole pipeline because of write error
                result_dict["write_error"] = str(e)

        #### print("#### PROFILE_IMPROVEMENT_PIPELINE: end (returning result)") ####
        return result_dict

    except asyncio.CancelledError as e:
        logging.warning("Profile improvement pipeline was cancelled: %s", e)
        #### print(f"#### DEBUG: pipeline cancelled: {e}") ####
        return {
            "status": "failed",
            "error": "cancelled",
            "message": "Pipeline was cancelled before completion.",
        }

    except Exception as e:
        logging.error("Profile improvement pipeline failed: %s", CustomException(e, sys))
        #### print(f"#### DEBUG: unexpected exception in pipeline: {e}") ####
        return {
            "status": "failed",
            "error": "pipeline_exception",
            "message": str(e),
        }

    finally:
        # Cleanup: restore agent state (non-blocking best-effort cleanup for external resources)
        try:
            if original_tools is not None:
                profile_improvement_agent.tools = original_tools
            else:
                if hasattr(profile_improvement_agent, "tools"):
                    delattr(profile_improvement_agent, "tools")
        except Exception:
            logging.debug("Failed to restore original agent tools", exc_info=True)

        try:
            if original_mcp_servers is not None:
                profile_improvement_agent.mcp_servers = original_mcp_servers
            elif hasattr(profile_improvement_agent, "mcp_servers"):
                delattr(profile_improvement_agent, "mcp_servers")
        except Exception:
            logging.debug("Failed to restore original mcp_servers", exc_info=True)

        # Schedule best-effort background cleanup for MCP servers (do not await here)
        for server in active_mcp_servers:
            try:
                asyncio.create_task(_safe_server_cleanup(server))
            except Exception as e:
                logging.debug("Failed to schedule safe cleanup for MCP server %s: %s", getattr(server, "name", "unknown"), e)

        # Schedule best-effort runner close if we created it (do not await here)
        if close_runner:
            try:
                asyncio.create_task(_safe_runner_close(runner))
            except Exception as e:
                logging.debug("Failed to schedule safe runner close: %s", e)
