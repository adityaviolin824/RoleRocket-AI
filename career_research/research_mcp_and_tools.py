from __future__ import annotations

import sys
import os
import requests
from typing import Any, Dict, List

from dotenv import load_dotenv
from utils.logger import logging
from utils.exception import CustomException

from agents import function_tool
from agents.mcp import MCPServerStdio

logger = logging.getLogger(__name__)

load_dotenv(override=True)

# ======================================
# API KEYS & CONFIG
# ======================================

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
JSEARCH_HOST = "jsearch.p.rapidapi.com"
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# ======================================
# JSEARCH PYTHON TOOL (Primary API - LIMITED)
# ======================================

@function_tool
def search_jobs_jsearch(
    query: str,
    country: str = "us",
    page: int = 1,
    num_pages: int = 1,           # Always 1 page max
    date_posted: str = "week",    # Recent jobs only
    remote_jobs_only: bool = False, # Fewer results
    max_results: int = 5,         # Post-process limit
) -> Dict[str, Any]:
    """
    JSearch API - LIMITED OUTPUT for agent context window safety.
    Defaults: 1 page, recent week, remote only, max 5 jobs.
    """
    try:
        if not RAPIDAPI_KEY:
            raise CustomException(
                "RAPIDAPI_KEY not configured, cannot call JSearch",
                error_detail=None,
            )

        url = f"https://{JSEARCH_HOST}/search"
        params = {
            "query": query,
            "country": country,
            "page": page,
            "num_pages": num_pages,
            "date_posted": date_posted,
            "remote_jobs_only": str(remote_jobs_only).lower(),
        }
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": JSEARCH_HOST,
        }

        logger.info(
            "Calling JSearch: '%s' (%s) page=%s num_pages=%s",
            query, country, page, num_pages,
        )

        resp = requests.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        if "data" in data and len(data["data"]) > max_results:
            original_count = len(data["data"])
            data["data"] = data["data"][:max_results]
            data["took"] = f"{len(data['data'])}/{original_count} results (limited to {max_results})"
            logger.info("JSearch truncated: %s → %s jobs", original_count, max_results)

        data["normalized_jobs"] = data.get("data", [])
        logger.info("JSearch normalized: %s jobs", len(data["normalized_jobs"]))

        logger.info("JSearch returned %s jobs (limited to %s)", len(data.get("data", [])), max_results)
        return data

    except CustomException:
        raise
    except Exception as e:
        logger.error("Error during JSearch call: %s", str(e))
        raise CustomException(e, error_detail=sys)

# ======================================
# ADZUNA PYTHON TOOL (FREE API - LIMITED)
# ======================================

@function_tool
def search_jobs_adzuna(
    query: str,
    country: str = "us",
    results_per_page: int = 5,   
    max_results: int = 5,        
) -> Dict[str, Any]:
    """
    Adzuna FREE API - LIMITED OUTPUT for agent context safety.
    Defaults: 5 results max. PH uses SG proxy.
    """
    try:
        if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
            raise CustomException(
                "ADZUNA_APP_ID or ADZUNA_APP_KEY not configured",
                error_detail=None,
            )
        # API Requires this stuff
        country_map = {
            "us": "us", "in": "in", "ph": "sg", "sg": "sg",
            "ca": "ca", "gb": "gb", "au": "au"
        }
        adzuna_country = country_map.get(country.lower(), "us")

        url = f"https://api.adzuna.com/v1/api/jobs/{adzuna_country}/search/1"
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "what": [query],  
            "results_per_page": min(results_per_page, max_results),
            "sort_by": "date",  # Recent jobs first (realtimr/week results)
        }

        logger.info(
            "Calling Adzuna: '%s' (%s → %s) results=%s",
            query, country, adzuna_country, results_per_page,
        )

        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # ADDED LIMITS coz tokens were sometimes exceeding limits due to repeated searches
        if "results" in data and len(data["results"]) > max_results:
            original_count = len(data["results"])
            data["results"] = data["results"][:max_results]
            data["count"] = min(data.get("count", 0), max_results)
            logger.info("Adzuna truncated: %s → %s jobs", original_count, max_results)
            
        data["normalized_jobs"] = data.get("results", [])
        logger.info("Adzuna normalized: %s jobs", len(data["normalized_jobs"]))
        logger.info("Adzuna returned %s jobs (limited to %s)", len(data.get("results", [])), max_results)
        return data

    except CustomException:
        raise
    except Exception as e:
        logger.error("Error during Adzuna call: %s", str(e))
        raise CustomException(e, error_detail=sys)




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



# def researcher_mcp_stdio_servers(
#     client_session_timeout_seconds: int = 300,
# ) -> List[MCPServerStdio]:
#     """
#     Build stdio MCP servers for:
#       - mcp-server-fetch (web content extraction)
#       - DuckDuckGo search
#     """
#     servers: List[MCPServerStdio] = []

#     # Fetch MCP
#     servers.append(
#         MCPServerStdio(
#             name="fetch_mcp",
#             params={
#                 "command": "mcp-server-fetch",
#                 "args": [],
#             },
#             client_session_timeout_seconds=client_session_timeout_seconds,
#         )
#     )

#     # DuckDuckGo MCP
#     servers.append(
#         MCPServerStdio(
#             name="ddg_mcp",
#             params={
#                 "command": "ddg-search-mcp",
#                 "args": [],
#             },
#             client_session_timeout_seconds=client_session_timeout_seconds,
#         )
#     )

#     return servers
