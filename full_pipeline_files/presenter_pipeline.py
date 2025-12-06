import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from utils.logger import logging
from utils.exception import CustomException
from utils.read_yaml import read_yaml

from present_to_user.job_compatibility_scoring import add_scores_to_aggregation
from present_to_user.present_jobs_pipeline import run_presenter_pipeline

logger = logging.getLogger(__name__)

# load config
config = read_yaml(Path("config/master_config.yaml"))
INPUT_AGG_PATH = config.input_agg_path
SCORED_OUT_PATH = config.scored_out_path
PRESENTER_MD_PATH = config.presenter_md_path
MEMORY_DB_PATH = config.memory_path


async def run_presenter_only_pipeline(
    model: str = "gpt-4.1-mini",
    input_agg_path: str = INPUT_AGG_PATH,
    scored_out_path: str = SCORED_OUT_PATH,
    presenter_md_path: str = PRESENTER_MD_PATH,
    memory_db_path: str = MEMORY_DB_PATH,
) -> str:
    """
    Presenter pipeline (only):
      1) Score/Aggregation -> add_scores_to_aggregation(input_agg_path, scored_out_path)
      2) Run presenter to generate markdown (uses present_jobs_pipeline)
    Uses provided paths and falls back to module defaults.
    Returns the presenter markdown path produced by the presenter step.
    """
    logger.info("<<<< PRESENTER_PIPELINE_START >>>>")
    logger.info("INPUT_AGG_PATH: %s", input_agg_path)
    logger.info("SCORED_OUT_PATH: %s", scored_out_path)
    logger.info("PRESENTER_MD_PATH (target): %s", presenter_md_path)
    logger.info("MEMORY_DB_PATH (target): %s", memory_db_path)

    # 1) Scoring / compatibility scoring
    try:
        logger.info("<<<< [1/2] SCORING_START >>>>")
        scored = add_scores_to_aggregation(input_agg_path, scored_out_path)
        logger.info("SCORING_COMPLETE: %s", scored_out_path)
        logger.info("<<<< [1/2] SCORING_END >>>>")
    except Exception as e:
        logger.error("SCORING_FAILED: %s", CustomException(e, sys))
        logger.info("<<<< PRESENTER_PIPELINE_ABORTED >>>>")
        raise

    # 2) Run presenter (this function encapsulates building the prompt and running the presenter agent)
    try:
        logger.info("<<<< [2/2] PRESENTER_START >>>>")
        # pass the job-specific paths through to the presenter so it doesn't use global defaults
        presenter_md_path_ret = await run_presenter_pipeline(
            input_agg_path=input_agg_path,
            scored_out_path=scored_out_path,
            presenter_md_path=presenter_md_path,
            memory_db_path=memory_db_path,
        )
        logger.info("PRESENTER_MD_PATH: %s", presenter_md_path_ret)
        logger.info("<<<< [2/2] PRESENTER_END >>>>")
    except Exception as e:
        logger.error("PRESENTER_FAILED: %s", CustomException(e, sys))
        logger.info("<<<< PRESENTER_PIPELINE_ABORTED >>>>")
        raise

    logger.info("<<<< PRESENTER_PIPELINE_END >>>>")
    # normalize path if returned
    try:
        return str(Path(presenter_md_path_ret).resolve())
    except Exception:
        return str(presenter_md_path_ret)


# optional local test entrypoint
if __name__ == "__main__":
    try:
        logging.info("Running presenter pipeline locally")
        asyncio.run(run_presenter_only_pipeline())
    except Exception as e:
        logging.error("PRESENTER_PIPELINE_LOCAL_FAILED: %s", CustomException(e, sys))
