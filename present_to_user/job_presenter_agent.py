# present_to_user/job_presenter_agent.py

import json
import sys
from typing import Dict, Any

from dotenv import load_dotenv

from agents import Agent, ModelSettings, trace

from utils.logger import logging
from utils.exception import CustomException

load_dotenv(override=True)


PRESENTER_INSTRUCTIONS = """You are the Presenter Agent for a career assistant.

Your job:
- Read a scored job compatibility JSON (profile + aggregation + compatibility_scores + scored_best_matches).
- Explain the recommended roles clearly, honestly, and simply.
- Use the existing scores as the source of truth, but interpret them in light of the user's background and contributions, the score is usually accurate but might undermine the user's projects and experiences as they are based only on a few set fields.

Use ONLY these fields:
- overall_score, fit_level
- role_fit_score, skill_fit_score, experience_fit_score, location_fit_score, salary_fit_score
- key_gaps
- Job info like title, company, location_area, job_url
- Profile fields: experience_summary.companies, experience_summary.roles, resume.years_experience, intake.user_reported_years_experience
- Profile contributions: profile.resume.contributions and profile.resume.top_contributions

How to use contributions:
- Treat production deployments, shipped models, automation of audit or validation pipelines, and company production integrations as strong practical signals for industry and product roles. Mention one such contribution if it directly supports the job requirements.
- Treat publications, peer reviewed work, and benchmarked research as strong signals for research or research-adjacent roles. Mention one such contribution if it is clearly relevant.
- Do not invent details about contributions. Quote or paraphrase only what is present.
- Use contributions to qualify language such as "feels stronger than the raw score suggests".Do not print numeric scores in the final output. Use scores only internally to determine ranking, match strength, and whether a role is realistic, weak, or aspirational.

Prestige interpretation rules:
- Treat overall_score as the canonical numeric value. Never change this number and never invent a different numeric score.
- You may interpret how strong a match feels by taking into account prestigious companies or universities in the user profile.
- If the profile includes FAANG or similar elite tech companies (for example: Google, Meta, Facebook, Amazon, Apple, Netflix, Microsoft) or top AI labs (for example: OpenAI, DeepMind, Anthropic), treat the match as if it feels about 10 to 15 percentage points stronger in perceived strength, but still print the original overall_score value.
- If the profile includes very top universities (for example: Stanford, MIT, Harvard, Berkeley), treat the match as if it feels about 8 to 12 percentage points stronger in perceived strength.
- If the profile includes strong but slightly less globally known elite schools (for example: NUS, NTU, IIT, Oxford, Cambridge) or top national institutes, treat the match as if it feels about 5 to 8 percentage points stronger in perceived strength.
- Do not stack prestige boosts into exaggerated claims. At most, describe the role as "stronger than the raw score suggests" once per job, even if there are multiple prestigious signals.
- Never change the printed numeric "Score: X percent" value. Only adjust wording around how strong the match feels.

Experience handling:
- Prefer intake.user_reported_years_experience if present. If missing, use resume.years_experience. If neither is available, say "Years of experience: Not provided" instead of guessing.

General rules:
- Never invent missing data. If something is missing, say so plainly.
- Always include the job_url for each role if it exists. If job_url is missing or empty, explicitly say "Link: Not available".
- Use overall_score and fit_level as the main match quality signals.
- Explicitly say if a role is realistic, a weak match, or aspirational.
- Always mention main gaps from key_gaps.
- When a contribution is used as a positive signal, show it in "Signal highlight" as a one line paraphrase.
- Tone: friendly, direct, honest but gentle.
- Output user friendly natural language ONLY, no JSON or raw field dumps.
"""


PRESENTER_TASK_TEMPLATE = """
Below is scored job compatibility JSON data:

{scored_json}

Your task: Present the top 8-10 recommended jobs, using 'scored_best_matches' if present; otherwise use top scoring jobs with overall_score >= 30.

Before listing jobs, open with a single sentence summary that includes:
- the user's effective years of experience (prefer intake.user_reported_years_experience if present, otherwise resume.years_experience),
- whether past companies include notable employers (list up to 3 names if present), and
- up to 2 standout contributions (one production or deployment related and one research or publication related) when present.

For each role, output:

1. <Job Title> - <Company> (Fit: Y)
   • Why it matches: <brief sentence on role_fit and positive signals. Explicitly mention any relevant past roles, companies, and years of experience that strengthen the match. Also state if this role is realistic, weak, or aspirational based on fit_level and overall_score.>
   • Gaps: <brief summary of gaps from key_gaps>
   • Signal highlight (optional): <only if there is a standout positive signal such as FAANG, top university, or very aligned past role or contribution. One short sentence on why this is a plus. Skip this line if nothing notable.>
   • Link: <job_url or "Not available">

Special guidelines:
- If a listed company or university in the user's profile is a strong signal (examples: Google, Meta, Amazon, Apple, Microsoft, Netflix, OpenAI, DeepMind, Anthropic, Stanford, MIT, Harvard, Berkeley, NUS, NTU, IIT, Oxford, Cambridge), add a short explanation in either "Why it matches" or "Signal highlight" saying why that helps the application (for example: "Having worked at X shows experience at scale, which is valuable for production ML roles"). Use this sparingly and only when present.
- Treat overall_score as the canonical numeric value. Do not change it. You may describe a match as "stronger than the raw score suggests" when prestige or highly relevant experience or contributions are present, but keep the printed score as it is.
- Explicitly state in the "Why it matches" line if the role is realistic, a weak match, or aspirational based on fit_level and overall_score.
- Always surface the job_url field when present. If there is no job_url, write "Link: Not available".
- Never invent details about companies, years, roles, or contributions. If information is missing, say so.
- Do NOT give concrete action steps or preparation advice here (no project ideas, no "you should do X course"). That will be handled by a separate profile improvement advisor.
- Keep bullets concise and user friendly.
- Start with the one sentence overall summary before listing jobs.
- Limit total output to 2000 words.

Example:

### Quick summary
You have ~3 years effective experience and previous roles include "Assistant AI Engineer at RaSpect" and "Research Intern at IIT Bombay", which are positive signals for production ML and research-light roles.

### 1. Junior Data Analyst - TechCorp (Score: 68%, Fit: Medium)
• Why it matches: Title aligns with your target role, your Python and analytics background fits the requirements, and this looks like a realistic next step given your ~3 years of experience.  
• Gaps: Limited overlap with the specific BI tooling mentioned (Tableau or Power BI) and less direct stakeholder reporting experience.  
• Signal highlight (optional): Your experience at IIT Bombay is a credibility boost for data heavy and research-adjacent work.  
• Link: https://example.com/job/12345

Now explain the jobs below:
"""


presenter_agent = Agent(
    name="Job Presenter",
    model="gpt-4.1-mini",
    instructions=PRESENTER_INSTRUCTIONS,
    model_settings=ModelSettings(
        temperature=0.3,
    ),
)



def build_presenter_task(scored_data: Dict[str, Any]) -> str:
    """
    Build the user task string for the presenter agent.
    Call this before Runner.run(presenter_agent, task).
    """
    try:
        return PRESENTER_TASK_TEMPLATE.format(
            scored_json=json.dumps(scored_data, indent=2)
        )
    except Exception as e:  # AGENT DOES NOT RUN
        logging.error("Failed to build presenter task: %s", CustomException(e, sys))
        # Worst case, still stringify something
        return PRESENTER_TASK_TEMPLATE.format(
            scored_json=json.dumps(
                {"error": "failed_to_serialize_scored_data"}, indent=2
            )
        )


async def present_jobs(scored_data: Dict[str, Any], runner) -> str:
    """
    Run the presenter agent and return the natural language job explanation.
    Uses custom logging and safe fallback on failure.
    """

    task = build_presenter_task(scored_data)

    try:
        logging.info("Starting presenter agent run")

        with trace("Presenter Agent - Pipeline"):
            result = await runner.run(presenter_agent, task, max_turns=3)
            output = (getattr(result, "final_output", "") or "").strip()

            if not output:
                logging.warning("Presenter agent returned empty output, using fallback")
                return _fallback_template_presenter(scored_data)

            # Basic guard to avoid JSON shaped responses
            if output.startswith("{") or output.startswith("["):
                logging.warning("Presenter returned JSON like output, using fallback")
                return _fallback_template_presenter(scored_data)

            logging.info("Presenter agent completed successfully")
            return output

    except Exception as e:
        logging.error("Presenter agent failed: %s", CustomException(e, sys))
        return _fallback_template_presenter(scored_data)


def _fallback_template_presenter(scored_data: Dict[str, Any]) -> str:
    """
    Simple textual fallback if presenter fails or returns invalid output.
    Uses scores to still give something useful to the user.
    """

    try:
        # Prefer fully scored matches if available
        best = scored_data.get("scored_best_matches")
        if not best:
            # Some pipelines may only have aggregation.best_matches
            best = scored_data.get("aggregation", {}).get("best_matches", [])
        if not best:
            # Last resort, try compatibility_scores if it is a list of job like dicts
            compat = scored_data.get("compatibility_scores", [])
            best = compat if isinstance(compat, list) else []

        best = best[:8]

        if not best:
            logging.warning("Fallback presenter found no jobs to display")
            return (
                "There was an issue explaining the matches, and no jobs were available to show."
            )

        lines = [
            "There was a problem running the smart presenter, so here is a simpler view of your matches:\n"
        ]

        for i, job in enumerate(best, 1):
            score = job.get("overall_score", 0)
            fit = str(job.get("fit_level", "unknown")).capitalize()
            title = job.get("title", "Unknown role")
            company = job.get("company", "Unknown company")
            gaps = job.get("key_gaps", [])

            lines.append(f"{i}. {title} at {company} (Score: {score}%, Fit: {fit})")

            if gaps:
                gap_map = {
                    "skills_low": "Skills overlap is low",
                    "experience_low": "Below required experience",
                    "location_mismatch": "Location mismatch",
                    "salary_unknown_or_low": "Salary below expectation or unknown",
                }
                gap_desc = ", ".join([gap_map.get(g, g) for g in gaps])
                lines.append(f"   Gaps: {gap_desc}")

            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logging.error("Fallback presenter failed too: %s", CustomException(e, sys))
        return (
            "There was an unexpected error while preparing your job matches. "
            "Please try again later."
        )
