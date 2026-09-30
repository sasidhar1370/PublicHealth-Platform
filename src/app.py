"""Study Assistant - Streamlit Web Application.

Editorial, industrial study assistant with multi-provider RAG extraction,
asymmetric bento layout, interactive assessment, and textbook citations.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import sys
from pathlib import Path
from typing import Any, List, Optional
import streamlit as st

# Ensure project root is present in sys.path regardless of execution CWD
_BASE_DIR = Path(__file__).resolve().parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from src.config import (
    ALLOWED_DIFFICULTIES,
    ALLOWED_QUESTION_TYPES,
    DEFAULT_PROVIDER,
    PROVIDER_ANTHROPIC,
    PROVIDER_CUSTOM,
    PROVIDER_GEMINI,
    PROVIDER_GROQ,
    PROVIDER_MODELS,
    PROVIDER_OPENAI,
    SUPPORTED_PROVIDERS,
    TEXTBOOKS_DIR,
    get_provider_api_keys,
    parse_multi_keys,
)
from src.rag_engine import (
    APIKeyMissingError,
    NoTextbooksFoundError,
    QuestionItem,
    QuestionSet,
    RAGError,
    RAGGenerationError,
    delete_textbook_pdf,
    generate_questions,
    generate_questions_divide_and_conquer,
    generate_questions_parallel,
    get_index_status,
    load_or_build_index,
    purge_index_storage,
    save_uploaded_pdf,
)

# Configure logging
logger = logging.getLogger("study_assistant.app")


def is_valid_api_key(key: str | None, provider: str = "") -> bool:
    """Validate that an API key is present and non-empty.

    Accepts any non-empty string so OpenRouter, custom OpenAI-compatible tokens,
    Gemini, Groq, Anthropic, or local keys are never falsely flagged as invalid.
    """
    if not key or not isinstance(key, str):
        return False
    return bool(key.strip())


def _get_pid(provider: str) -> str:
    """Sanitize a provider name into a safe session-state key fragment."""
    return (
        provider.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("-", "_")
        .replace(".", "_")
    )


def _render_provider_key_section(provider: str) -> dict:
    """Render one provider configuration block without generic icons or pills."""
    pid = _get_pid(provider)
    stored_key_name = f"sk_{pid}"
    show_flag_name = f"sf_{pid}"

    env_keys = get_provider_api_keys(provider)
    env_default = env_keys[0] if env_keys else ""
    if stored_key_name not in st.session_state:
        st.session_state[stored_key_name] = env_default

    current_val: str = st.session_state[stored_key_name]
    show: bool = st.session_state.get(show_flag_name, False)
    is_armed: bool = is_valid_api_key(current_val, provider)

    status_tag = "ACTIVE" if is_armed else "OFFLINE"
    status_class = "tag-active" if is_armed else "tag-offline"

    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
            <span style="font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:0.92rem; color:#E5E5E5; text-transform:uppercase; letter-spacing:0.04em;">{provider}</span>
            <span class="{status_class}">{status_tag}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_key, col_eye = st.columns([5, 1])
    with col_key:
        placeholder = f"{provider} API Key"
        if show:
            entered = st.text_input(
                f"Key_{pid}",
                value=current_val,
                key=f"wi_v_{pid}",
                placeholder=placeholder,
                label_visibility="collapsed",
            )
        else:
            entered = st.text_input(
                f"Key_{pid}",
                value=current_val,
                key=f"wi_h_{pid}",
                type="password",
                placeholder=placeholder,
                label_visibility="collapsed",
            )
    with col_eye:
        eye_label = "HIDE" if show else "SHOW"
        if st.button(eye_label, key=f"eye_{pid}", use_container_width=True):
            new_show = not show
            st.session_state[stored_key_name] = entered
            target_wkey = f"wi_v_{pid}" if new_show else f"wi_h_{pid}"
            st.session_state[target_wkey] = entered
            st.session_state[show_flag_name] = new_show
            st.rerun()

    st.session_state[stored_key_name] = entered

    if is_armed and st.button(f"CLEAR KEY", key=f"clr_{pid}", use_container_width=True):
        st.session_state[stored_key_name] = ""
        for wk in (f"wi_v_{pid}", f"wi_h_{pid}"):
            st.session_state.pop(wk, None)
        st.rerun()

    selected_model = None
    custom_base_url = None
    if is_armed:
        if provider == PROVIDER_CUSTOM:
            custom_base_url = st.text_input(
                "Base URL",
                value=st.session_state.get(f"base_{pid}", "https://openrouter.ai/api/v1"),
                key=f"base_{pid}",
            )
            selected_model = st.text_input(
                "Model Identifier",
                value=st.session_state.get(f"mdl_{pid}", "deepseek/deepseek-chat"),
                key=f"mdl_{pid}",
            )
        else:
            models = PROVIDER_MODELS.get(provider, [])
            if models:
                selected_model = st.selectbox(
                    f"Model ({provider})",
                    options=models,
                    index=0,
                    key=f"mdl_{pid}",
                    label_visibility="collapsed",
                )

    return {
        "provider": provider,
        "keys": [entered.strip()] if entered.strip() else [],
        "model": selected_model,
        "custom_base_url": custom_base_url,
        "is_armed": is_armed,
    }


# Page Configuration
st.set_page_config(
    page_title="Study Assistant",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Architectural, Editorial Anti-AI CSS
st.markdown(
    """
    <style>
    /* Typography: Playfair Display (Serif Title) & Space Grotesk (Body & Data) */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,900;1,600&family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

    /* Global Matte Deep Charcoal & Sharp Borders */
    html, body, .stApp {
        background-color: #121212 !important;
        font-family: 'Space Grotesk', -apple-system, sans-serif !important;
        color: #E2E2E2 !important;
        letter-spacing: -0.01em;
    }

    h1, h2, h3, .editorial-title {
        font-family: 'Playfair Display', Georgia, serif !important;
        color: #F5F5F5 !important;
        letter-spacing: -0.02em;
    }

    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main Container & 8px Grid Spacing */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3.5rem;
        max-width: 1280px;
    }

    /* Sidebar Matte Surface */
    [data-testid="stSidebar"] {
        background-color: #161616 !important;
        border-right: 1px solid #2E2E2E !important;
    }

    /* Header Bento Panel */
    .header-bento {
        background-color: #1A1A1A;
        border: 1px solid #2E2E2E;
        border-radius: 4px;
        padding: 2.2rem 2.5rem;
        margin-bottom: 1.5rem;
    }
    .header-bento h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.15;
    }
    .header-bento p {
        font-size: 1.05rem;
        color: #A0A0A0;
        margin-top: 0.6rem;
        margin-bottom: 0;
        max-width: 780px;
        line-height: 1.5;
    }
    .header-telemetry {
        display: flex;
        gap: 1.5rem;
        margin-top: 1.2rem;
        padding-top: 1rem;
        border-top: 1px solid #282828;
    }
    .telemetry-item {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #888888;
    }
    .telemetry-item span {
        color: #C85A32;
        margin-left: 0.35rem;
    }

    /* Asymmetric Bento Cards */
    .bento-card {
        background-color: #1A1A1A;
        border: 1px solid #2E2E2E;
        border-radius: 4px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .bento-card-highlight {
        background-color: #181818;
        border: 1px solid #3E3E3E;
        border-radius: 4px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .bento-card-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.82rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #888888;
        margin-bottom: 0.8rem;
    }

    /* Primary Accent Buttons (Burnt Rust #C85A32) */
    div.stButton > button[kind="primary"] {
        background-color: #C85A32 !important;
        color: #FFFFFF !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        font-size: 0.9rem !important;
        border: 1px solid #A84722 !important;
        border-radius: 4px !important;
        padding: 0.75rem 1.4rem !important;
        box-shadow: none !important;
        transition: background-color 0.15s ease !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #B54E29 !important;
        border-color: #C85A32 !important;
    }
    div.stButton > button:not([kind="primary"]) {
        background-color: #222222 !important;
        color: #E2E2E2 !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        border: 1px solid #333333 !important;
        border-radius: 4px !important;
        box-shadow: none !important;
        transition: all 0.15s ease !important;
    }
    div.stButton > button:not([kind="primary"]):hover {
        background-color: #2D2D2D !important;
        border-color: #4A4A4A !important;
        color: #FFFFFF !important;
    }

    /* Question Item Bento Box */
    .question-box {
        background-color: #1A1A1A;
        border: 1px solid #2E2E2E;
        border-radius: 4px;
        padding: 1.6rem;
        margin-bottom: 1.2rem;
    }
    .question-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.8rem;
    }
    .question-num {
        font-family: 'Playfair Display', serif;
        font-size: 1.35rem;
        font-weight: 700;
        color: #C85A32;
    }
    .question-body {
        font-size: 1.1rem;
        font-weight: 500;
        color: #F0F0F0;
        line-height: 1.6;
        margin-bottom: 1.2rem;
    }

    /* Status Tags (Strict Flat Industrial Styling) */
    .tag-active {
        background-color: #1A261D;
        color: #4ADE80;
        border: 1px solid #22543D;
        padding: 0.15rem 0.5rem;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        border-radius: 2px;
    }
    .tag-offline {
        background-color: #242424;
        color: #777777;
        border: 1px solid #333333;
        padding: 0.15rem 0.5rem;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        border-radius: 2px;
    }
    .tag-meta {
        background-color: #222222;
        color: #A3A3A3;
        border: 1px solid #333333;
        padding: 0.2rem 0.55rem;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        border-radius: 2px;
        display: inline-block;
        margin-right: 0.4rem;
    }

    /* Multiple-Choice Option Rows */
    .option-row-flat {
        background-color: #202020;
        border: 1px solid #2E2E2E;
        border-radius: 4px;
        padding: 0.85rem 1.1rem;
        margin-bottom: 0.5rem;
        color: #E5E5E5;
        font-size: 0.96rem;
        transition: border-color 0.15s ease;
    }
    .option-row-flat:hover {
        border-color: #C85A32;
        background-color: #252525;
    }

    /* Industrial Citation Box */
    .citation-box-industrial {
        background-color: #151515;
        border-left: 3px solid #C85A32;
        border-top: 1px solid #282828;
        border-right: 1px solid #282828;
        border-bottom: 1px solid #282828;
        padding: 1.1rem 1.3rem;
        border-radius: 2px;
        margin-top: 1rem;
        font-size: 0.88rem;
        color: #B5B5B5;
        line-height: 1.6;
    }
    .citation-title-tag {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        color: #C85A32;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.4rem;
        display: block;
    }

    /* Assessment Metric Box */
    .metric-panel {
        background-color: #1A1A1A;
        border: 1px solid #2E2E2E;
        border-radius: 4px;
        padding: 1.4rem;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .metric-value {
        font-family: 'Playfair Display', serif;
        font-size: 1.8rem;
        font-weight: 700;
        color: #F5F5F5;
    }

    /* Expanders Restyling */
    .streamlit-expanderHeader {
        background-color: #1E1E1E !important;
        border: 1px solid #2E2E2E !important;
        border-radius: 4px !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        color: #D4D4D4 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =====================================================================
# Session State Initialization
# =====================================================================


def init_session() -> None:
    """Initialize essential session state keys."""
    if "question_set" not in st.session_state:
        st.session_state.question_set = None
    if "show_raw_code" not in st.session_state:
        st.session_state.show_raw_code = False
    if "flashcard_idx" not in st.session_state:
        st.session_state.flashcard_idx = 0
    if "flashcard_show_answer" not in st.session_state:
        st.session_state.flashcard_show_answer = False
    if "quiz_answers" not in st.session_state:
        st.session_state.quiz_answers = {}
    if "quiz_submitted" not in st.session_state:
        st.session_state.quiz_submitted = False
    if "winning_provider" not in st.session_state:
        st.session_state.winning_provider = None
    if "execution_mode" not in st.session_state:
        st.session_state.execution_mode = "Divide & Conquer (Parallel)"
    if "current_topic" not in st.session_state:
        st.session_state.current_topic = ""
    if "contributions" not in st.session_state:
        st.session_state.contributions = []


# =====================================================================
# Export Helpers
# =====================================================================


def build_markdown_export(question_set: QuestionSet, topic: str) -> str:
    """Convert a QuestionSet into formatted Markdown text."""
    lines: List[str] = [
        f"# Study Practice: {topic}",
        "",
        f"> Grounded textbook practice extract.",
        "",
    ]
    if question_set.status_note:
        lines.extend([f"**Grounding Notice:** {question_set.status_note}", ""])

    for idx, q in enumerate(question_set.questions, 1):
        lines.append(f"### Question {idx} [{q.difficulty} | {q.question_type}]")
        lines.append("")
        lines.append(f"{q.question}")
        lines.append("")
        if q.options:
            for opt in q.options:
                lines.append(f"- {opt}")
            lines.append("")
        lines.extend(
            [
                f"#### Solution",
                f"{q.answer}",
                "",
                f"<details><summary><b>Citation</b></summary>",
                f"",
                f"- **Source Book:** {q.source_book}",
                f"- **Chapter:** {q.chapter}",
                f"- **Page:** {q.page_number}",
                f"</details>",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)


def build_anki_csv(question_set: QuestionSet) -> str:
    """Export questions and answers into Anki flashcard CSV format."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Front (Question)", "Back (Answer & Citation)", "Tags"])
    for q in question_set.questions:
        opts_html = "<br>" + "<br>".join(q.options) if q.options else ""
        front = f"{q.question}{opts_html}<br><br><small><i>[{q.difficulty} | {q.question_type}]</i></small>"
        back = (
            f"{q.answer}<br><hr>"
            f"<small><b>Source:</b> {q.source_book} (p. {q.page_number}, {q.chapter})</small>"
        )
        tags = f"study-assistant {q.difficulty.lower()} {q.question_type.lower()}"
        writer.writerow([front, back, tags])
    return output.getvalue()


# =====================================================================
# Sidebar: Engine Configuration & Local Storage
# =====================================================================


def render_sidebar() -> dict:
    """Render the sidebar with crisp industrial layout and direct plain-English copy."""
    st.sidebar.markdown(
        """
        <div style="padding: 0.5rem 0 1rem 0;">
            <div style="font-family:'Playfair Display',serif; font-size:1.35rem; font-weight:700; color:#F5F5F5;">Configuration</div>
            <div style="font-size:0.8rem; color:#888888; margin-top:0.2rem;">Multi-provider keys and textbook ingest</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Collapsible Provider Keys
    all_configs = []
    with st.sidebar.expander("Provider API Keys", expanded=False):
        for provider in SUPPORTED_PROVIDERS:
            cfg = _render_provider_key_section(provider)
            all_configs.append(cfg)
            st.markdown("<div style='margin-bottom:0.8rem;'></div>", unsafe_allow_html=True)

    armed_configs = [c for c in all_configs if c["is_armed"]]
    n_armed = len(armed_configs)

    # 2. Execution Strategy Selector
    st.sidebar.markdown(
        """
        <div style="font-family:'Space Grotesk',sans-serif; font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#888888; margin-top:1.2rem; margin-bottom:0.4rem;">
            Execution Strategy
        </div>
        """,
        unsafe_allow_html=True,
    )
    mode_options = [
        "Divide & Conquer (Parallel)",
        "Race Mode (Fastest LLM Wins)",
    ]
    selected_mode = st.sidebar.radio(
        "Parallel Strategy",
        options=mode_options,
        index=0,
        label_visibility="collapsed",
        help="Divide & Conquer splits total questions equally across providers. Race Mode runs the full query across all providers simultaneously.",
    )
    st.session_state.execution_mode = selected_mode

    # Strategy status summary
    if n_armed > 1:
        names = ", ".join(c['provider'] for c in armed_configs)
        st.sidebar.markdown(f"<div class='tag-active' style='display:block; padding:0.4rem 0.6rem;'>PARALLEL READY — {n_armed} PROVIDERS: {names}</div>", unsafe_allow_html=True)
    elif n_armed == 1:
        st.sidebar.markdown(f"<div class='tag-active' style='display:block; padding:0.4rem 0.6rem;'>ACTIVE PROVIDER: {armed_configs[0]['provider']}</div>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<div class='tag-offline' style='display:block; padding:0.4rem 0.6rem;'>NO KEYS CONFIGURED</div>", unsafe_allow_html=True)

    st.sidebar.markdown("<div style='font-size:0.75rem; color:#666666; margin-top:0.6rem;'>Embedding Engine: <b style='color:#A3A3A3;'>Local CPU (BAAI/bge-small-en-v1.5 • 384 dims)</b></div>", unsafe_allow_html=True)

    # 3. Local Textbooks Store
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="font-family:'Space Grotesk',sans-serif; font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#888888; margin-bottom:0.4rem;">
            Textbook Library
        </div>
        """,
        unsafe_allow_html=True,
    )

    status = get_index_status()
    pdf_count = status["pdf_count"]
    index_exists = status["index_exists"]
    vector_count = status["vector_count"]

    st.sidebar.markdown(
        f"""
        <div style="font-size:0.84rem; color:#A3A3A3; margin-bottom:0.8rem;">
            Indexed Passages: <b style="color:#F5F5F5;">{vector_count if index_exists else 0}</b> | Source Documents: <b style="color:#F5F5F5;">{pdf_count}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.sidebar.file_uploader(
        "Upload Textbook PDF",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        help="Upload course PDF textbooks directly into the local repository.",
    )
    if uploaded_files:
        for uf in uploaded_files:
            save_uploaded_pdf(uf)
        st.sidebar.success(f"Saved {len(uploaded_files)} PDF file(s).")
        st.rerun()

    if status["pdf_details"]:
        with st.sidebar.expander("Manage Source PDFs", expanded=False):
            for item in status["pdf_details"]:
                col_info, col_del = st.columns([3, 1])
                with col_info:
                    st.markdown(f"**{item['name']}**")
                    st.caption(f"{item['size_mb']} MB • {item['pages']} pages")
                with col_del:
                    if st.button("DEL", key=f"del_{item['name']}", help="Delete PDF from library"):
                        delete_textbook_pdf(item["name"])
                        st.rerun()

    col_act1, col_act2 = st.sidebar.columns(2)
    with col_act1:
        if st.button("REBUILD INDEX", help="Re-index all documents locally on CPU", use_container_width=True):
            with st.spinner("Indexing documents locally on CPU (384-dim BAAI/bge-small-en-v1.5)..."):
                try:
                    load_or_build_index(force_rebuild=True)
                    st.sidebar.success("Index ready.")
                    st.rerun()
                except Exception as rb_err:
                    st.sidebar.error(f"Failed: {rb_err}")
    with col_act2:
        if st.button("PURGE INDEX", help="Delete ChromaDB cache", use_container_width=True):
            purge_index_storage()
            st.sidebar.info("Cache cleared.")
            st.rerun()

    return {
        "armed_configs": armed_configs,
        "execution_mode": selected_mode,
    }


# =====================================================================
# Main Header & Quick Presets
# =====================================================================


def render_header(config: dict[str, Any]) -> None:
    """Render the editorial top banner."""
    armed = config.get("armed_configs", [])
    count = len(armed)

    if count > 1:
        prov_summary = ", ".join(c['provider'] for c in armed)
        mode_label = config.get("execution_mode", "Divide & Conquer")
        telemetry_html = f"""
        <div class="telemetry-item">Providers Active: <span>{count} ({prov_summary})</span></div>
        <div class="telemetry-item">Strategy: <span>{mode_label}</span></div>
        """
    elif count == 1:
        p = armed[0]
        telemetry_html = f"""
        <div class="telemetry-item">Active LLM: <span>{p['provider']}</span></div>
        <div class="telemetry-item">Model: <span>{p.get('model') or 'Default'}</span></div>
        """
    else:
        telemetry_html = """
        <div class="telemetry-item" style="color:#C85A32;">Status: <span>No API Key Configured (Open Configuration Sidebar)</span></div>
        """

    st.markdown(
        f"""
        <div class="header-bento">
            <h1>Study Assistant</h1>
            <p>Generate verifiable practice questions strictly grounded in indexed course textbooks with page citations.</p>
            <div class="header-telemetry">
                {telemetry_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_quick_presets() -> None:
    """Render topic query presets."""
    st.markdown(
        """
        <div style="font-family:'Space Grotesk',sans-serif; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#888888; margin-bottom:0.5rem;">
            Quick Topic Selectors
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    presets = [
        "OS Deadlocks & Bankers Algorithm",
        "Binary Search Trees & Balancing",
        "Mitochondrial ATP Synthesis",
        "Keynesian Macroeconomics",
    ]
    for idx, (col, topic_name) in enumerate(zip(cols, presets)):
        with col:
            if st.button(topic_name, key=f"preset_{idx}", use_container_width=True):
                st.session_state.selected_preset = topic_name
                st.rerun()


# =====================================================================
# Question & Study Mode Renderers
# =====================================================================


def render_practice_card(idx: int, item: QuestionItem) -> None:
    """Render a single question item in an industrial bento box with separate options and solution expander."""
    options_html = ""
    if item.options:
        options_html = "".join(f"<div class='option-row-flat'>{opt}</div>" for opt in item.options)

    st.markdown(
        f"""
        <div class="question-box">
            <div class="question-header">
                <span class="question-num">0{idx}.</span>
                <div>
                    <span class="tag-meta">{item.difficulty}</span>
                    <span class="tag-meta">{item.question_type}</span>
                </div>
            </div>
            <div class="question-body">{item.question}</div>
            {options_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Reveal Ground-Truth Solution & Textbook Citation", expanded=False):
        st.markdown(
            f"""
            <div style="font-family:'Space Grotesk',sans-serif; font-size:0.82rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#C85A32; margin-bottom:0.5rem;">
                Ground-Truth Solution
            </div>
            <div style="font-size:1rem; line-height:1.6; color:#E0E0E0; margin-bottom:1rem;">
                {item.answer}
            </div>
            <div class="citation-box-industrial">
                <span class="citation-title-tag">VERIFIED TEXTBOOK CITATION</span>
                <div><b>Source Document:</b> {item.source_book}</div>
                <div><b>Chapter / Module:</b> {item.chapter}</div>
                <div><b>Page Citation:</b> Page {item.page_number}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-bottom: 1.2rem;'></div>", unsafe_allow_html=True)


def _extract_correct_option_letter(answer: str) -> Optional[str]:
    """Helper to detect correct option letter (A, B, C, D) from the LLM answer."""
    match = re.search(r"\b([A-D])\b", answer.strip()[:60])
    if match:
        return match.group(1).upper()
    return None


def render_interactive_quiz(question_set: QuestionSet) -> None:
    """Render questions as an interactive assessment with radio selection, immediate scoring, and citation display."""
    st.markdown(
        """
        <div style="margin-bottom:1rem;">
            <div style="font-family:'Playfair Display',serif; font-size:1.5rem; font-weight:700;">Interactive Assessment</div>
            <div style="font-size:0.88rem; color:#888888;">Select your answers and submit for verified grading.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    total_mcqs = 0
    correct_count = 0

    for idx, item in enumerate(question_set.questions, 1):
        st.markdown(
            f"""
            <div class="question-box" style="padding: 1.2rem 1.4rem; margin-bottom: 0.6rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                    <span style="font-family:'Space Grotesk',sans-serif; font-weight:700; color:#C85A32; font-size:0.85rem;">ITEM 0{idx}</span>
                    <div>
                        <span class="tag-meta">{item.difficulty}</span>
                        <span class="tag-meta">{item.question_type}</span>
                    </div>
                </div>
                <div style="font-size: 1.05rem; font-weight: 600; color: #F0F0F0; line-height: 1.5;">
                    {item.question}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if item.options:
            total_mcqs += 1
            user_choice = st.radio(
                f"Item {idx} Choice",
                options=item.options,
                key=f"quiz_opt_{idx}",
                index=None,
                label_visibility="collapsed",
            )
            st.session_state.quiz_answers[idx] = user_choice

            if st.session_state.quiz_submitted:
                correct_letter = _extract_correct_option_letter(item.answer)
                user_selected_letter = None
                if user_choice:
                    opt_match = re.match(r"^([A-D])\)", user_choice.strip())
                    if opt_match:
                        user_selected_letter = opt_match.group(1).upper()

                if correct_letter and user_selected_letter:
                    if user_selected_letter == correct_letter:
                        correct_count += 1
                        st.markdown(f"<div class='tag-active' style='display:inline-block; margin-top:0.3rem;'>CORRECT — {user_choice}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='tag-offline' style='display:inline-block; color:#EF4444; border-color:#991B1B; margin-top:0.3rem;'>INCORRECT — Selected: {user_choice}</div>", unsafe_allow_html=True)
        else:
            user_answer = st.text_area(
                f"Item {idx} Written Response",
                key=f"quiz_ans_{idx}",
                height=90,
                placeholder="Type your theoretical analysis or short-answer response here...",
                label_visibility="collapsed",
            )
            st.session_state.quiz_answers[idx] = user_answer

            if st.session_state.quiz_submitted and user_answer and user_answer.strip():
                st.markdown(
                    f"""
                    <div style="background:#1A1A1A; border:1px solid #2E2E2E; border-left:3px solid #C85A32; border-radius:3px; padding:0.8rem 1rem; margin-top:0.4rem; margin-bottom:0.6rem;">
                        <span style="font-family:'Space Grotesk',sans-serif; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#888888;">Your Submitted Response</span>
                        <div style="color:#F5F5F5; font-size:0.92rem; margin-top:0.3rem; line-height:1.5;">{user_answer}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if st.session_state.quiz_submitted:
            with st.expander(f"Ground-Truth Solution for Item {idx}", expanded=True):
                st.markdown(f"**Solution:** {item.answer}")
                st.markdown(
                    f"""
                    <div class="citation-box-industrial">
                        <span class="citation-title-tag">SOURCE CITATION</span>
                        <div><b>Document:</b> {item.source_book} | <b>Section:</b> {item.chapter} | <b>Page:</b> {item.page_number}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='margin-bottom: 1.2rem;'></div>", unsafe_allow_html=True)

    if st.session_state.quiz_submitted:
        if total_mcqs > 0:
            pct = int((correct_count / total_mcqs) * 100)
            st.markdown(
                f"""
                <div class="metric-panel">
                    <div>
                        <div style="font-family:'Space Grotesk',sans-serif; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#888888;">Assessment Score</div>
                        <div class="metric-value">{correct_count} / {total_mcqs} ({pct}%)</div>
                    </div>
                    <div class="tag-meta" style="font-size:0.9rem; padding:0.4rem 0.8rem;">
                        {'PASSED' if pct >= 60 else 'NEEDS REVIEW'}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="metric-panel">
                    <div>
                        <div style="font-family:'Space Grotesk',sans-serif; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#888888;">Assessment Mode</div>
                        <div class="metric-value" style="font-size:1.15rem; color:#F5F5F5;">Conceptual Self-Evaluation Complete</div>
                    </div>
                    <div class="tag-meta" style="font-size:0.85rem; padding:0.4rem 0.8rem;">
                        VERIFIED CITATIONS REVEALED
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("SUBMIT ASSESSMENT", type="primary", use_container_width=True):
            st.session_state.quiz_submitted = True
            st.rerun()
    with col2:
        if st.button("RESET RESPONSES", use_container_width=False):
            st.session_state.quiz_submitted = False
            st.session_state.quiz_answers = {}
            st.rerun()


def render_flashcards(question_set: QuestionSet) -> None:
    """Render practice questions in an editorial flip-flashcard card."""
    total = len(question_set.questions)
    if total == 0:
        return

    current_idx = min(st.session_state.flashcard_idx, total - 1)
    current_q = question_set.questions[current_idx]

    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
            <div style="font-family:'Playfair Display',serif; font-size:1.5rem; font-weight:700;">Flashcard Review</div>
            <span class="tag-meta">CARD 0{current_idx + 1} OF 0{total}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    card_container = st.container()
    with card_container:
        if not st.session_state.flashcard_show_answer:
            opts_display = ""
            if current_q.options:
                opts_display = "<div style='margin-top: 1.2rem; text-align: left; width: 90%;'>" + "".join(
                    f"<div class='option-row-flat'>{opt}</div>" for opt in current_q.options
                ) + "</div>"

            st.markdown(
                f"""
                <div class="question-box" style="min-height:240px; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; padding:2.5rem;">
                    <div>
                        <span class="tag-meta">{current_q.difficulty}</span>
                        <span class="tag-meta">{current_q.question_type}</span>
                    </div>
                    <div style="font-family:'Playfair Display',serif; font-size:1.45rem; font-weight:700; color:#F5F5F5; margin-top:1.2rem; max-width:850px; line-height:1.4;">
                        {current_q.question}
                    </div>
                    {opts_display}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="question-box" style="min-height:240px; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; padding:2.5rem; border-color:#C85A32;">
                    <span class="tag-active">GROUND-TRUTH SOLUTION</span>
                    <div style="font-size:1.15rem; color:#F5F5F5; margin-top:1.2rem; max-width:850px; line-height:1.6; text-align:left;">
                        {current_q.answer}
                    </div>
                    <div style="font-size:0.85rem; color:#888888; margin-top:1.2rem;">
                        <b>Citation:</b> {current_q.source_book} (p. {current_q.page_number}, {current_q.chapter})
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    col_nav1, col_nav2, col_nav3 = st.columns([1, 1, 1])
    with col_nav1:
        if st.button("PREVIOUS CARD", disabled=(current_idx == 0), use_container_width=True):
            st.session_state.flashcard_idx = max(0, current_idx - 1)
            st.session_state.flashcard_show_answer = False
            st.rerun()
    with col_nav2:
        btn_lbl = "SHOW QUESTION" if st.session_state.flashcard_show_answer else "REVEAL ANSWER"
        if st.button(btn_lbl, use_container_width=True, type="primary"):
            st.session_state.flashcard_show_answer = not st.session_state.flashcard_show_answer
            st.rerun()
    with col_nav3:
        if st.button("NEXT CARD", disabled=(current_idx >= total - 1), use_container_width=True):
            st.session_state.flashcard_idx = min(total - 1, current_idx + 1)
            st.session_state.flashcard_show_answer = False
            st.rerun()


# =====================================================================
# Main Application Entry Point (Asymmetric Bento Grid)
# =====================================================================


def main() -> None:
    """Main execution flow for Study Assistant application."""
    init_session()

    # Render Sidebar Configuration
    config = render_sidebar()

    # Render Main Editorial Header
    render_header(config)

    # Topic Presets
    render_quick_presets()
    default_topic_val = st.session_state.pop("selected_preset", "")

    # Main Bento Query Interface (Asymmetric 2:1 ratio)
    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
    
    col_main_query, col_main_params = st.columns([2, 1])

    with col_main_query:
        st.markdown(
            """
            <div class="bento-card">
                <div class="bento-card-title">Study Target & Concept</div>
            """,
            unsafe_allow_html=True,
        )
        topic_input = st.text_input(
            "Study Topic",
            value=default_topic_val,
            placeholder="e.g., Virtual Memory Paging, Dijkstra Shortest Path, Keynesian Macroeconomics",
            label_visibility="collapsed",
            help="Enter the specific topic or theory to extract and practice from course textbooks.",
        )
        generate_btn = st.button(
            "GENERATE PRACTICE QUESTIONS",
            type="primary",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_main_params:
        st.markdown(
            """
            <div class="bento-card">
                <div class="bento-card-title">Parameters</div>
            """,
            unsafe_allow_html=True,
        )
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            difficulty = st.selectbox(
                "Difficulty",
                options=ALLOWED_DIFFICULTIES,
                index=1,
            )
        with col_p2:
            question_type = st.selectbox(
                "Type",
                options=ALLOWED_QUESTION_TYPES,
                index=0,
            )
        quantity = st.slider(
            "Question Quantity",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Empty library notification
    status = get_index_status()
    if status["pdf_count"] == 0 and not status["index_exists"]:
        st.markdown(
            """
            <div class="bento-card" style="border-left:3px solid #C85A32;">
                <div style="font-family:'Playfair Display',serif; font-size:1.25rem; font-weight:700; color:#F5F5F5;">Getting Started</div>
                <div style="color:#A0A0A0; font-size:0.9rem; margin-top:0.4rem; line-height:1.6;">
                    1. Upload course PDF textbooks using the <b>Textbook Library</b> in the sidebar.<br>
                    2. Add your provider API keys under <b>Provider API Keys</b>.<br>
                    3. Enter your study concept above and click <b>GENERATE PRACTICE QUESTIONS</b>.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Generation Execution Flow
    if generate_btn:
        armed_configs = config.get("armed_configs", [])
        if not armed_configs:
            st.error("API Key required. Open the sidebar Configuration to add a key.")
            return

        if not topic_input.strip():
            st.warning("Please specify a study topic before generating questions.")
            return

        mode = config.get("execution_mode", "Divide & Conquer (Parallel)")

        if len(armed_configs) == 1:
            single_cfg = armed_configs[0]
            with st.spinner(f"Ingesting textbook nodes and synthesizing with {single_cfg['provider']}..."):
                try:
                    question_set = generate_questions(
                        topic=topic_input.strip(),
                        difficulty=difficulty,
                        question_type=question_type,
                        quantity=quantity,
                        provider=single_cfg["provider"],
                        llm_keys=single_cfg["keys"],
                        llm_model=single_cfg.get("model"),
                        custom_base_url=single_cfg.get("custom_base_url"),
                    )
                    st.session_state.question_set = question_set
                    st.session_state.winning_provider = single_cfg["provider"]
                    st.session_state.contributions = []
                    st.session_state.current_topic = topic_input.strip()
                    st.session_state.flashcard_idx = 0
                    st.session_state.flashcard_show_answer = False
                    st.session_state.quiz_submitted = False
                    st.session_state.quiz_answers = {}

                except NoTextbooksFoundError:
                    st.warning(f"No PDF textbooks found in `{TEXTBOOKS_DIR}`. Upload PDFs in the sidebar.")
                except APIKeyMissingError as key_err:
                    st.error(f"API Key Required: {key_err}")
                except RAGGenerationError as gen_err:
                    st.error(f"Generation Error: {gen_err}")
                except ValueError as val_err:
                    st.warning(f"Validation Error: {val_err}")
                except RAGError as rag_err:
                    st.error(f"RAG Error: {rag_err}")
                except Exception as unexp_err:
                    logger.exception("Error during single provider generation.")
                    st.error(f"Generation Error: {unexp_err}")

        elif "Divide & Conquer" in mode:
            with st.spinner(f"Partitioning {quantity} questions across {len(armed_configs)} providers in parallel..."):
                try:
                    question_set, contribs = generate_questions_divide_and_conquer(
                        topic=topic_input.strip(),
                        difficulty=difficulty,
                        question_type=question_type,
                        total_quantity=quantity,
                        provider_configs=armed_configs,
                    )
                    st.session_state.question_set = question_set
                    st.session_state.contributions = contribs
                    st.session_state.winning_provider = None
                    st.session_state.current_topic = topic_input.strip()
                    st.session_state.flashcard_idx = 0
                    st.session_state.flashcard_show_answer = False
                    st.session_state.quiz_submitted = False
                    st.session_state.quiz_answers = {}

                except NoTextbooksFoundError:
                    st.warning(f"No PDF textbooks found in `{TEXTBOOKS_DIR}`. Upload PDFs in the sidebar.")
                except APIKeyMissingError as key_err:
                    st.error(f"API Key Error: {key_err}")
                except RAGGenerationError as gen_err:
                    st.error(f"Generation Error: {gen_err}")
                except Exception as unexp_err:
                    logger.exception("Error during divide & conquer generation.")
                    st.error(f"Generation Error: {unexp_err}")

        else:
            with st.spinner(f"Racing {len(armed_configs)} providers in parallel..."):
                try:
                    question_set, winner = generate_questions_parallel(
                        topic=topic_input.strip(),
                        difficulty=difficulty,
                        question_type=question_type,
                        quantity=quantity,
                        provider_configs=armed_configs,
                    )
                    st.session_state.question_set = question_set
                    st.session_state.winning_provider = winner
                    st.session_state.contributions = []
                    st.session_state.current_topic = topic_input.strip()
                    st.session_state.flashcard_idx = 0
                    st.session_state.flashcard_show_answer = False
                    st.session_state.quiz_submitted = False
                    st.session_state.quiz_answers = {}

                except NoTextbooksFoundError:
                    st.warning(f"No PDF textbooks found in `{TEXTBOOKS_DIR}`. Upload PDFs in the sidebar.")
                except APIKeyMissingError as key_err:
                    st.error(f"API Key Error: {key_err}")
                except RAGGenerationError as gen_err:
                    st.error(f"Generation Error: {gen_err}")
                except Exception as unexp_err:
                    logger.exception("Error during parallel race generation.")
                    st.error(f"Generation Error: {unexp_err}")

    # Output Results
    if st.session_state.question_set is not None:
        q_set: QuestionSet = st.session_state.question_set

        if not q_set.questions:
            st.info(f"No questions generated: {q_set.status_note or 'No matching textbook passages found.'}")
        else:
            # Parallel telemetry report
            if st.session_state.contributions:
                c_badges = " | ".join(
                    f"<b>{c['provider']}</b>: {c['count']} items ({c['status']})"
                    for c in st.session_state.contributions
                )
                st.markdown(
                    f"""
                    <div class="bento-card" style="border-left:3px solid #C85A32; padding:0.9rem 1.2rem;">
                        <span style="font-family:'Space Grotesk',sans-serif; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#C85A32;">Parallel Synthesis Summary</span>
                        <div style="font-size:0.88rem; color:#D4D4D4; margin-top:0.2rem;">{c_badges}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            elif st.session_state.winning_provider:
                st.markdown(
                    f"""
                    <div class="bento-card" style="border-left:3px solid #C85A32; padding:0.9rem 1.2rem;">
                        <span style="font-family:'Space Grotesk',sans-serif; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#C85A32;">Race Result</span>
                        <div style="font-size:0.88rem; color:#D4D4D4; margin-top:0.2rem;">Fastest response delivered by: <b>{st.session_state.winning_provider}</b></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

            # Study Mode Tabs
            tab_practice, tab_quiz, tab_flashcards = st.tabs(
                ["Practice Cards", "Interactive Assessment", "Flashcard Review"]
            )

            with tab_practice:
                st.markdown(
                    f"""
                    <div style="margin-bottom:1.2rem;">
                        <div style="font-family:'Playfair Display',serif; font-size:1.5rem; font-weight:700;">Extracted Practice Items ({len(q_set.questions)} questions)</div>
                        <div style="font-size:0.88rem; color:#888888;">Grounded directly in local textbook passages.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if q_set.status_note:
                    st.caption(f"Grounding note: {q_set.status_note}")

                for idx, item in enumerate(q_set.questions, 1):
                    render_practice_card(idx, item)

            with tab_quiz:
                render_interactive_quiz(q_set)

            with tab_flashcards:
                render_flashcards(q_set)

            # Export Panel
            st.markdown("---")
            st.markdown(
                """
                <div style="font-family:'Space Grotesk',sans-serif; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#888888; margin-bottom:0.8rem;">
                    Export & Archival
                </div>
                """,
                unsafe_allow_html=True,
            )
            col_exp1, col_exp2, col_exp3 = st.columns(3)

            current_topic_title = getattr(st.session_state, "current_topic", "study_session")
            clean_filename_base = f"study_questions_{current_topic_title.replace(' ', '_').lower()}"

            with col_exp1:
                md_data = build_markdown_export(q_set, current_topic_title)
                st.download_button(
                    label="EXPORT MARKDOWN (.MD)",
                    data=md_data,
                    file_name=f"{clean_filename_base}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            with col_exp2:
                anki_data = build_anki_csv(q_set)
                st.download_button(
                    label="EXPORT ANKI FLASHCARDS (.CSV)",
                    data=anki_data,
                    file_name=f"{clean_filename_base}_anki.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            with col_exp3:
                if st.button("VIEW RAW TEXT", use_container_width=True):
                    st.session_state.show_raw_code = not st.session_state.show_raw_code

            if st.session_state.show_raw_code:
                st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)
                st.code(md_data, language="markdown")


if __name__ == "__main__":
    main()
