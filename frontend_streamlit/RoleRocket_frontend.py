import streamlit as st
import requests
import json
import time
import math


API_URL = "http://127.0.0.1:8000" # will change after deployment
REQUEST_TIMEOUT = 45


st.set_page_config(page_title="RoleRocket AI", page_icon="🚀", layout="wide")


if "view" not in st.session_state:
    st.session_state.view = "upload"
if "last_status" not in st.session_state:
    st.session_state.last_status = {}
if "jobs_data" not in st.session_state:
    st.session_state.jobs_data = None
if "selected_jobs" not in st.session_state:
    st.session_state.selected_jobs = []


def check_status():
    """Safe status check with timeout and friendly fallback."""
    try:
        r = requests.get(f"{API_URL}/status", timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"state": "error", "error": "🚀 RoleRocket's engines are offline. Please check if the backend is running."}
    except requests.exceptions.Timeout:
        return {"state": "error", "error": "⏰ RoleRocket is taking too long to respond. Please try again."}
    except Exception as e:
        return {"state": "error", "error": f"API error: {str(e)}"}


def reset_pipeline():
    """Reset the pipeline state and go back to upload view."""
    try:
        requests.post(f"{API_URL}/reset", timeout=REQUEST_TIMEOUT)
    except Exception:
        pass
    st.session_state.view = "upload"
    st.session_state.last_status = {}
    st.session_state.jobs_data = None
    st.session_state.selected_jobs = []
    st.rerun()


def _upload_and_queue(uploaded_file, preferences):
    """Upload resume and preferences to the API. Returns (ok, message)."""
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        data = {"preferences": json.dumps(preferences)}
        r = requests.post(f"{API_URL}/intake", files=files, data=data, timeout=REQUEST_TIMEOUT)
        if r.status_code in (200, 201):
            return True, "Intake queued."
        return False, f"{r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)



_SPINNER_HTML = """
<style>
    .spinner-container {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin: 1rem 0;
    }}
    .spinner {{
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        animation: spin 1s linear infinite;
        margin-bottom: 1rem;
    }}
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    .spinner-title {{
        font-size: 1.5rem;
        font-weight: bold;
        color: white;
        margin-bottom: 0.5rem;
        text-align: center;
    }}
    .spinner-subtitle {{
        font-size: 1rem;
        color: rgba(255, 255, 255, 0.9);
        text-align: center;
        line-height: 1.5;
        max-width: 500px;
    }}
</style>
<div class="spinner-container">
    <div class="spinner"></div>
    <div class="spinner-title">{title}</div>
    <div class="spinner-subtitle">{subtitle}</div>
</div>
"""


def _render_loading_block(html_placeholder, progress_placeholder, title, subtitle, progress_fraction=None):
    """Render the spinner + messages into separate placeholders."""
    html = _SPINNER_HTML.format(title=title, subtitle=subtitle)
    html_placeholder.markdown(html, unsafe_allow_html=True)
    
    try:
        if progress_fraction is None:
            frac = (math.sin(time.time() / 2) + 1) / 2  # pulsing effect
        else:
            frac = float(max(0.0, min(1.0, progress_fraction)))
        progress_placeholder.progress(frac)
    except Exception:
        pass


def _poll_until(target_step=None):
    """Poll the API until a terminal state is reached for the target step."""
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
            if step == "intake":
                title = "⏳ Profiling in progress"
                subtitle = "Our resume spelunkers are diving deep, extracting your superpowers and battle scars."
                _render_loading_block(html_placeholder, progress_placeholder, title, subtitle, progress_fraction)
            elif step == "research":
                title = "🔍 The Research Hive is buzzing"
                subtitle = "Our researchers are frantically hunting top roles for you, armed with coffee and determination."
                _render_loading_block(html_placeholder, progress_placeholder, title, subtitle, progress_fraction)
            elif step == "present":
                title = "📊 Final polish in progress"
                subtitle = "The presenter agent is giving the report a tuxedo and a bow tie while adding finishing touches."
                _render_loading_block(html_placeholder, progress_placeholder, title, subtitle, progress_fraction)
            elif step == "improvement":
                title = "💡 Personal roadmap assembly"
                subtitle = "Our trillion-parameter advisor is carefully sketching your fast-track roadmap, with dramatic flair."
                _render_loading_block(html_placeholder, progress_placeholder, title, subtitle, progress_fraction)
            else:
                title = "⏳ Working on your request"
                subtitle = "We are juggling a few things behind the scenes and cooking up stellar matches for you."
                _render_loading_block(html_placeholder, progress_placeholder, title, subtitle, progress_fraction)


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


st.title("🚀 RoleRocket AI")
st.markdown("*This rocket is powered by Agentic fuel* 🔥")
st.markdown("**Launch your next role with AI-powered matching and personalized guidance.** Upload your resume to begin.")



if st.session_state.view == "upload":
    st.write("Upload your resume and share a few preferences so our system can find good role matches for you.")


    uploaded_file = st.file_uploader("📄 Upload Resume (PDF or DOCX)", type=["pdf", "doc", "docx"])


    st.subheader("🎯 Job Preferences")
    col1, col2 = st.columns(2)


    with col1:
        preferred_role = st.text_input("Preferred Role", "Manager")
        user_reported_years_experience = st.number_input(
            "Years of Experience", min_value=0.0, max_value=50.0, value=2.0, step=0.5
        )
        target_salary_lpa = st.number_input("Target Salary (LPA)", min_value=0, max_value=200, value=10)


    with col2:
        preferred_locations = st.text_input("Preferred Locations (comma separated)", "Mumbai, Bangalore")
        remote_preference = st.selectbox("Remote Preference", options=["hybrid", "remote", "onsite"], index=0)
        willing_to_relocate = st.checkbox("Willing to Relocate", value=False)


    career_goals = st.text_area("Career Goals", "Build impactful products and achieve financial independence", help="Describe your career aspirations and goals")


    if st.button("🚀 Launch My Career Search!", type="primary"):
        if uploaded_file is None:
            st.error("⚠️ Please upload a resume file before launching.")
        else:
            preferences = {
                "preferred_role": preferred_role,
                "user_reported_years_experience": user_reported_years_experience,
                "preferred_locations": [loc.strip() for loc in preferred_locations.split(",") if loc.strip()],
                "remote_preference": remote_preference,
                "target_salary_lpa": target_salary_lpa,
                "willing_to_relocate": willing_to_relocate,
                "career_goals": career_goals,
            }
            with st.spinner("Fueling the RoleRocket with your profile... 🚀"):
                ok, msg = _upload_and_queue(uploaded_file, preferences)
                if ok:
                    st.success("✅ Upload successful! Your profile is queued for processing.")
                    st.session_state.view = "intake_processing"
                    st.rerun()
                else:
                    st.error(f"❌ Upload failed: {msg}")



elif st.session_state.view == "intake_processing":
    st.subheader("📥 Processing Your Resume")
    st.write("Our system is extracting key details from your resume to build a profile for job matching.")
    
    auto = st.checkbox("Auto refresh status", value=True, key="auto_intake")
    
    if auto:
        final_status = _poll_until(target_step="intake")
    else:
        if st.button("🔄 Refresh Status"):
            pass
        final_status = check_status()


    if final_status.get("state") == "done" and final_status.get("step") in (None, "intake"):
        st.success("✅ Intake complete! Your profile has been processed.")
        if st.button("🔍 Start Job Research", type="primary"):
            try:
                r = requests.post(f"{API_URL}/start_research", timeout=REQUEST_TIMEOUT)
                if r.status_code in (200, 201):
                    st.session_state.view = "research_processing"
                    st.rerun()
                else:
                    st.error(f"Failed to start research: {r.text}")
            except Exception as e:
                st.error(f"Error starting research: {e}")
    elif final_status.get("state") == "error":
        st.error(f"❌ Error: {final_status.get('error')}")
        if st.button("🔄 Reset & Try Again"):
            reset_pipeline()



elif st.session_state.view == "research_processing":
    st.subheader("🔍 Finding the best roles for you")
    st.write("We are searching opportunities and preparing a concise report of role matches tailored to your profile.")
    
    auto = st.checkbox("Auto refresh status", value=True, key="auto_research")
    
    if auto:
        final_status = _poll_until(target_step="present")
    else:
        if st.button("🔄 Refresh Status"):
            pass
        final_status = check_status()


    if final_status.get("state") == "done" and final_status.get("step") in (None, "present"):
        st.success("🎉 All done! Your personalized job matches are ready.")
        st.session_state.view = "results"
        st.rerun()
    elif final_status.get("state") == "error":
        st.error(f"❌ Error: {final_status.get('error')}")
        if st.button("🔄 Reset & Try Again"):
            reset_pipeline()



elif st.session_state.view == "results":
    st.subheader("✅ Your Personalized Job Matches")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("**Your job research report is ready!** Download it or preview it below.")
    with col2:
        try:
            download_response = requests.get(f"{API_URL}/download", timeout=REQUEST_TIMEOUT)
            if download_response.status_code == 200:
                st.download_button(
                    label="📥 Download",
                    data=download_response.content,
                    file_name="rolerocket_job_matches.md",
                    mime="text/markdown",
                )
        except Exception as e:
            st.error(f"Error downloading: {e}")


    st.markdown("---")
    st.markdown("### 📄 Report Preview")
    try:
        download_response = requests.get(f"{API_URL}/download", timeout=REQUEST_TIMEOUT)
        if download_response.status_code == 200:
            st.markdown(download_response.text)
        else:
            st.error("Could not load report preview")
    except Exception as e:
        st.error(f"Error loading preview: {e}")


    st.markdown("---")
    
    if st.button("💡 Get Guidance to Improve My Profile", type="primary"):
        st.session_state.view = "job_selection"
        st.rerun()
    
    if st.button("🔄 Process Another Resume"):
        reset_pipeline()



elif st.session_state.view == "job_selection":
    st.subheader("💡 Select Roles for Profile Improvement Guidance")
    st.write("Choose the roles you're most interested in, and we'll provide tailored guidance on how to strengthen your profile for those positions.")
    
    if st.session_state.jobs_data is None:
        with st.spinner("Loading job data..."):
            try:
                response = requests.get(f"{API_URL}/aggregation", timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    st.session_state.jobs_data = response.json()
                else:
                    st.error(f"Failed to fetch jobs: {response.status_code}")
                    if st.button("← Back to Results"):
                        st.session_state.view = "results"
                        st.rerun()
                    st.stop()
            except Exception as e:
                st.error(f"Error loading jobs: {str(e)}")
                if st.button("← Back to Results"):
                    st.session_state.view = "results"
                    st.rerun()
                st.stop()
    
    job_list = st.session_state.jobs_data.get("aggregation", {}).get("best_matches", [])
    
    if len(job_list) == 0:
        st.warning("No jobs found in aggregation data.")
        if st.button("← Back to Results"):
            st.session_state.view = "results"
            st.rerun()
    else:
        st.write(f"**{len(job_list)} roles found in your job matches.**")
        st.write("Select the ones you'd like guidance for:")
        
        selected_indices = []
        for idx, job in enumerate(job_list):
            job_title = job.get('title', f"Job {idx + 1}")
            company = job.get('company', "Unknown Company")
            location = job.get('location_area', "")
            
            label = f"{job_title} at {company}"
            if location:
                label += f" • {location}"
            
            if st.checkbox(label, key=f"job_{idx}"):
                selected_indices.append(idx)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("← Back to Results"):
                st.session_state.view = "results"
                st.rerun()
        
        with col2:
            if st.button("🚀 Get My Roadmap", type="primary", disabled=len(selected_indices) == 0):
                selected_jobs_list = [job_list[i] for i in selected_indices]
                
                selection_output = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "user_intent": "profile_improvement_guidance",
                    "selected_count": len(selected_jobs_list),
                    "selected_jobs": selected_jobs_list
                }
                
                try:
                    response = requests.post(
                        f"{API_URL}/save_selection",
                        json=selection_output,
                        timeout=REQUEST_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ Saved {result['count']} job(s)!")
                        
                        with st.spinner("Launching the advisor... 🚀"):
                            improve_response = requests.post(
                                f"{API_URL}/start_improvement",
                                timeout=REQUEST_TIMEOUT
                            )
                            
                            if improve_response.status_code == 200:
                                st.success("✅ Analysis started!")
                                st.session_state.view = "improvement_processing"
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to start analysis: {improve_response.text}")
                    else:
                        st.error(f"❌ Failed to save: {response.text}")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")



elif st.session_state.view == "improvement_processing":
    st.subheader("💡 Generating Profile Improvement Recommendations")
    st.write("Our AI advisor is analyzing your profile against the selected roles and preparing personalized guidance.")
    
    auto = st.checkbox("Auto refresh status", value=True, key="auto_improvement")
    
    if auto:
        final_status = _poll_until(target_step="improvement")
    else:
        if st.button("🔄 Refresh Status"):
            pass
        final_status = check_status()


    if final_status.get("state") == "done" and final_status.get("step") in (None, "improvement"):
        st.success("🎉 Profile improvement recommendations are ready!")
        st.session_state.view = "improvement_results"
        st.rerun()
    elif final_status.get("state") == "error":
        st.error(f"❌ Error: {final_status.get('error')}")
        if st.button("← Back to Job Selection"):
            st.session_state.view = "job_selection"
            st.rerun()



elif st.session_state.view == "improvement_results":
    st.subheader("🗺️ Your Career Roadmap")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("**Your personalized profile improvement guide is ready!** Download it or preview it below.")
    with col2:
        try:
            download_response = requests.get(f"{API_URL}/download_improvement", timeout=REQUEST_TIMEOUT)
            if download_response.status_code == 200:
                st.download_button(
                    label="📥 Download",
                    data=download_response.content,
                    file_name="rolerocket_career_roadmap.md",
                    mime="text/markdown",
                )
        except Exception as e:
            st.error(f"Error downloading: {e}")


    st.markdown("---")
    st.markdown("### 📖 Roadmap Preview")
    try:
        download_response = requests.get(f"{API_URL}/download_improvement", timeout=REQUEST_TIMEOUT)
        if download_response.status_code == 200:
            st.markdown(download_response.text)
        else:
            st.error("Could not load guide preview")
    except Exception as e:
        st.error(f"Error loading preview: {e}")


    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Job Matches"):
            st.session_state.view = "results"
            st.rerun()
    
    with col2:
        if st.button("🔄 Process Another Resume"):
            reset_pipeline()
