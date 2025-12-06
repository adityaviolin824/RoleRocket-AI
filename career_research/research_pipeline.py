"""
Career research pipeline orchestration.

Sequential flow:
1) Load the full user profile from the LiteLLM memory database.
2) Minimize the profile into only the fields needed for job search APIs
   (role, location, remote preference, salary expectation).
3) Start all required MCP servers inside an AsyncExitStack:
   - fetch_mcp for fetching page content
   - ddg_mcp for DuckDuckGo based search
   - playwright_mcp for dynamic pages if needed
4) Create three junior job researchers using create_multi_source_career_research_agents:
   - JSearch API agent (Python tool)
   - Adzuna API agent (Python tool)
   - DuckDuckGo web search agent (MCP tools only)
5) Build a compact task that includes the minimized profile and instructs each
   junior to return a JobSearchOutput without explanations.
6) Run all three junior agents in parallel with Runner.run, wrapped in
   safe_run_junior so any failure becomes an empty JobSearchOutput instead of
   crashing the pipeline.
7) Create a senior researcher agent that does not call tools and only works on
   the JSON outputs from the three juniors.
8) Build a senior task that embeds the three JobSearchOutput objects as JSON
   and instructs the senior agent to merge, deduplicate and rank jobs into a
   JobAggregation object.
9) Run the senior agent and validate that the final_output is a JobAggregation.
10) Return a combined dictionary that includes:
    - original profile
    - senior best matches
    - full aggregation
    - per source jobs (jsearch, adzuna, ddg)
    - per source search criteria metadata.
"""

import sys
import json
import asyncio
from typing import Any, Dict
from contextlib import AsyncExitStack

from agents import Runner, trace
from agents.exceptions import MaxTurnsExceeded
from utils.logger import logging
from utils.exception import CustomException

from career_research.fetch_user_profile import fetch_user_profile_async
from career_research.career_researcher_agent import (
    create_multi_source_career_research_agents,
    create_senior_researcher_agent,
    JobSearchOutput,
    JobAggregation,
)
from career_research.research_mcp_and_tools import (
    researcher_mcp_stdio_servers,
)
from career_research.research_reports import write_debug_markdown  # <- new import

logger = logging.getLogger(__name__)



def minimize_profile(full_profile: dict) -> dict:
    """
    Reduce profile size for junior agents to avoid context issues.
    - Combines resume location string and intake preferred_locations list into a unique combined list.
    - Chooses up to 3 high-signal skills (frameworks/tools) for search, falling back to languages if needed.
    - For experience, prefers user_reported_years_experience from intake, then falls back to resume.years_experience.
    """
    prefs = full_profile.get("preferences") or {}
    resume = full_profile.get("resume") or {}

    # ----------------------
    # Locations
    # ----------------------
    resume_location = resume.get("location")
    preferred_locations = prefs.get("preferred_locations") or []

    combined_locations: list[str] = []
    if isinstance(resume_location, str) and resume_location.strip():
        combined_locations.append(resume_location.strip())

    for ploc in preferred_locations:
        if not isinstance(ploc, str):
            continue
        ploc_strip = ploc.strip()
        if ploc_strip and ploc_strip not in combined_locations:
            combined_locations.append(ploc_strip)

    # ----------------------
    # Skills: prefer frameworks/tools over bare languages
    # ----------------------
    raw_skills = resume.get("top_technical_skills") or []

    # Common “low-signal” languages for filtering
    low_signal_langs = {
        # Generic programming languages
        "python", "java", "c++", "c", "c#", "javascript", "js",
        "typescript", "go", "golang", "ruby", "php", "rust",
        "kotlin", "swift", "scala",

        # Generic soft skills (never useful for search)
        "communication", "leadership", "teamwork", "collaboration",
        "problem solving", "critical thinking", "creativity",

        # Generic non-tech resume filler
        "english", "hindi", "marathi", "bengali",
        "sales", "marketing", "management",
        "microsoft office", "excel", "powerpoint", "word",
    }

    high_signal: list[str] = []
    for s in raw_skills:
        if not isinstance(s, str):
            continue
        s_clean = s.strip()
        if not s_clean:
            continue
        if s_clean.lower() not in low_signal_langs:
            high_signal.append(s_clean)

    # If we found any high-signal ones, use those; otherwise fall back to the original list
    if high_signal:
        top_skills = high_signal[:3]
    else:
        top_skills = [s for s in raw_skills if isinstance(s, str) and s.strip()][:3]

    # ----------------------
    # Experience: prefer user-reported over resume estimate
    # ----------------------
    user_years = prefs.get("user_reported_years_experience")
    if user_years is not None:
        years_experience = float(user_years)
    else:
        resume_years = resume.get("years_experience")
        years_experience = float(resume_years) if resume_years is not None else 0.0

    return {
        "preferred_role": prefs.get("preferred_role"),
        "locations": combined_locations,          # plural list for agents to handle
        "remote_preference": prefs.get("remote_preference", "any"),
        "target_salary_lpa": prefs.get("target_salary_lpa"),
        "years_experience": years_experience,
        "top_skills": top_skills,
    }




async def safe_run_junior(agent, task: str) -> JobSearchOutput:
    """
    Run a junior agent with safeguards:
      - limit max_turns
      - catch MaxTurnsExceeded and other errors
      - always return a JobSearchOutput object
    """
    try:
        run_result = await Runner.run(agent, task, max_turns=12)

        final = getattr(run_result, "final_output", None)
        if isinstance(final, JobSearchOutput):
            return final

        logger.warning(
            "Junior agent returned unexpected output type (%s). "
            "Falling back to empty JobSearchOutput.",
            type(final),
        )
        return JobSearchOutput(jobs=[], search_criteria=None)

    except MaxTurnsExceeded:
        logger.warning(
            "Junior agent hit max turns. Returning empty JobSearchOutput."
        )
        return JobSearchOutput(jobs=[], search_criteria=None)

    except Exception as e:
        logger.error(
            "Junior agent crashed. Returning empty JobSearchOutput. Error: %s",
            e,
        )
        return JobSearchOutput(jobs=[], search_criteria=None)


async def run_career_research(
    memory_db_path: str,
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    """
    Main entrypoint for the job role research stage.
    """
    try:
        # 1. Load profile
        profile = await fetch_user_profile_async(memory_db_path)
        mini_profile = minimize_profile(profile)

        logger.info(
            "Loaded user profile for research. "
            "resume_present=%s, prefs_present=%s",
            bool(profile.get("resume")),
            bool(profile.get("preferences")),
        )

        # 2. Start MCP servers and create agents inside their context
        async with AsyncExitStack() as stack:
            mcp_servers = []
            for server in researcher_mcp_stdio_servers():
                entered = await stack.enter_async_context(server)
                mcp_servers.append(entered)

            # 2a. Create junior source specific agents
            jsearch_agent, adzuna_agent, ddg_agent = (
                await create_multi_source_career_research_agents(
                    model=model,
                    mcp_servers=mcp_servers,
                )
            )

            # 2b. Create senior aggregation agent
            senior_agent = await create_senior_researcher_agent(
                model=model,
                mcp_servers=mcp_servers,
            )

            # 3. Build task for juniors (use minimized profile)
            base_task = (
                "You receive a small JSON profile with these keys: "
                "preferred_role, locations, remote_preference, target_salary_lpa, years_experience, top_skills.\n"
                "Use this JSON only. Do not invent different roles, locations, or salary values.\n\n"
                "When you call your job search tool, you must:\n"
                "- Build the search query from preferred roles and similar roles.\n"
                "- Use the locations list to infer the city or region for search.\n"
                "- Infer the correct country from the locations list and pass it explicitly as the country argument.\n"
                "- Do not rely on the tool default country.\n\n"
                "Return a JobSearchOutput JSON only. No explanations or extra text.\n\n"
                "User profile JSON:\n"
                f"{json.dumps(mini_profile, ensure_ascii=False)}"
            )


            # 4. Run juniors in parallel with tracing and safety
            with trace("Junior_Researchers_Finding_Best_Roles"):
                jsearch_output, adzuna_output, ddg_output = await asyncio.gather(
                    safe_run_junior(jsearch_agent, base_task),
                    safe_run_junior(adzuna_agent, base_task),
                    safe_run_junior(ddg_agent, base_task),
                )

            # 5. Build task for senior agent
            senior_task = (
                "# CANDIDATE PROFILE\n"
                f"{json.dumps(mini_profile, indent=2)}\n\n"

                "# JOB SOURCES (JobSearchOutput JSON)\n"
                f"JSEARCH: {json.dumps(jsearch_output.model_dump())}\n\n"
                f"ADZUNA: {json.dumps(adzuna_output.model_dump())}\n\n"
                f"DDG: {json.dumps(ddg_output.model_dump())}\n\n"

                "# MATCHING RULES\n"
                "- For each job, fill matched_criteria (list) and a short reason based only on real evidence.\n"
                "- Use matched_criteria items from: 'role', 'skills', 'experience', 'location', 'salary'.\n\n"

                "role:\n"
                "- Add 'role' if the job title contains preferred_role keywords and seniority fits candidate experience.\n\n"

                "skills:\n"
                "- Add 'skills' if at least 2 skills from key_skills appear in required or implied skills.\n\n"

                "experience:\n"
                "- Add 'experience' if candidate experience >= job requirement or within 1 year.\n"
                "- If experience_required is null, infer: Senior=5+ yrs, Manager=3+ yrs, Junior=0 to 2 yrs, default=1 to 3 yrs.\n\n"

                "location:\n"
                "- Add 'location' if same city, region or country, or remote_type matches remote_preference.\n\n"

                "salary:\n"
                "- Add 'salary' only if salary meets or exceeds salary_expectation (if provided).\n\n"

                "# DEDUPLICATION RULES\n"
                "You must remove duplicates before ranking.\n"
                "- First build a combined list of all jobs from JSEARCH, ADZUNA and DDG.\n"
                "- For each job, create a deduplication key:\n"
                "  - If job_url is present and not empty, key = normalized job_url (ignore http vs https, ignore trailing slashes).\n"
                "  - Otherwise key = lowercased '<title> | <company> | <location_area or unknown>'.\n"
                "- Jobs that share the same deduplication key are considered duplicates.\n"
                "- For duplicates, keep only ONE job in the final result:\n"
                "  - Prefer the job that has a non empty job_url.\n"
                "  - If both have job_url, prefer the one with more non null fields (salary, skills, experience_required).\n"
                "  - If still equal, prefer source priority: jsearch > adzuna > ddg.\n"
                "- Do not allow the same deduplication key to appear more than once in best_matches.\n\n"

                "# AGGREGATION STEPS\n"
                "1) Merge jobs from all sources, apply the deduplication rules above\n"
                "2) Rank jobs: first by number of matched_criteria, then prefer jobs that include 'skills' in matched_criteria.\n"
                "3) For each unique job, set matched_criteria and a one line reason like "
                "\"Role strong; Skills 2/3; Experience 1 year short; Location ok\".\n"
                "4) Select the top 8 to 12 jobs for best_matches from the ranked unique list.\n"
                "5) Write search_summary as 2 to 3 factual sentences about how many strong, medium and weak or aspirational matches you found.\n\n"

                "Return a single JobAggregation JSON object only. "
                "Do not call tools. Do not invent missing values. Do not output prose outside JSON."
            )



            # 6. Run senior aggregation
            with trace("Senior_Researcher_Reviewing_Research"):
                senior_run = await Runner.run(
                    senior_agent,
                    senior_task,
                    max_turns=12,
                )

        senior_output = getattr(senior_run, "final_output", None)
        if not isinstance(senior_output, JobAggregation):
            raise CustomException(
                f"Senior agent returned unexpected output type: {type(senior_output)}",
                error_detail=sys,
            )

        # 7. Build combined result
        return {
            "profile": profile,
            "jobs": senior_output.best_matches,
            "aggregation": senior_output,
            "jsearch_jobs": jsearch_output.jobs,
            "adzuna_jobs": adzuna_output.jobs,
            "ddg_jobs": ddg_output.jobs,
            "search_criteria": {
                "jsearch": jsearch_output.search_criteria,
                "adzuna": adzuna_output.search_criteria,
                "ddg": ddg_output.search_criteria,
            },
        }

    except Exception as e:
        logger.exception("Error in career research pipeline")
        raise CustomException(e, error_detail=sys)

