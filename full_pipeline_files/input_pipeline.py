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

from memory_saving.user_intake_pipeline import (
    process_resume_and_save,
    save_user_preferences,
)

logger = logging.getLogger(__name__)

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

    try:
        logger.info("<<<< [1/2] USER_INTAKE_RESUME_START >>>>")
        await process_resume_and_save(path=resume_path, model=model)
        logger.info("<<<< [1/2] USER_INTAKE_RESUME_END >>>>")
    except Exception as e:
        logger.error("USER_INTAKE_RESUME_FAILED: %s", CustomException(e, sys))
        logger.info("<<<< INTAKE_PIPELINE_ABORTED >>>>")
        raise

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

