"""
Utilities for generating debug reports for the Career Research pipeline.
Outputs clean markdown summarizing the entire job aggregation result.
"""

import json
import datetime
from pathlib import Path
from typing import Dict, Any


def write_debug_markdown(
    result: Dict[str, Any],
    output_path: str = "outputs/researched_jobs.md"
):
    """
    Write a clean markdown report showing:
    - pipeline metrics
    - best matches
    - full aggregated job list
    - search summary
    - search criteria
    - extracted user profile

    Parameters:
        result (dict): The full pipeline output dictionary returned by run_career_research().
        output_path (str): Where the markdown file should be written.
    """

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    lines = []
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Title
    lines.append(f"# Career Research Debug Report\nGenerated: {timestamp}\n")

    # Pipeline Metrics
    lines.append("## Pipeline Metrics")
    lines.append(f"- Best matches selected: {len(result['jobs'])}")
    lines.append(f"- Sources used: {', '.join(result['aggregation'].source_breakdown.keys())}")
    lines.append(f"- JSearch: {len(result['jsearch_jobs'])} jobs")
    lines.append(f"- Adzuna: {len(result['adzuna_jobs'])} jobs")
    lines.append(f"- DuckDuckGo: {len(result['ddg_jobs'])} jobs")
    lines.append("")

    # Senior Summary
    lines.append("## Senior Agent Summary")
    lines.append(result["aggregation"].search_summary or "")
    lines.append("")

    # User Profile
    lines.append("## User Profile")
    lines.append("```")
    lines.append(json.dumps(result["profile"], indent=2))
    lines.append("```")

    # Best Matches
    lines.append("\n## Best Matches (Ranked)")
    for job in result["jobs"]:
        data = job.model_dump()
        title = data.get("title", "")
        company = data.get("company", "")

        lines.append(f"### {title} — {company}")
        lines.append(f"- Location: {data.get('location_area', 'Not specified')}")
        lines.append(f"- Remote: {data.get('remote_type', 'Not specified')}")

        salary_min = data.get("salary_min")
        salary_max = data.get("salary_max")
        currency = data.get("salary_currency")

        if salary_min and salary_max and currency:
            lines.append(f"- Salary: {salary_min} to {salary_max} {currency}")
        elif salary_min and currency:
            lines.append(f"- Salary: {salary_min}+ {currency}")
        else:
            lines.append("- Salary: Not specified")

        lines.append(f"- URL: {data.get('job_url', 'N/A')}")
        lines.append(f"- Source: {data.get('source', 'unknown')}")
        lines.append(f"- Reason: {data.get('reason', 'No reason provided')}")
        lines.append("")

    # All Aggregated Jobs
    lines.append("\n## All Aggregated Jobs (Deduplicated)")

    # Source Breakdown
    lines.append("\n## Source Breakdown")
    lines.append("```")
    lines.append(json.dumps(result["aggregation"].source_breakdown, indent=2))
    lines.append("```")

    # Raw Search Criteria
    lines.append("\n## Raw Search Criteria")
    lines.append("```")
    search_criteria_dict = {
        source: (criteria.model_dump() if criteria else None)
        for source, criteria in result["search_criteria"].items()
    }
    lines.append(json.dumps(search_criteria_dict, indent=2))
    lines.append("```")

    # Write to file
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")