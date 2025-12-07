# RoleRocket AI

<p align="center">
  <img src="frontend_streamlit/helpers/background/RoleRocket_bg.jpg" alt="RoleRocket Background" style="width:1000px; height:400px; max-width:100%;">
</p>

> Agentic end-to-end career assistant that turns your resume and preferences into job matches, compatibility scores, and tailored profile-improvement advice for your chosen roles.

---



## Live Demo

🚀 **Frontend:** https://rolerocket-ai.streamlit.app  
🔌 **Backend API:** https://rolerocket-ai-v2.onrender.com

⚠️ **Note:** First backend load may take ~50 seconds due to free-tier cold start. Subsequent requests are instant. Image OCR features are disabled on the public demo due to memory limits. Text-based PDF and DOCX parsing works normally. API is deployed using Docker.

---

## Overview

RoleRocket AI ingests a resume (PDF, DOCX, or image), extracts structured profile data, and runs a four-phase pipeline: intake and memory, research-optimized mini-profile generation, multi-source job research with deterministic scoring, and a presentation plus advisor phase that produces both ranked job matches and targeted improvement guidance. It is built as an API-first system with a FastAPI backend and a Streamlit frontend, designed to be demoed and inspected in interviews.

---

## Why this project matters

- Uses coordinated agent teams across multiple phases instead of a single LLM prompt.
- Separates deterministic scoring logic (pure Python) from LLM-based reasoning and presentation, keeping decisions explainable and auditable.
- Allows users to select specific roles and receive deep, role-specific improvement guidance rather than generic recommendations.

---

## How it works (4 phases)

1. **Intake & memory**
   - Accepts modern and scanned resumes (PDF, DOCX, images).
   - Uses parsing and optional OCR to extract raw text and normalize fields such as roles, dates, education, tech stack, and projects.
   - Builds a canonical `resume_profile` and stores it in a local SQLite-backed memory (`userprofile.db`) along with user preferences (`job_intake`).

2. **Mini-profile generation for research**
   - Condenses the canonical profile into a compact `JobSearchProfile` used by research agents.
   - Includes target role, computed or user-specified experience, preferred locations, remote preference, salary target, and high-signal skills.

3. **Multi-source job research & deterministic scoring**
   - Three junior researcher agents query multiple job sources and tools (APIs plus MCP-backed search and fetch tools) in parallel.
   - A senior researcher merges results, aggressively deduplicates listings, and retains 8–12 strong matches per run.
   - A Python-based scoring engine evaluates each job across:
     - Role and title fit  
     - Skill overlap  
     - Experience and seniority alignment  
     - Location and remote fit  
     - Salary match where available
   - Scores are combined using configurable weights to produce an overall compatibility score, fit label, and gap tags.

4. **Presentation & tailored advice**
   - A presenter agent converts scored jobs into a human-readable markdown report (`presenter_output.md`) with ranked roles, scores, and short explanations.
   - Users select roles they care about most.
   - An advisor phase generates a second markdown report (`profile_improvement_output.md`) with role-specific guidance on skills, projects, resume focus, and interview preparation.

---

## Key features

- **Four-phase agentic pipeline**  
  Intake & memory -> mini-profile -> research & scoring -> presentation & advisor

- **Universal resume support**  
  PDF, DOCX, and image resumes with normalization into a structured profile.

- **Multi-source job research**  
  Parallel junior researcher agents and a senior aggregation step across multiple data sources.

- **Deterministic compatibility scoring**  
  Explainable Python scoring across role, skills, experience, location, and salary.

- **Advisor for selected roles**  
  Dedicated second pass for deep, role-specific improvement recommendations.

- **API-first design**  
  FastAPI backend with clear, inspectable endpoints.

- **Deployment-ready**  
  Dockerized backend on Render with a separate Streamlit Cloud frontend.

---

## User flow

1. Upload a resume and set role, location, remote, salary, and goal preferences.  
2. Resume is parsed and converted into a canonical profile and a minimized search profile.  
3. Research agents collect and merge job listings from multiple sources.  
4. Deterministic scoring ranks jobs by compatibility.  
5. A presenter agent generates a ranked markdown report.  
6. The user selects roles of interest and requests deeper guidance.  
7. An advisor agent produces a role-specific improvement report.

---

## Architecture & tech

- **Backend**: FastAPI orchestrator with endpoints such as:
  - `/intake`, `/start_research`, `/status`, `/aggregation`
  - `/save_selection`, `/start_improvement`
  - `/download`, `/download_improvement`, `/reset`, `/health`
- **Frontend**: Streamlit app covering the full user journey.
- **Agent orchestration**: Custom agent runners using MCP-backed tools for job search and web research (DuckDuckGo search MCP, fetch MCP, LibSQL-backed memory MCP).
- **Memory & artifacts**:
  - SQLite (`userprofile.db`) for user profile persistence.
  - JSON and markdown artifacts stored in `outputs/`.
- **Deployment**:
  - Backend deployed on Render.
  - Frontend deployed via Streamlit Cloud pointing to the API.

---

## Artifacts produced

- `job_aggregation.json` – Aggregated and deduplicated job listings.  
- `compatibility_scores.json` – Per-dimension and overall compatibility scores.  
- `presenter_output.md` – Ranked job matches with explanations.  
- `profile_improvement_output.md` – Role-specific improvement guidance.

---

## Getting started

This repository is designed as an API-first service with a lightweight frontend layer.

1. Clone the repository and install dependencies.  
2. Set up configuration and required environment variables.  
3. (Optional) Install MCP tools for local development.  
4. Run `streamlit run frontend_streamlit/RoleRocket_frontend.py` and set `API_URL` to the backend URL.

---

## Future directions

- Expand agent teams and route senior and advisor agents to higher-capability reasoning models.  
- Enable persistent sessions and multi-user support with lightweight authentication.  
- Add more job data sources and custom MCP integrations.  
- Improve observability with frontend-visible logs and feedback-driven tuning.  
- Introduce formal evaluation, safety checks, and clearer user disclosures.  
- Polish UX with richer comparison views and interview-ready exports.

Overall, RoleRocket AI demonstrates a production-style, end-to-end pipeline from resume intake to job research, deterministic scoring, and actionable recommendations, with clear paths for scaling models, data sources, and user experience.
