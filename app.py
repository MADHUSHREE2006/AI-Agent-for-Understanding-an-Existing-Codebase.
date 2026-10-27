"""Streamlit web frontend for the Codebase Understanding Agent.

Run with:

    python -m streamlit run app.py

The UI reuses the existing agent core, LLM client, and report generator — no
new agent logic lives here. Highlights of this version:

* Polished custom theme (gradient header, glass cards, custom timeline).
* A workflow phase banner that lights up the agent's current phase as it runs.
* A live vertical-timeline ReAct trace (Thought → Action → Observation) that
  grows step by step via the agent's ``on_step`` callback.
* Four result tabs: rendered report, full trace, an interactive citation table,
  and the agent's final answer — plus a one-click report download.
* Two bundled sample projects pre-loaded for instant demos.
"""

from __future__ import annotations

import html
import os
import time
from html import escape

import pandas as pd
import streamlit as st

from agent import CodebaseAgent
from config import Config, get_config
from llm import LLMClient, LLMError
from output.report_generator import generate_report
from tools.code_parser import parse_file_structure, extract_business_rule_candidates
from tools.dependency_mapper import map_dependencies
from tools.file_explorer import find_files

# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = {
    "📚 Library Management System": os.path.join(HERE, "tests", "sample_project"),
    "🎓 Student Grading System":    os.path.join(HERE, "tests", "sample_grading"),
}

TOOL_ICONS = {
    "get_directory_tree":  "🌳",
    "find_files":          "🔍",
    "read_file":           "📄",
    "parse_file_structure":"🔬",
    "map_dependencies":    "🕸️",
    "search_content":      "🔎",
    "list_directory":      "📁",
}

# The five phases of the workflow; the banner lights up the active one.
PHASES = [
    ("Explore",          "🌳", {"get_directory_tree", "find_files", "list_directory"}),
    ("Understand",       "🔬", {"read_file", "parse_file_structure"}),
    ("Connect",          "🕸️", {"map_dependencies"}),
    ("Find Rules",       "🔎", {"search_content"}),
    ("Verify & Explain", "✅", {None}),  # final-answer step
]


def phase_for(action):
    for name, _icon, tools in PHASES:
        if action in tools:
            return name
    return None


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def step_title(step) -> str:
    icon = TOOL_ICONS.get(step.action, "🔧") if step.action else "✅"
    return f"{icon} {step.action or 'Final Answer'}"


def apply_overrides(cfg: Config, backend, model, host, base_url, api_key, max_iter) -> Config:
    cfg.backend = backend
    if backend == "ollama":
        if model:
            cfg.ollama_model = model
        if host:
            cfg.ollama_host = host
    elif backend == "openai":
        if model:
            cfg.openai_model = model
        if base_url:
            cfg.openai_base_url = base_url
        if api_key:
            cfg.openai_api_key = api_key
    cfg.max_iterations = max_iter
    return cfg


def quick_project_stats(target: str):
    """Static analysis stats for the snapshot card (no LLM calls)."""
    deps = map_dependencies(target)
    files = deps.get("files", [])
    n_cls = sum(len(parse_file_structure(os.path.join(target, f)).get("classes", [])) for f in files)
    n_fn = sum(len(parse_file_structure(os.path.join(target, f)).get("functions", [])) for f in files)
    n_rules = len(extract_business_rule_candidates(target))
    return len(files), n_cls, n_fn, n_rules


def render_phase_banner(active_phase=None, done=False):
    """Render the 5-phase workflow banner as styled HTML."""
    chips = []
    for name, icon, _ in PHASES:
        state = "done" if done else ("active" if name == active_phase else "idle")
        chips.append(
            f'<div class="phase-chip phase-{state}">'
            f'<span class="phase-ic">{icon}</span>'
            f'<span class="phase-nm">{name}</span>'
            f'</div>'
        )
    arrows = '<span class="phase-arrow">›</span>' * 5
    return (
        '<div class="phase-banner">'
        + '<span class="phase-arrow">›</span>'.join(chips)
        + '</div>'
    )


def render_timeline(steps_html: str) -> str:
    return f'<div class="timeline">{steps_html}</div>'


def step_to_html(step) -> str:
    """One timeline node as HTML."""
    cls = "t-step t-err" if step.error else "t-step"
    title = escape(step_title(step))
    thought = escape(step.thought) if step.thought else ""
    obs_raw = step.observation if step.observation and step.observation not in (
        "(pending)", "Final Answer produced."
    ) else ""
    obs = escape(obs_raw)
    if len(obs) > 600:
        obs = obs[:600] + "\n…"
    thought_html = f'<div class="t-thought">💭 {thought}</div>' if thought else ""
    obs_html = (
        f'<pre class="t-obs">{"⚠️ " if step.error else ""}{obs}</pre>'
        if obs else ""
    )
    return (
        f'<div class="{cls}">'
        f'<div class="t-circle">{step.iteration}</div>'
        f'<div class="t-card">'
        f'<div class="t-title">{title}</div>'
        f'{thought_html}{obs_html}'
        f'</div></div>'
    )


# -----------------------------------------------------------------------
# Page setup
# -----------------------------------------------------------------------
st.set_page_config(
    page_title="Codebase Understanding Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Theme CSS --------------------------------------------------------
st.markdown("""
<style>
:root { --accent:#6c5ce7; --accent2:#00cec9; --ok:#00b894; --warn:#fdcb6e; --err:#e17055; }

/* Header gradient banner */
.hero {
  background: linear-gradient(135deg,#6c5ce7 0%,#a29bfe 50%,#00cec9 100%);
  padding: 22px 28px; border-radius: 16px; color:#fff; margin-bottom: 18px;
}
.hero h1 { color:#fff; font-size:1.9rem; margin:0; font-weight:800; }
.hero p { color:rgba(255,255,255,.92); margin:6px 0 0; font-size:1.02rem; }

/* Glass card */
.glass {
  background: rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12);
  border-radius:14px; padding:16px 18px; backdrop-filter: blur(6px);
}

/* Phase banner */
.phase-banner { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:6px 0 14px; }
.phase-chip {
  display:inline-flex; align-items:center; gap:7px; padding:8px 14px; border-radius:999px;
  font-size:.86rem; font-weight:600; transition:all .2s;
  background:#f1f3f9; color:#5b647e; border:2px solid transparent;
}
.phase-chip .phase-ic { font-size:1.05rem; }
.phase-idle { background:#eef0f5; color:#8a93a8; }
.phase-active { background:#6c5ce7; color:#fff; box-shadow:0 4px 14px rgba(108,92,231,.4); transform:scale(1.05); }
.phase-done { background:#e6f9f3; color:#00b894; border-color:#00b894; }

/* Metric cards */
.metric-card {
  background:#fff; border-radius:12px; padding:14px 16px; text-align:center;
  box-shadow:0 2px 10px rgba(0,0,0,.06); border:1px solid #eceef3;
}
.metric-card .mc-val { font-size:1.7rem; font-weight:800; color:#2d3561; }
.metric-card .mc-lab { font-size:.78rem; color:#8a93a8; text-transform:uppercase; letter-spacing:.04em; }
.metric-card .mc-ic { font-size:1.4rem; margin-bottom:4px; }

/* Timeline */
.timeline { position:relative; padding-left:8px; }
.t-step { position:relative; padding-left:42px; margin-bottom:14px; }
.t-step::before {
  content:""; position:absolute; left:18px; top:34px; bottom:-14px; width:2px;
  background:linear-gradient(#6c5ce7,#a29bfe); opacity:.4;
}
.t-step:last-child::before { display:none; }
.t-circle {
  position:absolute; left:0; top:2px; width:34px; height:34px; border-radius:50%;
  background:#6c5ce7; color:#fff; display:flex; align-items:center; justify-content:center;
  font-weight:700; font-size:.95rem; box-shadow:0 2px 8px rgba(108,92,231,.4);
}
.t-err .t-circle { background:var(--err); }
.t-card { background:#fff; border-radius:10px; padding:10px 14px; border:1px solid #eceef3; box-shadow:0 1px 4px rgba(0,0,0,.05); }
.t-err .t-card { border-color:#f5c6cb; background:#fff5f5; }
.t-title { font-weight:700; color:#2d3561; font-size:.95rem; }
.t-thought { color:#6b7280; font-size:.85rem; margin-top:4px; font-style:italic; }
.t-obs { background:#f7f8fb; border-radius:6px; padding:8px; margin-top:8px; font-size:.78rem;
  white-space:pre-wrap; max-height:180px; overflow:auto; color:#3a4256; }
.t-err .t-obs { background:#fdeaea; }

/* Tool legend */
.legend { display:flex; flex-wrap:wrap; gap:8px; }
.legend span { background:#f1f3f9; padding:4px 10px; border-radius:8px; font-size:.8rem; }

/* Footer */
.app-footer { text-align:center; color:#9aa1b1; font-size:.8rem; margin-top:28px; padding-top:14px; border-top:1px solid #eceef3; }

/* tighter section spacing */
section[data-testid="stSidebar"] .stMarkdown p { font-size:.88rem; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🤖 Codebase Agent")
    st.caption("AI-powered code explorer & explainer")
    st.divider()

    st.markdown("#### ⚙️ Backend")
    backend = st.selectbox(
        "LLM backend", ["simulate", "ollama", "openai"],
        help="simulate = no model | ollama = local LLM | openai = hosted API",
    )
    model = host = base_url = api_key = ""
    if backend == "ollama":
        model = st.text_input("Model", value="qwen2.5-coder:7b")
        host  = st.text_input("Host", value="http://localhost:11434")
    elif backend == "openai":
        model    = st.text_input("Model", value="gpt-4o-mini")
        base_url = st.text_input("Base URL", value="https://api.openai.com/v1")
        api_key  = st.text_input("API key", type="password")

    max_iter = st.slider("Max steps", 3, 20, 12)
    st.divider()

    cfg_test = apply_overrides(get_config(), backend, model, host, base_url, api_key, max_iter)
    if LLMClient(cfg_test).is_available():
        st.success(f"✅ {backend} ready")
    else:
        st.warning(f"⚠️ {backend} unavailable → simulate")
    st.divider()

    with st.expander("❓ How it works"):
        st.markdown("""
The agent runs a **ReAct loop**: it *reasons*, then *acts* (calls a tool),
then *observes* the result — repeating until it understands the codebase.

**5 phases:**
1. 🌳 **Explore** — directory tree, find files
2. 🔬 **Understand** — read & parse structure (AST)
3. 🕸️ **Connect** — map import dependencies
4. 🔎 **Find Rules** — search for validations/conditions
5. ✅ **Verify & Explain** — re-check, then answer with `file:line` citations

Every citation is **verified against the real source** before the report is
shown — so claims are grounded, not hallucinated.
""")

    st.divider()
    st.caption("💡 `simulate` runs the full workflow with no model download.")

# -----------------------------------------------------------------------
# Hero header
# -----------------------------------------------------------------------
st.markdown("""
<div class="hero">
  <h1>🤖 Codebase Understanding Agent</h1>
  <p>Drop in any Python project. The agent explores it, maps the structure &amp;
  dependencies, extracts the business rules, and explains it with citations
  linked to the exact <code>file:line</code>.</p>
</div>
""", unsafe_allow_html=True)

# Phase banner (idle state until run)
st.markdown(render_phase_banner(), unsafe_allow_html=True)

# Tool legend
with st.expander("🧰 Available tools"):
    legend = " ".join(
        f"<span>{ic} {nm}</span>" for nm, ic in TOOL_ICONS.items()
    )
    st.markdown(f'<div class="legend">{legend}</div>', unsafe_allow_html=True)

st.divider()

# -----------------------------------------------------------------------
# Target selection
# -----------------------------------------------------------------------
col_path, col_sample = st.columns([3, 2])
with col_path:
    st.markdown("##### 📂 Project to analyse")
    target_input = st.text_input(
        "Path", value=SAMPLES["📚 Library Management System"],
        label_visibility="collapsed", placeholder="C:/Users/you/my_project",
    )
with col_sample:
    st.markdown("##### ⚡ Quick sample")
    sel = st.selectbox("sample", list(SAMPLES.keys()), label_visibility="collapsed")
    if st.button("Load sample", use_container_width=True):
        st.session_state["last_target"] = SAMPLES[sel]
        st.rerun()

target = os.path.abspath(st.session_state.get("last_target", target_input))
valid = os.path.isdir(target)
if not valid:
    st.error(f"❌ Not a valid directory: `{target}`")

# -----------------------------------------------------------------------
# Project snapshot
# -----------------------------------------------------------------------
if valid:
    st.markdown("##### 📊 Project snapshot")
    with st.spinner("Scanning project…"):
        n_files, n_cls, n_fn, n_rules = quick_project_stats(target)
    sc = st.columns(4)
    for col, (ic, val, lab) in zip(sc, [
        ("🐍", n_files, "Python files"),
        ("🏛️", n_cls, "Classes"),
        ("⚙️", n_fn, "Functions"),
        ("📜", n_rules, "Rule candidates"),
    ]):
        col.markdown(
            f'<div class="metric-card"><div class="mc-ic">{ic}</div>'
            f'<div class="mc-val">{val}</div><div class="mc-lab">{lab}</div></div>',
            unsafe_allow_html=True,
        )

st.divider()
run_btn = st.button("🚀 Run Agent", type="primary", disabled=not valid,
                    use_container_width=True)

# -----------------------------------------------------------------------
# Execution
# -----------------------------------------------------------------------
if run_btn and valid:
    cfg = apply_overrides(get_config(), backend, model, host, base_url, api_key, max_iter)
    llm = LLMClient(cfg)
    if cfg.backend != "simulate" and not llm.is_available():
        st.warning(f"⚠️ {cfg.backend} not available — falling back to **simulate**.")
        cfg.backend = "simulate"
        llm = LLMClient(cfg)

    project_name = os.path.basename(target)

    st.markdown("##### 🔄 Live Agentic Trace")
    st.caption("Watch the agent reason and use tools in real time.")

    phase_ph = st.empty()            # phase banner placeholder
    progress = st.progress(0.0, text="Starting…")
    trace_ph = st.empty()            # timeline placeholder (redrawn each step)

    all_steps: list = []
    current_phase = {"name": None}
    timeline_html: list = []

    def on_step(step):
        all_steps.append(step)
        ph = phase_for(step.action)
        if ph:
            current_phase["name"] = ph
        # update phase banner
        phase_ph.markdown(render_phase_banner(current_phase["name"]), unsafe_allow_html=True)
        # update progress
        frac = min(len(all_steps) / cfg.max_iterations, 0.99)
        progress.progress(frac, text=f"Step {step.iteration} — {step_title(step)}")
        # redraw full timeline
        timeline_html.append(step_to_html(step))
        trace_ph.markdown(
            render_timeline("".join(timeline_html)), unsafe_allow_html=True
        )

    agent = CodebaseAgent(cfg, target, llm)
    t0 = time.time()
    try:
        with st.spinner("Agent is thinking…"):
            result = agent.run(on_step=on_step)
    except LLMError as exc:
        st.error(f"LLM error: {exc}")
        st.stop()
    elapsed = time.time() - t0

    progress.progress(1.0, text=f"Done in {elapsed:.1f}s")
    phase_ph.markdown(render_phase_banner(done=True), unsafe_allow_html=True)

    # ---- Summary metrics ----
    st.divider()
    verified = sum(1 for c in result.citations if c.file_exists and c.line_valid)
    sc2 = st.columns(5)
    for col, (ic, val, lab) in zip(sc2, [
        ("📂", project_name, "Project"),
        ("🧭", result.iterations, "Steps"),
        ("🔖", len(result.citations), "Citations"),
        ("✅", f"{verified}/{len(result.citations)}", "Verified"),
        ("⏱️", f"{elapsed:.1f}s", "Time"),
    ]):
        col.markdown(
            f'<div class="metric-card"><div class="mc-ic">{ic}</div>'
            f'<div class="mc-val">{val}</div><div class="mc-lab">{lab}</div></div>',
            unsafe_allow_html=True,
        )

    # ---- Build report ----
    report_md = generate_report(target, result, cfg)

    # ---- Tabs ----
    tab_rpt, tab_trace, tab_cite, tab_ans = st.tabs(
        ["📄 Full Report", "🧭 Step-by-Step Trace", "✅ Citation Check", "💬 Final Answer"]
    )

    with tab_rpt:
        with st.container(border=True):
            st.markdown(report_md)
        st.download_button(
            "⬇️ Download Report (.md)", data=report_md.encode("utf-8"),
            file_name=f"report_{project_name}.md", mime="text/markdown",
            use_container_width=True,
        )

    with tab_trace:
        st.markdown(
            f"The agent completed **{result.iterations} step(s)** in "
            f"**{elapsed:.1f}s**. Each step's full tool call is below."
        )
        for step in result.steps:
            with st.expander(f"{step.iteration}. {step_title(step)}"
                             + (" ⚠️" if step.error else ""),
                             expanded=(step == result.steps[-1])):
                if step.thought:
                    st.markdown("**💭 Thought**")
                    st.info(step.thought)
                if step.action:
                    c1, c2 = st.columns([1, 3])
                    c1.markdown("**🔧 Tool**"); c1.code(step.action, language="text")
                    c2.markdown("**📥 Input**"); c2.code(step.action_input or "{}", language="json")
                if step.observation and step.observation not in ("(pending)", "Final Answer produced."):
                    st.markdown("**📤 Observation**")
                    obs = step.observation
                    if len(obs) > 2000:
                        obs = obs[:2000] + "\n…[truncated]"
                    if step.error:
                        st.error(obs)
                    else:
                        st.code(obs, language="text")

    with tab_cite:
        if result.citations:
            df = pd.DataFrame([
                {
                    "Citation": c.raw,
                    "File exists": "✅" if c.file_exists else "❌",
                    "Line valid": "✅" if c.line_valid else "⚠️",
                    "Status": "Verified" if (c.file_exists and c.line_valid) else "Unverified",
                }
                for c in result.citations
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{verified} of {len(result.citations)} referenced locations "
                       "confirmed to exist in the source.")
        else:
            st.info("No `file:line` citations were found in the final answer.")

    with tab_ans:
        st.markdown(result.final_answer or "_No final answer produced._")
        if result.truncated:
            st.warning("⚠️ The agent reached the iteration limit before finishing.")

    # ---- Save report ----
    os.makedirs(cfg.output_dir, exist_ok=True)
    report_path = os.path.join(cfg.output_dir, f"report_{project_name}.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_md)
    st.caption(f"💾 Report also saved to: `{report_path}`")

# -----------------------------------------------------------------------
# Footer
# -----------------------------------------------------------------------
st.markdown("---")
st.markdown(
    '<div class="app-footer">Codebase Understanding Agent · ReAct agentic workflow · '
    'tool use + result checking · simulate / ollama / openai backends</div>',
    unsafe_allow_html=True,
)
