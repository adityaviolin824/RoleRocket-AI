from __future__ import annotations

"""
Aditya's Epic Research Team

4 Researchers look for the best job matches according to the user's resume and preferences
(resume and data are fetched in the main pipeline).

Architecture:
- Three junior research agents (JSearch API, Adzuna API, DuckDuckGo web search)
- One senior researcher agent (merge, deduplicate, rank)
- Returns JobAggregation with source_breakdown, best_matches, search_summary
"""

import sys
from typing import List, Optional, Sequence, Dict, Tuple, Any

from pydantic import BaseModel, Field
from utils.logger import logging
from utils.exception import CustomException

from agents import Agent, AgentOutputSchema

from career_research.career_research_prompts_config import (
    JUNIOR_BASE_JOB_FETCH_INSTRUCTIONS,
    JUNIOR_JSEARCH_FALLBACK_RULES,
    JUNIOR_ADZUNA_FALLBACK_RULES,
    DDG_JOB_FETCH_INSTRUCTIONS,
    SENIOR_AGGREGATOR_INSTRUCTIONS,
)

logger = logging.getLogger(__name__)


# ======================================
# USER PROFILE MODELS (resume + intake)
# ======================================

class ResumeProfile(BaseModel):
    """
    Canonical profile built from the parsed resume and LLM experience estimate.
    Mirrors what we store in the 'resume_profile' memory entity.

    Experience here is an approximate total based on the resume only.
    The user's own self-reported experience from intake is preferred when available.
    """
    full_name: str = ""
    email: str = ""
    headline: str = ""
    location: str = ""

    # Approx total experience inferred from resume (LLM estimate)
    years_experience: float = 0.0

    # Optional: keep this if your parser still computes raw months; otherwise you can drop it.
    total_experience_months: int = 0

    top_technical_skills: List[str] = Field(default_factory=list)
    summary: str = ""


class JobIntake(BaseModel):
    """
    User-provided preferences collected during intake, stored under 'job_intake'.

    user_reported_years_experience is the user's own total experience estimate
    and is treated as the source of truth when present.
    """
    preferred_role: str = ""
    user_reported_years_experience: Optional[float] = None
    preferred_locations: List[str] = Field(default_factory=list)
    remote_preference: str = "any"  # valid: remote, hybrid, onsite, any
    target_salary_lpa: Optional[float] = None
    willing_to_relocate: Optional[bool] = None
    career_goals: str = ""


class JobSearchProfile(BaseModel):
    """
    Unified profile used by research and scoring agents.
    It merges the resume-based profile with intake preferences.
    """
    resume: ResumeProfile
    intake: JobIntake

    def effective_years_experience(self) -> float:
        """
        Prefer the user's self-reported total experience from intake,
        falling back to the resume-derived (LLM) estimate when missing.
        """
        if self.intake.user_reported_years_experience is not None:
            return float(self.intake.user_reported_years_experience)
        return float(self.resume.years_experience)


# ======================================
# STRUCTURED OUTPUT MODELS
# ======================================

class JobRole(BaseModel):
    title: str = Field(..., description="Job title for the role")
    company: Optional[str] = Field(None, description="Company name if available")
    location_area: Optional[str] = Field(None, description="City or region of the role if available")
    salary_min: Optional[float] = Field(None, description="Minimum numeric salary if available")
    salary_max: Optional[float] = Field(None, description="Maximum numeric salary if available")
    salary_currency: Optional[str] = Field(None, description="Currency code such as INR or USD")
    job_type: Optional[str] = Field(None, description="Job type such as full_time, part_time or contract")
    remote_type: Optional[str] = Field(None, description="Remote mode such as remote, onsite or hybrid")
    job_url: Optional[str] = Field(None, description="Direct job posting link if available")
    source: Optional[str] = Field(None, description="Source identifier such as jsearch, adzuna or ddg")

    required_skills: Optional[List[str]] = Field(
        None,
        description="Key required skills or technologies extracted from the job posting, if available.",
    )
    preferred_skills: Optional[List[str]] = Field(
        None,
        description="Preferred or nice-to-have skills from the job posting, if available.",
    )
    experience_required: Optional[str] = Field(
        None,
        description="Experience or seniority requirement from the posting, for example '2+ years', '5-7 years', 'senior'.",
    )

    matched_criteria: Optional[List[str]] = Field(
        None,
        description="List of matched user criteria such as ['role', 'skills', 'experience', 'location']",
    )
    additional_comments: Optional[str] = Field(
        None,
        description="Short notes about missing fields or partial matches. No long analysis.",
    )
    reason: Optional[str] = Field(
        None,
        description="Short structured note on why this job matches the user profile.",
    )

class SearchCriteria(BaseModel):
    query: Optional[str] = Field(None, description="Final job search query")
    country: Optional[str] = Field(None, description="Country code such as in, us or sg")
    filters_applied: Optional[List[str]] = Field(
        None,
        description="High level filters such as ['role', 'location', 'remote_preference']",
    )

class JobSearchOutput(BaseModel):
    jobs: List[JobRole] = Field(default_factory=list, description="Filtered job roles")
    search_criteria: Optional[SearchCriteria] = Field(None, description="Search metadata")

class JobAggregation(BaseModel):
    """Final aggregated output from all sources."""
    source_breakdown: Dict[str, int] = Field(
        ...,
        description="Jobs per source, for example {'jsearch': 3, 'adzuna': 4, 'ddg': 2}",
    )
    best_matches: List[JobRole] = Field(..., description="Top 8 to 12 ranked matches")
    search_summary: str = Field(..., description="Short summary of coverage and quality")

# ======================================
# MULTI-SOURCE JUNIOR AGENTS
# ======================================

async def create_multi_source_career_research_agents(
    model: str,
    mcp_servers: Sequence[object],
) -> Tuple[Agent, Agent, Agent]:
    """
    Create three junior agents:
      - jsearch_agent (uses JSearch tool)
      - adzuna_agent (uses Adzuna tool)
      - ddg_agent (uses MCP servers for web search and fetch)
    Returns (jsearch_agent, adzuna_agent, ddg_agent)
    """
    try:
        from career_research.research_mcp_and_tools import (
            search_jobs_jsearch,
            search_jobs_adzuna,
        )

        jsearch_agent = Agent(
            name="job_fetcher_jsearch",
            model=model,
            instructions=JUNIOR_BASE_JOB_FETCH_INSTRUCTIONS + JUNIOR_JSEARCH_FALLBACK_RULES,
            tools=[search_jobs_jsearch],
            mcp_servers=list(mcp_servers),
            output_type=JobSearchOutput,
        )

        adzuna_agent = Agent(
            name="job_fetcher_adzuna",
            model=model,
            instructions=JUNIOR_BASE_JOB_FETCH_INSTRUCTIONS + JUNIOR_ADZUNA_FALLBACK_RULES,
            tools=[search_jobs_adzuna],
            mcp_servers=list(mcp_servers),
            output_type=JobSearchOutput,
        )

        ddg_agent = Agent(
            name="job_fetcher_ddg",
            model=model,
            instructions=DDG_JOB_FETCH_INSTRUCTIONS,
            tools=[],
            mcp_servers=list(mcp_servers),
            output_type=JobSearchOutput,
        )

        return jsearch_agent, adzuna_agent, ddg_agent

    except Exception as e:
        logger.error("Error creating multi-source agents: %s", e)
        raise CustomException(e, error_detail=sys)

# ======================================
# SENIOR AGGREGATOR AGENT
# ======================================

async def create_senior_researcher_agent(
    model: str,
    mcp_servers: Sequence[object],
) -> Agent:
    """
    Senior aggregator that receives the junior outputs and produces a JobAggregation.
    The agent must not call any external tools.
    """
    try:
        return Agent(
            name="senior_job_analyst",
            model=model,
            instructions=SENIOR_AGGREGATOR_INSTRUCTIONS,
            mcp_servers=list(mcp_servers),
            output_type=AgentOutputSchema(
                JobAggregation,
                strict_json_schema=False,
            ),
        )

    except Exception as e:
        logger.error("Error creating senior researcher agent: %s", e)
        raise CustomException(e, error_detail=sys)
