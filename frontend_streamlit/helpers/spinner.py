"""
Complete spinner.py with required function
"""
import streamlit as st
import time
import math

_SPINNER_MESSAGES = {
    "intake": ("⏳ Profiling in progress", "Extracting your superpowers and battle scars."),
    "research": ("🔍 Research Hive buzzing", "Hunting top roles that match your skills."),
    "present": ("🎤 Final rehearsal", "Sorting rankings and rehearsing a crisp opening line so your findings arrive pitch perfect."),
    "improvement": ("💡 Roadmap assembly", "Sketching your fast track next steps.")
}

def render_spinning_status(html_placeholder, progress_placeholder, step, progress_fraction):
    """Render step-specific spinner using HTML/CSS."""
    if step in _SPINNER_MESSAGES:
        title, subtitle = _SPINNER_MESSAGES[step]
    else:
        title, subtitle = "⏳ Working on your request", "Cooking up stellar matches..."
    
    html = f"""
    <style>
    .spinner-container {{
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        padding:2rem;
        background:rgba(2,6,23,0.96);
        border-radius:12px;
        box-shadow:0 12px 30px rgba(0,0,0,0.55);
        margin:1rem 0;
    }}
    .spinner {{
        border:4px solid #f3f3f3;
        border-top:4px solid #f97316;
        border-radius:50%;
        width:50px;
        height:50px;
        animation:spin 1s linear infinite;
        margin-bottom:1rem;
    }}
    @keyframes spin {{
        0% {{transform:rotate(0deg);}}
        100% {{transform:rotate(360deg);}}
    }}
    .spinner-title {{
        font-size:1.3rem;
        font-weight:bold;
        color:#fefce8;
        margin-bottom:0.4rem;
        text-align:center;
    }}
    .spinner-subtitle {{
        font-size:0.95rem;
        color:rgba(248,250,252,0.9);
        text-align:center;
        line-height:1.5;
        max-width:520px;
    }}
    </style>
    <div class="spinner-container">
        <div class="spinner"></div>
        <div class="spinner-title">{title}</div>
        <div class="spinner-subtitle">{subtitle}</div>
    </div>
    """

    html_placeholder.markdown(html, unsafe_allow_html=True)
    
    try:
        progress_placeholder.progress(progress_fraction)
    except:
        pass
