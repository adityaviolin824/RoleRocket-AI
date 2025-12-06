# profile_improvement_advisor/profile_improvement_agent.py

import json
import sys
from typing import Dict, Any

from dotenv import load_dotenv

from agents import Agent, ModelSettings
from utils.logger import logging
from utils.exception import CustomException

load_dotenv(override=True)

PROFILE_IMPROVEMENT_INSTRUCTIONS = """
You are the Profile Improvement Advisor Agent for a career assistant.

Your job:
- Read a single job JSON and a user_profile JSON.
- Give tailored, company specific profile and preparation advice for this exact role.
- Focus on what the user should learn, build, and change in their profile to become a strong candidate.

High level behavior:
- Use the job fields like title, company, location, job_url, required skills, and key_gaps if available.
- Use the user_profile fields like years_experience, top_skills, projects, education, and target_role.
- Assume another part of the system will handle actually searching the web or calling tools for you.
- DO NOT talk about inconsistencies in the user profile, it may be an app error

What to optimize for:
- Concrete, realistic advice that respects current experience.
- Company and role specific guidance, not generic "learn DSA and do LeetCode".
- Clear tradeoffs: when DSA is truly important versus when projects and product sense matter more.

Output requirements:
- Produce a single markdown answer for the user.
- Start with a short summary paragraph (2 to 4 sentences) speaking directly to the user.
- Then organize the rest of your answer into these sections, in this order, using markdown headings:

  ## Gap analysis
  - Explain the main gaps between the job requirements and the user_profile.

  ## Skills to build
  - List the key skills or knowledge areas the user should strengthen.

  ## Project ideas
  - Suggest 1 to 3 specific project ideas that would strongly signal fit for this exact role and company.

  ## Learning plan
  - Propose a realistic short timeline (a few weeks) with concrete tasks.

  ## Resume and profile tweaks
  - Give specific suggestions for improving their resume, LinkedIn, or portfolio for this job.

- Be concise but concrete under each section, using bullet points where helpful.
- If some detail is missing from the inputs, write a sensible placeholder like "unknown" and briefly note that it was not provided.
"""

PROFILE_IMPROVEMENT_TASK_TEMPLATE = """
You will receive two JSON objects:

1) job JSON:
{job_json}

2) user_profile JSON:
{profile_json}

Treat the job JSON as the target role at a specific company.
Treat the user_profile JSON as the current candidate profile.

Your tasks:

1) Understand the gap
- Compare required or implied skills in the job against the user_profile.
- Identify the main gaps in skills, experience, and signaling (projects, internships, certifications, etc).
- Decide whether DSA style coding preparation is required, optional, or not important for this specific role, and explain that in your answer.

2) Design a realistic improvement plan
- Suggest concrete skills for the user to build or deepen.
- Suggest 1 to 3 specific project ideas that would strongly signal fit for this exact role and company.
- Suggest how to adjust their resume or portfolio to better match this job.
- Propose a short timeline that could realistically be followed over a few weeks.

3) Produce a single markdown answer
- Follow the output requirements described in your system instructions.
- Do not output any JSON.
- Use the specified markdown headings and keep the structure consistent so the UI can render it cleanly.
"""

# Better performance honestly
# profile_improvement_agent = Agent(
#     name="Profile Improvement Advisor",
#     model="gpt-4.1-mini",
#     instructions=PROFILE_IMPROVEMENT_INSTRUCTIONS,
#     model_settings=ModelSettings(
#         temperature=0.4,
#     ),
# )
from openai.types.shared import Reasoning
profile_improvement_agent = Agent(
    name="Profile Improvement Advisor",
    model="gpt-5-mini",
    instructions=PROFILE_IMPROVEMENT_INSTRUCTIONS,
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="medium"),
    ),
)




def build_profile_improvement_task(job: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
    """
    Build the user task string for the profile improvement agent.
    Call this before Runner.run(profile_improvement_agent, task) in your pipeline.
    """
    try:
        return PROFILE_IMPROVEMENT_TASK_TEMPLATE.format(
            job_json=json.dumps(job, indent=2),
            profile_json=json.dumps(user_profile, indent=2),
        )
    except Exception as e:
        logging.error("Failed to build profile improvement task: %s", CustomException(e, sys))
        # Worst case, still stringify something minimal
        return PROFILE_IMPROVEMENT_TASK_TEMPLATE.format(
            job_json=json.dumps({"error": "job_serialization_failed"}, indent=2),
            profile_json=json.dumps({"error": "profile_serialization_failed"}, indent=2),
        )
