# present_to_user/presenter_pipeline.py
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict

from utils.logger import logging
from utils.exception import CustomException

from present_to_user.job_compatibility_scoring import add_scores_to_aggregation
from present_to_user.job_presenter_agent import (
    presenter_agent,
    build_presenter_task,
    _fallback_template_presenter,
)
from agents import Runner

from pathlib import Path

from career_research.fetch_user_profile import fetch_user_profile_async
from utils.read_yaml import read_yaml

config = read_yaml(Path("config/master_config.yaml"))

INPUT_AGG_PATH = config.input_agg_path
SCORED_OUT_PATH = config.scored_out_path
PRESENTER_MD_PATH = config.presenter_md_path
MEMORY_DB_PATH = config.memory_path


async def run_presenter_pipeline(
    input_agg_path: str = INPUT_AGG_PATH,
    scored_out_path: str = SCORED_OUT_PATH,
    presenter_md_path: str = PRESENTER_MD_PATH,
    memory_db_path: str = MEMORY_DB_PATH,
) -> str:
    """
    Runs scoring + presenter agent + markdown save.
    Uses the provided paths (falls back to module-level defaults).
    Returns path to the final presenter markdown output.
    """
    # 1. Scoring
    try:
        logging.info("Starting scoring step")
        logging.info("Using input_agg_path=%s scored_out_path=%s", input_agg_path, scored_out_path)
        scored = add_scores_to_aggregation(input_agg_path, scored_out_path)
        logging.info(
            "Scoring step complete: %d scored jobs",
            len(scored.get("compatibility_scores", [])),
        )
    except Exception as e:
        logging.error("Scoring failed: %s", CustomException(e, sys))
        raise

    # 1.5 Fetch user profile from memory DB and attach to scored payload
    try:
        logging.info(
            "Attempting to fetch user profile from memory DB at %s",
            memory_db_path,
        )

        profile = await fetch_user_profile_async(memory_db_path)

        if not isinstance(profile, dict):
            logging.warning(
                "Fetched profile is not a dict (type=%s), skipping profile injection",
                type(profile),
            )
        else:
            # fetch_user_profile returns {"resume": ..., "preferences": ...}
            # Presenter prompt expects "resume" and "intake"
            if "preferences" in profile and "intake" not in profile:
                profile["intake"] = profile.pop("preferences")

            scored["profile"] = profile

            logging.info(
                "Attached fetched profile to scored payload. "
                "resume_present=%s, intake_present=%s",
                bool(profile.get("resume")),
                bool(profile.get("intake")),
            )

    except Exception as e:
        # Do not fail the whole pipeline if profile is missing or broken
        logging.warning(
            "Could not fetch user profile from memory DB, continuing without it: %s",
            CustomException(e, sys),
        )

    # 2. Presenter
    try:
        logging.info("Preparing presenter task")

        ##### DEBUG: FULL STRUCTURED PRESENTER INPUT START #####
        # logging.info(
        #     "PRESENTER STRUCTURED INPUT (scored payload):\n%s",
        #     json.dumps(scored, indent=2, ensure_ascii=False),
        # )
        ##### DEBUG: FULL STRUCTURED PRESENTER INPUT END #####

        task = build_presenter_task(scored)

        logging.info("Running presenter agent")
        result = await Runner.run(presenter_agent, task, max_turns=3)

        output_text = (
            getattr(result, "final_output", None)
            or getattr(result, "output_text", None)
            or str(result)
        )
        output_text = (output_text or "").strip()

        if not output_text or output_text.startswith(("{", "[")):
            logging.warning("Presenter response unusable, using fallback")
            output_text = _fallback_template_presenter(scored)

        # Save markdown
        os.makedirs(os.path.dirname(presenter_md_path) or ".", exist_ok=True)
        now = datetime.utcnow().isoformat(" ", "seconds") + " UTC"

        md_content = (
            f"# Job Matches — Presenter Output\n"
            f"*Generated: {now}*\n\n---\n\n"
            f"{output_text}\n"
        )

        with open(presenter_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logging.info("Presenter output saved at %s", presenter_md_path)
        # return an absolute resolved path
        try:
            return str(Path(presenter_md_path).resolve())
        except Exception:
            return presenter_md_path

    except Exception as e:
        logging.error("Presenter step failed: %s", CustomException(e, sys))
        raise
