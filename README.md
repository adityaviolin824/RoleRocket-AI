# RoleRocket AI

> Agentic end-to-end AI career assistant that turns your resume and preferences into job matches, compatibility scores, and tailored profile-improvement advice for your chosen roles.

---

## Overview

RoleRocket AI ingests your resume (PDF, DOCX, or image), extracts structured profile data, and runs a four-phase pipeline: intake and memory, research-optimized mini-profile generation, multi-source job research with deterministic scoring, and a presentation + advisor phase that produces both a ranked job report and targeted improvement guidance. It is built as an API-first system with a FastAPI backend and a Streamlit frontend, designed to be demoable and inspected in interviews.

---

## Why it’s interesting

- Uses coordinated “agent teams” across multiple phases instead of a single LLM prompt.
- Separates deterministic scoring (pure Python) from LLM-based reasoning and presentation, making behavior explainable and auditable.
- Lets users not only see matched roles but also select specific roles and request deeper, role-specific advice.

---

## How it works (4 phases)

1. **Intake & memory**
   - Accepts modern and scanned resumes (PDF, DOCX, images).
   - Uses OCR and parsing to extract raw text and normalize fields (roles, dates, education, tech stack, projects).
   - Builds a canonical `resume_profile` and stores it in a local SQLite-backed memory (`userprofile.db`), along with user preferences (`job_intake`).

2. **Mini-profile generation for research**
   - Condenses the canonical profile into a compact `JobSearchProfile` used by the research agents.
   - Includes target role, years of experience (user-override or computed from dates), preferred locations, remote preference, salary target, and a small set of high-signal skills.

3. **Multi-source job research & deterministic scoring**
   - Three “junior” researcher agents query multiple job sources and tools (APIs + MCP-backed tools like search/fetch) in parallel.
   - A “senior” researcher merges results, aggressively deduplicates jobs, and keeps 8–12 best matches per run.
   - A scoring engine in Python computes compatibility for each job along dimensions like:
     - Role/title fit
     - Skill overlap
     - Experience and seniority alignment
     - Location and remote fit
     - Salary match (where available)
   - Scores are combined via a configurable weighted formula to produce an overall compatibility score plus a fit label and key-gap tags.

4. **Presentation & tailored advice**
   - A presenter agent turns the scored jobs into a human-readable markdown report (`presenter_output.md`) with:
     - Ranked roles, scores, and short “why it fits” explanations.
     - Matched vs missing skills and quick next-step suggestions.
   - The user then selects roles they care about most.
   - An advisor phase generates a second markdown report (`profile_improvement_output.md`) with role-specific recommendations on:
     - Which skills to prioritize
     - Project and portfolio ideas
     - Resume phrasing and focus areas
     - Interview prep pointers

---

## Key features

- **Four-phase agentic pipeline**  
  Intake & memory → mini-profile → research & scoring → presentation & advisor.

- **Universal resume support**  
  Handles PDFs, DOCX, and image/scanned resumes via OCR, then normalizes into a structured profile.

- **Multi-source research**  
  Three junior researcher agents and one senior aggregator, using multiple job data sources and MCP-based tools for web/search.

- **Deterministic compatibility scoring**  
  Pure Python scoring logic that combines role, skills, experience, location, and salary into an overall compatibility score and fit category.

- **Advisor for selected roles**  
  Users choose interesting roles and trigger a dedicated advisor pass for role-specific improvement guidance.

- **API-first design**  
  FastAPI backend exposes clear endpoints for intake, research, status, aggregation, downloads, and the advisor flow.

- **Streamlit frontend**  
  Provides a multi-step UX: upload, status tracking, viewing matches, selecting roles, and reading/downloadable reports.

- **Deployment-ready**  
  Backend deployed to Render; frontend deployed via Streamlit Cloud (or similar), suitable for live demos.

---

## User flow

1. Upload a resume and set preferences (role, locations, remote preference, salary, goals).
2. System parses/OCRs the resume and creates a canonical profile plus a minimized search profile.
3. Research agents gather jobs from multiple sources; a senior agent merges and filters them.
4. Python-based scoring ranks jobs by compatibility.
5. Presenter agent generates a markdown report with ranked roles and explanations.
6. User reviews the report, selects roles of interest, and requests specialized advice.
7. Advisor phase produces a second markdown report with targeted improvement guidance.

---

## Architecture & tech

- **Backend**: FastAPI orchestrator with endpoints such as:
  - `/intake`, `/start_research`, `/status`, `/aggregation`,
  - `/save_selection`, `/start_improvement`, `/download`, `/download_improvement`, `/reset`, `/health`
- **Frontend**: Streamlit app for the full user journey.
- **Agent orchestration**: Custom agent runners with MCP-backed tools for job search and web research.
- **Memory & artifacts**:
  - SQLite (`userprofile.db`) for user profile memory.
  - JSON outputs (aggregation, scores) and markdown outputs (reports) in `outputs/`.
- **Deployment**:
  - Backend deployed on Render.
  - Frontend deployed via Streamlit Cloud (or another simple host) pointing to the API.

---

## Artifacts produced

- `job_aggregation.json` – Aggregated, deduplicated jobs and metadata from all researcher agents.
- `compatibility_scores.json` – Deterministic scoring results, including per-dimension scores and overall compatibility.
- `presenter_output.md` – Human-facing, ranked job recommendations with explanations.
- `profile_improvement_output.md` – Role-specific improvement guide for the user’s selected roles.

---

---

## Getting started

This repository is designed as an API first service with a simple frontend on top. You can run it locally or deploy the backend and frontend separately.

1. Clone the repository and install dependencies:

   ```bash
   git clone https://github.com/<your-username>/RoleRocket-AI.git
   cd RoleRocket-AI

   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # macOS/Linux: source .venv/bin/activate

   pip install -r requirements.txt

   Or can use UV and directly run uv sync, that will automatically create the required environment
