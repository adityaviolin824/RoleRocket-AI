import base64
from pathlib import Path

import streamlit as st


def apply_base_styles():
    """Inject RoleRocket CSS into Streamlit with a blurred, darker background image."""
    img_path = Path(__file__).parent / "background" / "RoleRocket_bg.jpg"
    bg_url = ""
    if img_path.exists():
        try:
            with img_path.open("rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            bg_url = f"data:image/jpg;base64,{b64}"
        except Exception:
            bg_url = ""

    st.markdown(
        f"""
    <style>

    /* === Layout === */
    .main .block-container {{
        max-width: 1120px;
        padding-top: 2.5rem;
        padding-bottom: 3.5rem;
    }}

    /* Use a fixed pseudo-layer to show the image so we can blur and darken it */
    body, .stApp {{
        background-color: #020617; /* fallback color */
    }}

    body::before, .stApp::before {{
        content: "";
        position: fixed;
        inset: 0;
        z-index: 0;
        pointer-events: none;
        background-image: url("{bg_url}") ;
        background-position: center;
        background-size: cover;
        background-repeat: no-repeat;
        /* blur + darken */
        filter: blur(6px) brightness(0.45);
        transform: scale(1.03); /* avoid sharp edges after blur */
        will-change: transform, filter;
    }}

    /* ensure Streamlit content sits above the background layer */
    .stApp > * {{
        position: relative;
        z-index: 1;
    }}

    /* === Core Cards === */
    .rr-card {{
        position: relative;
        background: linear-gradient(180deg, rgba(15,23,42,0.96), rgba(3,7,18,0.96));
        border-radius: 18px;
        padding: 1.8rem 2rem;
        border: 1px solid rgba(148,163,184,0.30);
        box-shadow:
            0 28px 60px rgba(2,6,23,0.92),
            inset 0 1px 0 rgba(255,255,255,0.04);
        backdrop-filter: blur(6px);
        margin-bottom: 1.7rem;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }}

    .rr-card:hover {{
        transform: translateY(-2px);
        box-shadow:
            0 38px 80px rgba(2,6,23,0.96),
            inset 0 1px 0 rgba(255,255,255,0.05);
    }}

    .rr-card-soft {{
        background: rgba(15,23,42,0.70);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        border: 1px solid rgba(148,163,184,0.24);
        backdrop-filter: blur(4px);
        margin-bottom: 1.4rem;
    }}

    /* === Typography === */
    .rr-hero-title {{
        font-size: 3.0rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        background: linear-gradient(
            115deg,
            #a3a3a3 10%,
            #b45309 50%,
            #92400e 100%
        );
        -webkit-background-clip: text;
        color: transparent;
        margin-bottom: 0.45rem;
        line-height: 1.2;
    }}

    .rr-hero-tagline {{
        font-size: 1.15rem;
        color: #e5e7eb;
        opacity: 0.92;
        max-width: 680px;
    }}

    .rr-section-title {{
        font-size: 1.35rem;
        font-weight: 700;
        color: #e5e7eb;
        margin-bottom: 0.5rem;
        position: relative;
    }}

    .rr-section-title:after {{
        content: "";
        position: absolute;
        left: 0;
        bottom: -6px;
        width: 36px;
        height: 2px;
        background: linear-gradient(90deg, #22c55e, transparent);
        opacity: 0.75;
    }}

    .rr-subtle {{
        color: #9ca3af;
        font-size: 1.0rem;
    }}

    /* === Progress / Steps === */
    .rr-step-chip {{
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        font-size: 0.88rem;
        padding: 0.35rem 0.7rem;
        border-radius: 999px;
        margin-bottom: 0.35rem;
        border: 1px solid transparent;
    }}

    .rr-step-done {{
        background: rgba(22,163,74,0.14);
        border-color: rgba(22,163,74,0.40);
        color: #bbf7d0;
    }}

    .rr-step-active {{
        background: rgba(56,189,248,0.14);
        border-color: rgba(56,189,248,0.45);
        color: #e0f2fe;
        box-shadow: 0 0 18px rgba(56,189,248,0.18);
    }}

    .rr-step-upcoming {{
        background: rgba(55,65,81,0.55);
        border-color: rgba(148,163,184,0.25);
        color: #d1d5db;
    }}

    /* === Inputs / Buttons === */
    .stButton > button {{
        border-radius: 999px;
        font-weight: 600;
        padding: 0.45rem 1.25rem;
        background: linear-gradient(120deg, #0f766e, #115e59);
        color: #f9fafb;
        border: none;
        box-shadow: 0 10px 24px rgba(15,118,110,0.40);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}

    .stButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 16px 34px rgba(15,118,110,0.50);
    }}

    .stTextInput > div > div > input,
    .stTextArea textarea {{
        border-radius: 0.8rem;
        background: rgba(3,7,18,0.88);
        border: 1px solid rgba(148,163,184,0.38);
        color: #e5e7eb;
    }}

    /* === Job Selection === */
    .rr-job-checkbox {{
        padding: 0.65rem 0.85rem;
        border-radius: 0.9rem;
        border: 1px solid rgba(148,163,184,0.35);
        background: rgba(15,23,42,0.86);
        margin-bottom: 0.45rem;
        transition: background 0.15s ease, border 0.15s ease;
    }}

    .rr-job-checkbox:hover {{
        background: rgba(30,41,59,0.90);
        border-color: rgba(59,130,246,0.55);
    }}

    /* === Preview Pane === */
    .rr-preview {{
        background: rgba(3,7,18,0.88);
        border-radius: 16px;
        border: 1px solid rgba(148,163,184,0.48);
        padding: 1.3rem 1.6rem;
        max-height: 560px;
        overflow-y: auto;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02);
    }}

    /* === Pro Tips Sidebar === */
    .rr-protips {{
        margin-top: 0.75rem;
        padding: 0.9rem 1rem;
        border-radius: 0.9rem;
        border: 1px solid rgba(56,189,248,0.45);
        background: radial-gradient(circle at 0% 0%, rgba(56,189,248,0.18), transparent 55%)
                    rgba(15,23,42,0.95);
        box-shadow: 0 14px 30px rgba(15,23,42,0.85);
        font-size: 0.86rem;
        color: #e5e7eb;
    }}

    .rr-protips-title {{
        font-weight: 600;
        font-size: 0.9rem;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        color: #bae6fd;
        margin-bottom: 0.4rem;
    }}

    .rr-protips ul {{
        padding-left: 1.1rem;
        margin: 0;
    }}

    .rr-protips li {{
        margin-bottom: 0.2rem;
    }}

    </style>
    """,
        unsafe_allow_html=True,
    )
