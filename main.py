# app/main.py
import asyncio
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from full_pipeline_files.input_pipeline import run_intake_pipeline
from full_pipeline_files.research_pipeline import run_research_pipeline
from full_pipeline_files.presenter_pipeline import run_presenter_only_pipeline
from profile_improvement_advisor.profile_improvement_pipeline import (
    run_profile_improvement_pipeline,
)
from utils.read_yaml import read_yaml

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION AND PATHS
# ============================================================================
config = read_yaml(Path("config/master_config.yaml"))
MODEL = config.llm

INPUT_DIR = Path("input")
MEMORY_DIR = Path("memory")
OUTPUT_DIR = Path("outputs")
INPUT_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = MEMORY_DIR / "userprofile.db"

# ============================================================================
# LIFESPAN EVENTS
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("=" * 80)
    logger.info("🚀 Job Research Pipeline API Starting")
    logger.info("=" * 80)
    logger.info(f"Model: {MODEL}")
    logger.info(f"Directory structure:")
    logger.info(f"  • Input:   {INPUT_DIR}")
    logger.info(f"  • Memory:  {MEMORY_DIR}")
    logger.info(f"  • Outputs: {OUTPUT_DIR}")
    logger.info(f"  • DB:      {DB_PATH}")
    logger.info("=" * 80)
    
    yield
    
    # Shutdown
    logger.info("🛑 Job Research Pipeline API Shutting Down")

# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================
app = FastAPI(title="Job Research Pipeline", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ============================================================================
# GLOBAL STATE TRACKER
# ============================================================================
_state: Dict[str, Any] = {
    "state": "idle",
    "step": None,
    "file": None,
    "preferences": None,
    "error": None,
    "aggregation_path": None,
    "presenter_md": None,
    "improvement_output": None,
    "improvement_result": None,
}

# ============================================================================
# BACKGROUND TASK FUNCTIONS
# ============================================================================
async def _run_intake_task(file_path: str, preferences: Dict[str, Any]):
    """Background task: Process resume and extract user profile."""
    logger.info(f"▶️  Starting intake pipeline")
    logger.info(f"   Resume: {Path(file_path).name}")
    logger.info(f"   DB: {DB_PATH}")
    
    _state.update({"state": "running", "step": "intake", "error": None})
    
    try:
        await run_intake_pipeline(
            resume_path=file_path,
            intake_answers=preferences,
            model=MODEL
        )
        
        logger.info(f"✅ Intake pipeline completed")
        _state["state"] = "done"
        
    except Exception as e:
        logger.error(f"❌ Intake pipeline failed: {str(e)}")
        logger.exception("Full traceback:")
        _state.update({"state": "error", "error": str(e)})

async def _run_research_task() -> bool:
    """Background task: Search for job opportunities."""
    logger.info(f"▶️  Starting research pipeline")
    
    _state.update({"state": "running", "step": "research", "error": None})
    
    try:
        job_agg_path = OUTPUT_DIR / "job_aggregation.json"
        logger.info(f"   Output: {job_agg_path.name}")
        
        await run_research_pipeline(
            model=MODEL,
            job_agg_path=str(job_agg_path)
        )
        
        logger.info(f"✅ Research pipeline completed")
        
        _state.update({
            "state": "done",
            "aggregation_path": str(job_agg_path.resolve())
        })
        return True
        
    except Exception as e:
        logger.error(f"❌ Research pipeline failed: {str(e)}")
        logger.exception("Full traceback:")
        _state.update({"state": "error", "error": str(e)})
        return False

async def _run_present_task() -> bool:
    """Background task: Generate final presentation."""
    logger.info(f"▶️  Starting presenter pipeline")
    
    _state.update({"state": "running", "step": "present", "error": None})
    
    try:
        agg_path = _state.get("aggregation_path") or str(OUTPUT_DIR / "job_aggregation.json")
        scored_out_path = OUTPUT_DIR / "compatibility_scores.json"
        presenter_md_path = OUTPUT_DIR / "presenter_output.md"
        
        await run_presenter_only_pipeline(
            model=MODEL,
            input_agg_path=agg_path,
            scored_out_path=str(scored_out_path),
        )
        
        if not presenter_md_path.exists():
            raise ValueError(f"Presenter output not created")
        
        logger.info(f"✅ Presenter pipeline completed")
        
        _state.update({
            "state": "done",
            "presenter_md": str(presenter_md_path.resolve())
        })
        return True
        
    except Exception as e:
        logger.error(f"❌ Presenter pipeline failed: {str(e)}")
        logger.exception("Full traceback:")
        _state.update({"state": "error", "error": str(e)})
        return False

async def _run_full_pipeline():
    """Orchestrator: Run research and presenter pipelines."""
    logger.info(f"🚀 Starting full pipeline (research -> present)")
    
    if await _run_research_task():
        await _run_present_task()
        
    logger.info(f"🏁 Full pipeline completed")

async def _run_improvement_task():
    """Background task: Run profile improvement pipeline."""
    logger.info(f"▶️  Starting profile improvement pipeline")
    
    _state.update({"state": "running", "step": "improvement", "error": None})
    
    try:
        selection_path = INPUT_DIR / "user_selected_jobs.json"
        output_path = OUTPUT_DIR / "profile_improvement_output.md"
        
        # Load selection data
        logger.info(f"   📂 Loading selection from {selection_path.name}")
        with open(selection_path, 'r', encoding='utf-8') as f:
            selection_data = json.load(f)
        
        logger.info(f"   ✅ Loaded {selection_data.get('selected_count', 0)} jobs")
        
        # Run the improvement pipeline
        logger.info(f"   🤖 Calling run_profile_improvement_pipeline()...")
        result = await run_profile_improvement_pipeline()
        logger.info(f"   ✅ Pipeline function returned successfully!")
        
        status = result.get("status", "unknown")
        total = result.get("total_jobs", 0)
        successful = result.get("successful", 0)
        
        logger.info(f"   📊 Pipeline: {status} ({successful}/{total} successful)")
        
        # Build markdown output
        logger.info(f"   📝 Building markdown output...")
        markdown_output = f"# Profile Improvement Report\n\n"
        markdown_output += f"**Generated:** {result.get('timestamp', 'N/A')}\n\n"
        markdown_output += f"**Jobs Analyzed:** {total}\n\n"
        markdown_output += f"**Successful:** {successful}\n\n"
        markdown_output += "---\n\n"
        
        for idx, job_result in enumerate(result.get("results", []), 1):
            markdown_output += f"## {idx}. {job_result.get('job_title', 'Unknown')}\n\n"
            markdown_output += f"**Company:** {job_result.get('company', 'N/A')}\n\n"
            markdown_output += f"**Location:** {job_result.get('location', 'N/A')}\n\n"
            
            if job_result.get('job_url'):
                markdown_output += f"**Link:** {job_result['job_url']}\n\n"
            
            markdown_output += f"### Improvement Recommendations\n\n"
            markdown_output += job_result.get('summary_text', 'No recommendations available')
            markdown_output += "\n\n---\n\n"
        
        logger.info(f"   📝 Markdown built ({len(markdown_output)} chars)")
        
        # Save to file
        logger.info(f"   💾 Saving to {output_path.name}...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_output, encoding="utf-8")
        
        # Verify file was written
        if output_path.exists():
            file_size = output_path.stat().st_size
            logger.info(f"   ✅ File saved successfully ({file_size} bytes)")
        else:
            logger.error(f"   ❌ File was NOT created!")
        
        logger.info(f"✅ Profile improvement pipeline completed")
        logger.info(f"   Output: {output_path.name}")
        
        _state.update({
            "state": "done",
            "improvement_output": str(output_path.resolve()),
            "improvement_result": result
        })
        
        logger.info(f"   ✅ State updated to 'done'")
        
    except Exception as e:
        logger.error(f"❌ Profile improvement pipeline failed: {str(e)}")
        logger.exception("Full traceback:")
        _state.update({"state": "error", "error": str(e)})

# ============================================================================
# API ENDPOINTS
# ============================================================================
@app.post("/intake")
async def intake(
    file: UploadFile = File(...),
    preferences: str = Form(...)
):
    """Upload resume and start intake pipeline."""
    logger.info(f"📨 POST /intake - {file.filename}")
    
    if _state["state"] in ["queued", "running"]:
        raise HTTPException(409, f"Pipeline already in progress: {_state['step']}")
    
    dest = INPUT_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    logger.info(f"   Saved: {dest.name}")
    
    try:
        prefs = json.loads(preferences)
    except json.JSONDecodeError as e:
        raise HTTPException(400, "preferences must be valid JSON")
    
    _state.update({
        "state": "queued",
        "step": "intake",
        "file": str(dest),
        "preferences": prefs,
        "error": None,
        "aggregation_path": None,
        "presenter_md": None,
        "improvement_output": None,
        "improvement_result": None,
    })
    
    asyncio.create_task(_run_intake_task(str(dest), prefs))
    logger.info(f"   🔄 Intake task queued")
    
    return {"status": "queued", "step": "intake"}

@app.post("/start_research")
async def start_research():
    """Start research and presenter pipelines."""
    logger.info(f"📨 POST /start_research")
    
    if not _state.get("file"):
        raise HTTPException(400, "No resume uploaded. Call /intake first.")
    
    if _state["step"] == "intake" and _state["state"] == "running":
        raise HTTPException(409, "Intake pipeline still running.")
    
    if _state["step"] in ["research", "present"] and _state["state"] in ["queued", "running"]:
        return {
            "status": "already_in_progress",
            "state": _state["state"],
            "step": _state["step"]
        }
    
    _state.update({"state": "queued", "step": "research", "error": None})
    asyncio.create_task(_run_full_pipeline())
    logger.info(f"   🔄 Research pipeline queued")
    
    return {"status": "queued", "step": "research"}

@app.get("/status")
async def get_status():
    """Get current pipeline status."""
    return JSONResponse(content=_state)

@app.get("/download")
async def download_results():
    """Download the final markdown report."""
    logger.info(f"📨 GET /download")
    
    path = Path(_state.get("presenter_md") or OUTPUT_DIR / "presenter_output.md")
    
    if not path.exists():
        raise HTTPException(404, f"File not found")
    
    logger.info(f"   Serving: {path.name}")
    return FileResponse(path, media_type="text/markdown", filename="job_matches.md")

@app.get("/aggregation")
async def get_aggregation():
    """Get job aggregation JSON data."""
    logger.info(f"📨 GET /aggregation")
    
    path = Path(_state.get("aggregation_path") or OUTPUT_DIR / "job_aggregation.json")
    
    if not path.exists():
        raise HTTPException(404, f"File not found")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"   Serving: {path.name}")
    return JSONResponse(content=data)

@app.post("/save_selection")
async def save_selection(selection_data: Dict[str, Any] = Body(...)):
    """Save user's job selection to input/user_selected_jobs.json."""
    logger.info(f"📨 POST /save_selection")
    
    try:
        save_path = INPUT_DIR / "user_selected_jobs.json"
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(selection_data, f, indent=2, ensure_ascii=False)
        
        selected_count = selection_data.get("selected_count", 0)
        
        logger.info(f"✅ Selection saved: {selected_count} jobs")
        
        return {
            "status": "saved",
            "path": str(save_path),
            "count": selected_count,
            "timestamp": selection_data.get("timestamp")
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to save selection: {str(e)}")
        raise HTTPException(500, f"Failed to save selection: {str(e)}")

@app.post("/start_improvement")
async def start_improvement():
    """Run profile improvement pipeline for selected jobs."""
    logger.info(f"📨 POST /start_improvement")
    
    selection_path = INPUT_DIR / "user_selected_jobs.json"
    if not selection_path.exists():
        raise HTTPException(400, "No job selection found. Select jobs first via /save_selection")
    
    _state.update({"state": "queued", "step": "improvement", "error": None})
    asyncio.create_task(_run_improvement_task())
    logger.info(f"   🔄 Profile improvement task queued")
    
    return {"status": "queued", "message": "Profile improvement analysis started"}

@app.get("/download_improvement")
async def download_improvement():
    """Download profile improvement report."""
    logger.info(f"📨 GET /download_improvement")
    
    path = Path(_state.get("improvement_output") or OUTPUT_DIR / "profile_improvement_output.md")
    
    if not path.exists():
        raise HTTPException(404, "Profile improvement report not found")
    
    logger.info(f"   Serving: {path.name}")
    return FileResponse(path, media_type="text/markdown", filename="profile_improvement.md")

@app.post("/reset")
async def reset_state():
    """Reset pipeline state."""
    logger.info(f"📨 POST /reset")
    
    if _state["state"] == "running":
        raise HTTPException(409, "Cannot reset while pipeline is running")
    
    _state.update({
        "state": "idle",
        "step": None,
        "file": None,
        "preferences": None,
        "error": None,
        "aggregation_path": None,
        "presenter_md": None,
        "improvement_output": None,
        "improvement_result": None,
    })
    
    logger.info(f"   ✅ State reset")
    return {"status": "reset", "message": "Pipeline state cleared"}

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "model": MODEL,
        "pipeline_state": _state["state"],
        "paths": {
            "input": str(INPUT_DIR),
            "memory": str(MEMORY_DIR),
            "outputs": str(OUTPUT_DIR),
            "database": str(DB_PATH)
        }
    }
