# present_to_user/job_compatibility_scoring.py
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple
from difflib import SequenceMatcher

from utils.logger import logging
from utils.exception import CustomException

# -----------------------------
# Config / weights
# -----------------------------
WEIGHTS = {
    "role": 0.30,
    "skills": 0.30,
    "experience": 0.20,
    "location": 0.10,
    "salary": 0.10,
}

# Tunables
MAX_SKILL_DENOM = 3  # denominator for skills ratio (cap)
MIN_SALARY_NEUTRAL_SCORE = 1.0  # score when no salary info (0..3 scale)
ROLE_SIMILARITY_FULL = 0.75  # ratio above which role considered a strong match


# -----------------------------
# Helpers
# -----------------------------
def _safe_lower_list(items: List[str]) -> List[str]:
    return [str(i).strip().lower() for i in (items or []) if str(i).strip()]


def _num_list_from_text(text: str) -> List[float]:
    """Extract numbers (ints or floats) from text; returns empty list if none."""
    if not text:
        return []
    found = re.findall(r"\b(\d+(?:\.\d+)?)\b", text)
    nums: List[float] = []
    for f in found:
        try:
            nums.append(float(f))
        except Exception:
            continue
    return nums


def _median_of_range(nums: List[float]) -> float:
    if not nums:
        return 0.0
    nums_sorted = sorted(nums)
    n = len(nums_sorted)
    mid = n // 2
    if n % 2 == 1:
        return nums_sorted[mid]
    return (nums_sorted[mid - 1] + nums_sorted[mid]) / 2.0


def _clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))


# -----------------------------
# Dimension scorers (0..3 float)
# -----------------------------
def score_role(preferred_role: str, title: str) -> Tuple[float, float]:
    """Return (score 0..3, similarity_ratio 0..1)."""
    try:
        if not preferred_role or not title:
            return 0.0, 0.0
        p = preferred_role.strip().lower()
        t = title.strip().lower()
        # fuzzy similarity using SequenceMatcher
        sim = SequenceMatcher(None, p, t).ratio()
        # Map similarity 0..1 to 0..3, but reward strong matches above ROLE_SIMILARITY_FULL
        score = _clamp(sim * 3.0, 0.0, 3.0)
        # If preferred role is direct substring, boost slightly
        if p in t or any(tok for tok in p.split() if tok and tok in t):
            score = max(score, 1.2)  # ensure at least some credit for substring matches
        return round(score, 3), round(sim, 3)
    except Exception:
        logging.exception("score_role failed")
        return 0.0, 0.0


def score_skills(user_skills: List[str], job_required: List[str], job_preferred: List[str]) -> Tuple[float, List[str]]:
    try:
        user_low = set(_safe_lower_list(user_skills))
        job_low = _safe_lower_list(job_required) + _safe_lower_list(job_preferred)
        job_low_unique = []
        for j in job_low:
            if j not in job_low_unique:
                job_low_unique.append(j)
        # compute exact and substring overlaps
        overlap = []
        for u in user_low:
            for j in job_low_unique:
                if u == j or u in j or j in u:
                    overlap.append(j)
                    break
        overlap = list(dict.fromkeys(overlap))  # preserve order, dedupe
        denom = max(1, min(MAX_SKILL_DENOM, len(job_low_unique)))  # avoid division by zero
        ratio = len(overlap) / denom
        score = _clamp(ratio * 3.0, 0.0, 3.0)
        return round(score, 3), overlap
    except Exception:
        logging.exception("score_skills failed")
        return 0.0, []


def score_experience(user_exp: float, job_exp_text: str) -> float:
    try:
        if user_exp is None:
            return 0.0
        nums = _num_list_from_text(job_exp_text)
        if not nums:
            # no explicit requirement: give a modest credit if user has some experience
            return 1.0 if user_exp >= 1.0 else 0.0
        # interpret requirement as the max or median of numbers (robust)
        required = max(nums)
        if required <= 0:
            return 0.0
        if user_exp >= required:
            return 3.0
        # proportional scale: fraction of requirement achieved, scaled to 0..3
        ratio = user_exp / required
        score = _clamp(ratio * 3.0, 0.0, 3.0)
        return round(score, 3)
    except Exception:
        logging.exception("score_experience failed")
        return 0.0


def score_location(user_loc: str, job_loc: str, remote_pref: str, remote_type: str) -> Tuple[float, str]:
    try:
        # remote compatibility
        remote_pref_l = (remote_pref or "").strip().lower()
        remote_type_l = (remote_type or "").strip().lower()

        if user_loc and job_loc:
            u = user_loc.strip().lower()
            j = job_loc.strip().lower()
            if u == j:
                return 3.0, "exact_city_match"
            # token overlap (city or country)
            u_tokens = set(re.split(r"[,\-\/\s]+", u))
            j_tokens = set(re.split(r"[,\-\/\s]+", j))
            if u_tokens & j_tokens:
                return 2.0, "token_overlap"
        # remote check
        if remote_pref_l and remote_type_l and remote_pref_l in remote_type_l:
            return 2.0, "remote_compatible"
        # if job is remote and user has flexible preference treat mildly positive
        if remote_type_l and ("remote" in remote_type_l) and (remote_pref_l in ("remote", "hybrid", "any")):
            return 1.5, "job_remote_user_flexible"
        return 0.0, "no_match"
    except Exception:
        logging.exception("score_location failed")
        return 0.0, "error"


def score_salary(exp_salary: float, min_sal: float, max_sal: float) -> Tuple[float, str]:
    try:
        # If user hasn't stated expectation, treat salary dimension as neutral (1)
        if exp_salary is None:
            return 1.0, "no_expectation"
        # No salary info from job: neutral score (not penalizing)
        if min_sal is None and max_sal is None:
            return MIN_SALARY_NEUTRAL_SCORE, "salary_unknown"
        # compute median job salary if both present, else take the present one
        try:
            if min_sal is not None and max_sal is not None:
                median = (float(min_sal) + float(max_sal)) / 2.0
            else:
                median = float(min_sal or max_sal)
        except Exception:
            logging.debug("salary conversion failed", exc_info=True)
            return 0.0, "salary_parse_error"
        # if job meets or exceeds expectation => full score
        if median >= exp_salary:
            return 3.0, "meets_expectation"
        # proportional mapping: ratio = median / exp_salary, scaled
        ratio = median / exp_salary if exp_salary > 0 else 0.0
        score = _clamp(ratio * 3.0, 0.0, 3.0)
        # human-friendly labels for reasoning
        if ratio >= 0.8:
            label = "near_expectation"
        elif ratio >= 0.5:
            label = "below_expectation"
        else:
            label = "far_below"
        return round(score, 3), label
    except Exception:
        logging.exception("score_salary failed")
        return 0.0, "error"


def label_fit(overall: float) -> str:
    # overall is 0..100
    if overall >= 70:
        return "strong"
    if overall >= 50:
        return "medium"
    if overall >= 30:
        return "weak"
    return "aspirational"


# -----------------------------
# Core scoring logic
# -----------------------------
def score_job(profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    try:
        preferred_role = profile.get("preferences", {}).get("preferred_role")
        user_loc = profile.get("resume", {}).get("location")
        remote_pref = profile.get("preferences", {}).get("working_style") or profile.get("preferences", {}).get("remote_preference")
        user_exp = profile.get("resume", {}).get("years_experience")
        user_skills = profile.get("resume", {}).get("top_technical_skills", [])
        exp_salary = profile.get("preferences", {}).get("salary_expectation") or profile.get("preferences", {}).get("target_salary_lpa")

        r, role_sim = score_role(preferred_role, job.get("title", ""))
        s, matched_skills = score_skills(user_skills, job.get("required_skills", []), job.get("preferred_skills", []))
        e = score_experience(user_exp, job.get("experience_required", "") or "")
        l, location_reason = score_location(user_loc, job.get("location_area", "") or "", remote_pref, job.get("remote_type", "") or "")
        sal, salary_reason = score_salary(exp_salary, job.get("salary_min"), job.get("salary_max"))

        # Weighted sum: each dim is 0..3, divide by 3 to normalize to 0..1, then *100
        weighted_sum = (
            r * WEIGHTS["role"] +
            s * WEIGHTS["skills"] +
            e * WEIGHTS["experience"] +
            l * WEIGHTS["location"] +
            sal * WEIGHTS["salary"]
        )
        overall = (weighted_sum / 3.0) * 100.0
        overall = round(_clamp(overall, 0.0, 100.0), 2)
        fit_level = label_fit(overall)

        # key_gaps: be conservative in reporting
        key_gaps = []
        if s < 1.5:
            key_gaps.append("skills_low")
        if e < 1.5:
            key_gaps.append("experience_low")
        if l < 1.0:
            key_gaps.append("location_mismatch")
        if sal < 1.0:
            key_gaps.append("salary_unknown_or_low")

        # confidence approx: average dimension (0..3) scaled to 0..1
        confidence = round((r + s + e + l + sal) / (3.0 * len(WEIGHTS)), 3)

        return {
            **job,
            "dimension_scores": {
                "role": round(r, 3),
                "role_similarity": round(role_sim, 3),
                "skills": round(s, 3),
                "matched_skills": matched_skills,
                "experience": round(e, 3),
                "location": round(l, 3),
                "location_reason": location_reason,
                "salary": round(sal, 3),
                "salary_reason": salary_reason,
            },
            "overall_score": overall,
            "fit_level": fit_level,
            "key_gaps": key_gaps,
            "confidence": confidence,
        }
    except Exception as e:
        logging.exception("Failed to score job: %s", job.get("job_url"))
        return {**job, "overall_score": 0.0, "fit_level": "aspirational", "key_gaps": ["scoring_error"], "confidence": 0.0}


def add_scores_to_aggregation(input_path: str, output_path: str) -> Dict[str, Any]:
    try:
        logging.info("Loading aggregation from %s", input_path)
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        profile = data.get("profile", {})
        aggregation = data.get("aggregation", {})

        best_matches = aggregation.get("best_matches", [])
        logging.info("Scoring %d best-matched jobs", len(best_matches))

        scored_best = []
        for job in best_matches:
            scored_best.append(score_job(profile, job))

        out = {
            "profile": profile,
            "aggregation": aggregation,
            "compatibility_scores": scored_best,
            "scored_best_matches": scored_best,
        }

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

        logging.info("Wrote compatibility scores to %s", output_path)
        return out

    except Exception as e:
        logging.exception("add_scores_to_aggregation failed")
        raise CustomException(e, sys)


# -----------------------------
# CLI entry (mock testing)
# -----------------------------
if __name__ == "__main__":
    DEFAULT_IN = os.path.join("outputs", "job_aggregation.json")
    DEFAULT_OUT = os.path.join("outputs", "compatibility_scores.json")

    try:
        logging.info("Starting job compatibility scoring")
        result = add_scores_to_aggregation(DEFAULT_IN, DEFAULT_OUT)
        logging.info("Scoring complete: %d jobs processed", len(result.get("compatibility_scores", [])))
    except CustomException as ce:
        logging.error("Fatal error in scoring: %s", str(ce))
        sys.exit(1)
    except Exception as e:
        logging.exception("Unexpected error")
        raise CustomException(e, sys)

