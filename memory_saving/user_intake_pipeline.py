import sys
import asyncio
from pathlib import Path

from utils.logger import logging
from utils.exception import CustomException

from memory_saving.save_user_resume_to_memory import pipeline_process_resume_file
from memory_saving.save_user_preferences_to_memory import save_intake_answers_to_memory

logger = logging.getLogger(__name__)


async def process_resume_and_save(path: str | Path, model: str = "gpt-4.1-mini"):
    """Process a resume file and store structured output in memory."""
    try:
        resume_path = Path(path)

        if not resume_path.exists():
            logger.error("Resume not found: %s", resume_path)
            raise CustomException(
                f"Resume not found: {resume_path}",
                error_detail=sys
            )

        logger.info("Processing resume: %s", resume_path)

        await pipeline_process_resume_file(
            path=resume_path,
            save_to_memory=True,
            model=model,
        )

        logger.info("Resume processed and saved")

    except Exception as e:
        logger.error("Error processing resume")
        raise CustomException(e, error_detail=sys)


async def save_user_preferences(intake_answers: dict):
    """Store user intake preferences (location, role, etc) into memory."""
    try:
        if not intake_answers:
            logger.error("Empty intake answers")
            raise CustomException(
                "intake_answers cannot be empty",
                error_detail=sys
            )

        logger.info("Saving intake preferences")

        await save_intake_answers_to_memory(intake_answers)

        logger.info("Intake preferences saved")

    except Exception as e:
        logger.error("Error saving user intake data")
        raise CustomException(e, error_detail=sys)
