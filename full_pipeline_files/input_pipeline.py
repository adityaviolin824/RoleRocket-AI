# pipeline/intake_pipeline.py

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from utils.logger import logging
from utils.exception import CustomException
from utils.read_yaml import read_yaml

# Intake stage functions
from memory_saving.user_intake_pipeline import (
    process_resume_and_save,
    save_user_preferences,
)

logger = logging.getLogger(__name__)

# load config
config = read_yaml(Path("config/master_config.yaml"))
MEMORY_DB_PATH = config.memory_path



async def run_intake_pipeline(
    resume_path: str | Path,
    intake_answers: Dict[str, Any],
    model: str = "gpt-4.1-mini",
    memory_db_path: str = MEMORY_DB_PATH,
) -> str:
    """
    Intake pipeline:
      1) Parse resume and save parsed profile to memory
      2) Save user preferences (intake_answers) to memory
    Returns the memory DB path used.
    """
    resume_path = Path(resume_path)
    logger.info("<<<< INTAKE_PIPELINE_START >>>>")
    logger.info("RESUME_PATH: %s", resume_path)
    logger.info("MEMORY_DB_PATH: %s", memory_db_path)

    # 1) Resume intake
    try:
        logger.info("<<<< [1/2] USER_INTAKE_RESUME_START >>>>")
        await process_resume_and_save(path=resume_path, model=model)
        logger.info("<<<< [1/2] USER_INTAKE_RESUME_END >>>>")
    except Exception as e:
        logger.error("USER_INTAKE_RESUME_FAILED: %s", CustomException(e, sys))
        logger.info("<<<< INTAKE_PIPELINE_ABORTED >>>>")
        raise

    # 2) Preferences intake
    try:
        logger.info("<<<< [2/2] USER_INTAKE_PREFERENCES_START >>>>")
        await save_user_preferences(intake_answers=intake_answers)
        logger.info("<<<< [2/2] USER_INTAKE_PREFERENCES_END >>>>")
    except Exception as e:
        logger.error("USER_INTAKE_PREFERENCES_FAILED: %s", CustomException(e, sys))
        logger.info("<<<< INTAKE_PIPELINE_ABORTED >>>>")
        raise

    logger.info("<<<< INTAKE_PIPELINE_END >>>>")
    return memory_db_path






# local test entrypoint (TESTING -> REMOVE LATER)
if __name__ == "__main__":
    sample_resume = Path("00-sample_data_for_pipe/Aditya_Bhattacharyya_CV_28Nov.pdf")
    sample_prefs = {
        "preferred_role": "AI Engineer",
        "user_reported_years_experience": 1.0,
        "preferred_locations": ["Mumbai", "Bangalore"],
        "remote_preference": "hybrid",
        "target_salary_lpa": 20,
        "willing_to_relocate": False,
        "career_goals": "financial independence",
    }
    try:
        logging.info("Running intake pipeline locally")
        asyncio.run(run_intake_pipeline(sample_resume, sample_prefs))
    except Exception as e:
        logging.error("INTAKE_PIPELINE_LOCAL_FAILED: %s", CustomException(e, sys))
