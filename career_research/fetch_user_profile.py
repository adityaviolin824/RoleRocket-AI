from __future__ import annotations

import sys  # ← ADD THIS
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from utils.logger import logging
from utils.exception import CustomException

logger = logging.getLogger(__name__)

def _get_latest_observation(
    conn: sqlite3.Connection,
    entity_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Return the latest observation.content for a given entity_name,
    parsed as JSON. If none exist or JSON is invalid, return None.
    """
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT content
            FROM observations
            WHERE entity_name = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (entity_name,),
        )
        row = cur.fetchone()
        if not row:
            logger.info("No observations found for entity_name=%s", entity_name)
            return None

        content = row[0]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error(
                "Invalid JSON in observation for entity_name=%s", entity_name
            )
            return None

    except Exception as e:
        logger.error(
            "Error querying latest observation for entity_name=%s", entity_name
        )
        raise CustomException(e, error_detail=sys)  # ← FIXED

def fetch_user_profile(
    db_path: str | Path,
    resume_entity: str = "resume_profile",
    intake_entity: str = "job_intake",
) -> Dict[str, Any]:
    """
    Load the latest resume profile and job intake from the memory DB
    and return a consolidated in memory profile dict.

    This only reads from the DB, it does not write anything back.
    """
    try:
        db_path = Path(db_path)

        if not db_path.exists():
            logger.error("Memory DB not found at %s", db_path)
            raise CustomException(
                f"Memory DB not found at {db_path}",
                error_detail=sys,  # ← FIXED
            )

        logger.info("Opening memory DB at %s", db_path)
        conn = sqlite3.connect(str(db_path))

        try:
            resume_profile = _get_latest_observation(conn, resume_entity) or {}
            job_intake = _get_latest_observation(conn, intake_entity) or {}

            profile: Dict[str, Any] = {
                "resume": resume_profile,
                "preferences": job_intake,
            }

            logger.info(
                "Fetched user profile from DB. "
                "resume_present=%s, preferences_present=%s",
                bool(resume_profile),
                bool(job_intake),
            )

            return profile

        finally:
            conn.close()
            logger.info("Closed memory DB connection")

    except CustomException:
        raise
    except Exception as e:
        logger.error("Error fetching user profile from memory DB")
        raise CustomException(e, error_detail=sys)  # ← FIXED

async def fetch_user_profile_async(
    db_path: str | Path,
    resume_entity: str = "resume_profile",
    intake_entity: str = "job_intake",
) -> Dict[str, Any]:
    """
    Async wrapper around fetch_user_profile.
    Currently calls the sync version directly.
    If needed you can offload to a thread pool later.
    """
    return fetch_user_profile(
        db_path=db_path,
        resume_entity=resume_entity,
        intake_entity=intake_entity,
    )
