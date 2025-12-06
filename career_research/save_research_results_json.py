# career_research/save_research_results.py

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _pydantic_to_dict(obj: Any) -> Any:
    """
    Convert a Pydantic model to a plain dict.
    Supports both v1 (.dict) and v2 (.model_dump).
    If it is not a Pydantic model, return as is.
    """
    if obj is None:
        return None

    # Pydantic v2
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        return obj.model_dump()

    # Pydantic v1
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return obj.dict()

    return obj


def save_research_results(
    result: Dict[str, Any],
    outputs_dir: str = "outputs",
    json_name: str = "job_aggregation.json",
) -> Path:
    """
    Save only the senior researcher output and the user profile
    into a single JSON file that the presenter can consume later.

    Expected structure of `result` (from run_career_research):
        {
            "profile": <dict>,
            "aggregation": <JobAggregation>,
            ...
        }

    Only "profile" and "aggregation" are written.
    """
    if "aggregation" not in result:
        raise ValueError("research result is missing 'aggregation' key")

    outdir = Path(outputs_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    path = outdir / json_name

    profile = result.get("profile")
    aggregation_obj = result.get("aggregation")
    aggregation_dict = _pydantic_to_dict(aggregation_obj)

    payload = {
        "profile": profile,
        "aggregation": aggregation_dict,
    }

    path.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info("Saved senior aggregation JSON to %s", path)
    return path


def load_research_results(
    path: str = "outputs/job_aggregation.json",
) -> Dict[str, Any]:
    """
    Load the saved JSON that contains:
        {
            "profile": <dict>,
            "aggregation": <dict>,
        }

    This is what the presenter layer should read.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Aggregation file not found at {p}")

    content = json.loads(p.read_text(encoding="utf-8"))
    return content
