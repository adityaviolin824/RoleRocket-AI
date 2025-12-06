import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from utils.logger import logging
from utils.exception import CustomException
from utils.read_yaml import read_yaml

from career_research.research_pipeline import run_career_research

logger = logging.getLogger(__name__)

config = read_yaml(Path("config/master_config.yaml"))
MEMORY_DB_PATH = config.memory_path
JOB_AGGREGATION_PATH = config.researcher_job_aggregation


async def run_research_pipeline(
    model: str = "gpt-4.1-mini",
    memory_db_path: str = MEMORY_DB_PATH,
    job_agg_path: str = JOB_AGGREGATION_PATH,
) -> str:
    """
    Research pipeline (only):
      1) Run career research using memory (memory_db_path)
      2) Persist JobAggregation JSON to job_agg_path
    Returns the path to the saved JobAggregation JSON.
    """
    logger.info("<<<< RESEARCH_PIPELINE_START >>>>")
    logger.info("MEMORY_DB_PATH: %s", memory_db_path)

    try:
        logger.info("<<<< [1/2] CAREER_RESEARCH_START >>>>")
        research_result = await run_career_research(
            memory_db_path=memory_db_path,
            model=model,
        )
        logger.info("<<<< [1/2] CAREER_RESEARCH_END >>>>")
    except Exception as e:
        logger.error("CAREER_RESEARCH_FAILED: %s", CustomException(e, sys))
        logger.info("<<<< RESEARCH_PIPELINE_ABORTED >>>>")
        raise

    try:
        logger.info("<<<< [2/2] SAVE_JOB_AGGREGATION_JSON_START >>>>")
        profile = research_result.get("profile", {})
        aggregation = research_result.get("aggregation")

        agg_dict = aggregation.model_dump() if hasattr(aggregation, "model_dump") else aggregation
        payload = {"profile": profile, "aggregation": agg_dict}

        os.makedirs(os.path.dirname(job_agg_path) or ".", exist_ok=True)
        with open(job_agg_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info("JOB_AGGREGATION_SAVED: %s", job_agg_path)
        logger.info("<<<< [2/2] SAVE_JOB_AGGREGATION_JSON_END >>>>")
    except Exception as e:
        logger.error("SAVE_JOB_AGGREGATION_JSON_FAILED: %s", CustomException(e, sys))
        logger.info("<<<< RESEARCH_PIPELINE_ABORTED >>>>")
        raise

    logger.info("<<<< RESEARCH_PIPELINE_END >>>>")
    return str(Path(job_agg_path).resolve())
