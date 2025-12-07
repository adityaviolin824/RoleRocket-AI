import streamlit as st
import requests
import json
import time
import math

# Import from helpers package
from helpers import base_style, spinner, markdown_to_pdf

API_URL = "https://rolerocket-ai-v2.onrender.com/" ###########
REQUEST_TIMEOUT = 240

st.set_page_config(page_title="RoleRocket AI", page_icon="🚀", layout="wide")

# Apply base styles from helpers
base_style.apply_base_styles()

# === GLOBAL STATE ===
if "view" not in st.session_state:
    st.session_state.view = "upload"
if "last_status" not in st.session_state:
    st.session_state.last_status = {}
if "jobs_data" not in st.session_state:
    st.session_state.jobs_data = None
if "selected_jobs" not in st.session_state:
    st.session_state.selected_jobs = []

# === HELPERS ===
def current_step_index(view: str) -> int:
    mapping = {
        "upload": 0,
        "intake_processing": 1,
        "research_processing": 2,
        "results": 2,
        "job_selection": 2,
        "improvement_processing": 3,
        "improvement_results": 3,
    }
    return mapping.get(view, 0)

def render_sidebar():
    with st.sidebar:
        st.markdown("### 🚀 RoleRocket AI")
        st.caption("Agentic career copilot")
        st.markdown("---")
        st.markdown("##### Pipeline")
        
        steps = [
            "Profiling and intake",
            "Job research and scoring",
            "Report presentation",
            "Roadmap and upskilling",
        ]
        
        idx = current_step_index(st.session_state.view)
        
        for i, label in enumerate(steps):
            if i < idx:
                css_class = "rr-step-chip rr-step-done"
                icon = "✅"
            elif i == idx:
                css_class = "rr-step-chip rr-step-active"
                icon = "🟢"
            else:
                css_class = "rr-step-chip rr-step-upcoming"
                icon = "⚪"
            
            st.markdown(
                f'<div class="{css_class}">{icon}<span>{label}</span></div>',
                unsafe_allow_html=True,
            )
        
        st.markdown("---")
        st.markdown(
            "**Pro tips**\n\n"
            "- Upload a focused resume\n"
            "- Set a realistic salary target\n"
            "- Narrow down preferred locations\n"
            "- Be specific in your career goals"
        )



def check_status():
    try:
        r = requests.get(f"{API_URL}/status", timeout=120)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"state": "error", "error": "🚀 RoleRocket's engines are offline. Please check if the backend is running."}
    except requests.exceptions.Timeout:
        return {"state": "error", "error": "⏰ RoleRocket is taking too long to respond. Please try again."}
    except Exception as e:
        return {"state": "error", "error": f"API error: {str(e)}"}

def reset_pipeline():
    try:
        requests.post(f"{API_URL}/reset", timeout=120)
    except Exception:
        pass
    st.session_state.view = "upload"
    st.session_state.last_status = {}
    st.session_state.jobs_data = None
    st.session_state.selected_jobs = []
    st.rerun()

def _upload_and_queue(uploaded_file, preferences):
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        data = {"preferences": json.dumps(preferences)}
        r = requests.post(f"{API_URL}/intake", files=files, data=data, timeout=120)
        if r.status_code in (200, 201):
            return True, "Intake queued."
        return False, f"{r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)

def get_pdf_download(md_content: str, filename: str, title: str):
    """Convert markdown to PDF bytes using helpers.markdown_to_pdf"""
    pdf_bytes = markdown_to_pdf.markdown_to_pdf_bytes(md_content, title=title)
    return st.download_button(
        label=f"📥 Download {filename}",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
    )

def _poll_until(target_step=None):
    start = time.time()
    html_placeholder = st.empty()
    progress_placeholder = st.empty()
    POLL_TIMEOUT = 300
    POLL_INTERVAL = 2
    
    while time.time() - start < POLL_TIMEOUT:
        status = check_status()
        state = status.get("state")
        step = status.get("step")
        error = status.get("error")
        
        elapsed = time.time() - start
        progress_fraction = min(1.0, elapsed / POLL_TIMEOUT)
        
        if state in ("running", "queued"):
            # Use spinner from helpers
            spinner.render_spinning_status(html_placeholder, progress_placeholder, step, progress_fraction)
        elif state == "done":
            if (target_step is None) or (step in (None, target_step)):
                html_placeholder.empty()
                progress_placeholder.empty()
                st.success("✅ Step complete!")
                return status
            else:
                html_placeholder.info("✅ A step finished, moving to the next stage...")
                progress_placeholder.empty()
        elif state == "error":
            html_placeholder.empty()
            progress_placeholder.empty()
            st.error(f"❌ {error}")
            return status
        
        time.sleep(POLL_INTERVAL)
    
    html_placeholder.empty()
    progress_placeholder.empty()
    st.warning("⚠️ This is taking longer than expected. The rocket may have hit some turbulence. Please refresh!")
    return check_status()



# === RENDER SIDEBAR AND HERO ===
render_sidebar()

col_hero_left, col_hero_right = st.columns([3, 2])
with col_hero_left:
    st.markdown('<div class="rr-hero-title">🚀 RoleRocket AI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="rr-hero-tagline">'
        'Launch your next role with agent teams that read your resume, hunt roles, '
        'and build a roadmap.'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="rr-subtle">This rocket runs on agentic fuel.</div>',
        unsafe_allow_html=True,
    )


    

# === MAIN VIEW ROUTER ===
if st.session_state.view == "upload":
    st.markdown("<div style='margin-top: 0.75rem;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="rr-section-title">📥 Upload your resume and preferences</div>', unsafe_allow_html=True)

    col_form, col_help = st.columns([3, 2])

    with col_form:
        uploaded_file = st.file_uploader("📄 Upload Resume (PDF or DOCX)", type=["pdf", "doc", "docx"])
        st.markdown("<div style='margin-top: 0.75rem;'></div>", unsafe_allow_html=True)
        st.subheader("🎯 Job Preferences")
        col1, col2 = st.columns(2)

        with col1:
            preferred_role = st.text_input("Preferred Role", "Manager")
            user_reported_years_experience = st.number_input(
                "Years of Experience", min_value=0.0, max_value=50.0, value=2.0, step=0.5
            )
            target_salary_lpa = st.number_input(
                "Target Salary (LPA)", min_value=0, max_value=200, value=10
            )

        with col2:
            preferred_locations = st.text_input(
                "Preferred Locations (comma separated)", "Mumbai, Bangalore"
            )
            remote_preference = st.selectbox(
                "Remote Preference", options=["hybrid", "remote", "onsite"], index=0
            )
            willing_to_relocate = st.checkbox("Willing to Relocate", value=False)

        career_goals = st.text_area(
            "Career Goals",
            "Build impactful products and achieve financial independence",
            help="Describe your career aspirations and what you want from your next role.",
        )

        launch_col1, launch_col2 = st.columns([2, 3])
        with launch_col1:
            if st.button("🚀 Launch My Career Search!", type="primary"):
                if uploaded_file is None:
                    st.error("⚠️ Please upload a resume file before launching.")
                else:
                    preferences = {
                        "preferred_role": preferred_role,
                        "user_reported_years_experience": user_reported_years_experience,
                        "preferred_locations": [
                            loc.strip()
                            for loc in preferred_locations.split(",")
                            if loc.strip()
                        ],
                        "remote_preference": remote_preference,
                        "target_salary_lpa": target_salary_lpa,
                        "willing_to_relocate": willing_to_relocate,
                        "career_goals": career_goals,
                    }
                    with st.spinner("Fueling the RoleRocket with your profile... 🚀"):
                        ok, msg = _upload_and_queue(uploaded_file, preferences)
                        if ok:
                            st.success("✅ Upload successful. Your profile is queued for processing.")
                            st.session_state.view = "intake_processing"
                            st.rerun()
                        else:
                            st.error(f"❌ Upload failed: {msg}")



elif st.session_state.view == "intake_processing":
    st.markdown("<div style='margin-top: 0.75rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="rr-section-title">📥 Processing your resume</div>',
        unsafe_allow_html=True,
    )
    st.write("The intake agent is extracting skills, experience, and constraints from your resume.")

    auto = st.checkbox("Auto refresh status", value=True, key="auto_intake")

    if auto:
        final_status = _poll_until(target_step="intake")
    else:
        if st.button("🔄 Refresh Status"):
            pass
        final_status = check_status()

    if final_status.get("state") == "done" and final_status.get("step") in (None, "intake"):
        st.success("✅ Intake complete. Your profile has been processed.")
        if st.button("🔍 Start Job Research", type="primary"):
            try:
                r = requests.post(f"{API_URL}/start_research", timeout=120)
                if r.status_code in (200, 201):
                    st.session_state.view = "research_processing"
                    st.rerun()
                else:
                    st.error(f"Failed to start research: {r.text}")
            except Exception as e:
                st.error(f"Error starting research: {e}")
    elif final_status.get("state") == "error":
        st.error(f"❌ Error: {final_status.get('error')}")
        if st.button("🔄 Reset and try again"):
            reset_pipeline()

    

elif st.session_state.view == "research_processing":
    st.markdown("<div style='margin-top: 0.75rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="rr-section-title">🔍 Finding the best roles for you</div>',
        unsafe_allow_html=True,
    )
    st.write("Research team is searching for roles, scoring them, and preparing a concise report.")

    auto = st.checkbox("Auto refresh status", value=True, key="auto_research")

    if auto:
        final_status = _poll_until(target_step="present")
    else:
        if st.button("🔄 Refresh Status"):
            pass
        final_status = check_status()

    if final_status.get("state") == "done" and final_status.get("step") in (None, "present"):
        st.success("🎉 All done. Your personalized job matches are ready.")
        st.session_state.view = "results"
        st.rerun()
    elif final_status.get("state") == "error":
        st.error(f"❌ Error: {final_status.get('error')}")
        if st.button("🔄 Reset and try again"):
            reset_pipeline()

    

elif st.session_state.view == "results":
    st.markdown("<div style='margin-top: 0.75rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="rr-section-title">✅ Your personalized job matches</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Your job research report is ready. Download it or preview it below.")
    with col2:
        try:
            download_response = requests.get(f"{API_URL}/download", timeout=120)
            if download_response.status_code == 200:
                get_pdf_download(download_response.text, "rolerocket_job_matches.pdf", "RoleRocket Job Matches")
        except Exception as e:
            st.error(f"Error downloading: {e}")

    st.markdown("---")
    st.markdown("### 📄 Report preview")

    try:
        download_response = requests.get(f"{API_URL}/download", timeout=120)
        if download_response.status_code == 200:
            st.markdown(download_response.text)
        else:
            st.error("Could not load report preview")
    except Exception as e:
        st.error(f"Error loading preview: {e}")

    st.markdown("---")

    # Large centered primary button
    if st.button("💡 Get guidance to improve my profile", type="primary", use_container_width=True):
        st.session_state.view = "job_selection"
        st.rerun()

    if st.button("🔄 Process another resume", type="primary", use_container_width=True):
        reset_pipeline()

        

elif st.session_state.view == "job_selection":
    
    st.markdown(
        '<div class="rr-section-title">💡 Select roles for profile improvement guidance</div>',
        unsafe_allow_html=True,
    )
    st.write(
        "Choose the roles you are most interested in and you will get tailored guidance "
        "on how to strengthen your profile for those positions."
    )

    if st.session_state.jobs_data is None:
        with st.spinner("Loading job data..."):
            try:
                response = requests.get(f"{API_URL}/aggregation", timeout=120)
                if response.status_code == 200:
                    st.session_state.jobs_data = response.json()
                else:
                    st.error(f"Failed to fetch jobs: {response.status_code}")
                    if st.button("← Back to results"):
                        st.session_state.view = "results"
                        st.rerun()
                    st.stop()
            except Exception as e:
                st.error(f"Error loading jobs: {str(e)}")
                if st.button("← Back to results"):
                    st.session_state.view = "results"
                    st.rerun()
                st.stop()

    job_list = st.session_state.jobs_data.get("aggregation", {}).get("best_matches", [])

    if len(job_list) == 0:
        st.warning("No jobs found in aggregation data.")
        if st.button("← Back to results"):
            st.session_state.view = "results"
            st.rerun()
    else:
        st.write(f"**{len(job_list)} roles found in your job matches.**")
        st.write("Select the ones you would like guidance for:")

        selected_indices = []
        for idx, job in enumerate(job_list):
            job_title = job.get("title", f"Job {idx + 1}")
            company = job.get("company", "Unknown Company")
            location = job.get("location_area", "")

            label = f"{job_title} at {company}"
            if location:
                label += f" • {location}"

            if st.checkbox(label, key=f"job_{idx}"):
                selected_indices.append(idx)

        st.markdown("---")

        col1, col2 = st.columns(2)

        if st.button("🚀 Get my roadmap", type="primary", use_container_width=True):
                selected_jobs_list = [job_list[i] for i in selected_indices]

                selection_output = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "user_intent": "profile_improvement_guidance",
                    "selected_count": len(selected_jobs_list),
                    "selected_jobs": selected_jobs_list,
                }

                try:
                    response = requests.post(
                        f"{API_URL}/save_selection",
                        json=selection_output,
                        timeout=120,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ Saved {result['count']} job(s).")

                        with st.spinner("Launching the advisor... 🚀"):
                            improve_response = requests.post(
                                f"{API_URL}/start_improvement",
                                timeout=120,
                            )

                            if improve_response.status_code == 200:
                                st.success("✅ Analysis started.")
                                st.session_state.view = "improvement_processing"
                                st.rerun()
                            else:
                                st.error(
                                    f"❌ Failed to start analysis: {improve_response.text}"
                                )
                    else:
                        st.error(f"❌ Failed to save: {response.text}")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

        if st.button("← Back to results", type="primary", use_container_width=True):
            st.session_state.view = "results"
            st.rerun()

    

elif st.session_state.view == "improvement_processing":
    st.markdown("<div style='margin-top: 0.75rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="rr-section-title">💡 Generating profile improvement recommendations</div>',
        unsafe_allow_html=True,
    )
    st.write(
        "The advisor agent is comparing your current profile to selected roles and drafting a focused roadmap."
    )

    auto = st.checkbox("Auto refresh status", value=True, key="auto_improvement")

    if auto:
        final_status = _poll_until(target_step="improvement")
    else:
        if st.button("🔄 Refresh Status"):
            pass
        final_status = check_status()

    if final_status.get("state") == "done" and final_status.get("step") in (None, "improvement"):
        st.success("🎉 Profile improvement recommendations are ready.")
        st.session_state.view = "improvement_results"
        st.rerun()
    elif final_status.get("state") == "error":
        st.error(f"❌ Error: {final_status.get('error')}")
        if st.button("← Back to job selection"):
            st.session_state.view = "job_selection"
            st.rerun()

    

elif st.session_state.view == "improvement_results":
    st.markdown("<div style='margin-top: 0.75rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="rr-section-title">🗺️ Your career roadmap</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Your personalized profile improvement guide is ready. Download it or preview it below.")
    with col2:
        try:
            download_response = requests.get(f"{API_URL}/download_improvement", timeout=120)
            if download_response.status_code == 200:
                get_pdf_download(download_response.text, "rolerocket_career_roadmap.pdf", "RoleRocket Career Roadmap")
        except Exception as e:
            st.error(f"Error downloading: {e}")

    st.markdown("---")
    st.markdown("### 📖 Roadmap preview")

    try:
        download_response = requests.get(f"{API_URL}/download_improvement", timeout=120)
        if download_response.status_code == 200:
            st.markdown(download_response.text)
        else:
            st.error("Could not load guide preview")
    except Exception as e:
        st.error(f"Error loading preview: {e}")

    st.markdown("---")

    if st.button("← Back to job matches", type="primary", use_container_width=True):
            st.session_state.view = "results"
            st.rerun()

    if st.button("🔄 Process another resume", type="primary", use_container_width=True):
            reset_pipeline()