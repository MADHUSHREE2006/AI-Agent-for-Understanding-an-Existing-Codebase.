"""Streamlit web frontend for the Codebase Understanding Agent.

Run with:

    python -m streamlit run app.py

The UI reuses the existing agent core, LLM client, and report generator — no
new agent logic is added here. Key features:

* Live ReAct trace — each step (Thought → Action → Observation) appears as
  it happens via the agent's on_step callback.
* Four result tabs: rendered report, step-by-step trace, citation table, final answer.
* Two bundled sample projects pre-loaded as quick-start options.
* Download button exports the full Markdown report.
* Sidebar backend switcher (simulate / ollama / openai).
"""

from __future__ import annotations

import os
import time

import streamlit as st

from agent import CodebaseAgent
from config import Config, get_config
from llm import LLMClient, LLMError
from output.report_generator import generate_report
from tools.code_parser import parse_file_structure, extract_business_rule_candidates
from tools.dependency_mapper import map_dependencies
from tools.file_explorer import find_files

# -----------------------------------------------------------------------
# Path constants
# -----------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = {
    "📚 Library Management System": os.path.join(HERE, "tests", "sample_project"),
    "🎓 Student Grading System":    os.path.join(HERE, "tests", "sample_grading"),
}

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
TOOL_ICONS = {
    "get_directory_tree":  "🌳",
    "find_files":          "🔍",
    "read_file":           "📄",
    "parse_file_structure":"🔬",
    "map_dependencies":    "🕸️",
    "search_content":      "🔎",
    "list_directory":      "📁",
}

def step_label(step) -> str:
    icon = TOOL_ICONS.get(step.action, "🔧") if step.action else "✅"
    name = step.action or "Final Answer"
    warn = " ⚠️" if step.error else ""
    return f"{icon} Step {step.iteration} — {name}{warn}"


def render_step(step) -> None:
    """Render one ReAct step inside an expander."""
    if step.thought:
        st.markdown(f"**💭 Thought**")
        st.info(step.thought)
    if step.action:
        col1, col2 = st.columns([1, 3])
        col1.markdown(f"**🔧 Tool**")
        col1.code(step.action, language="text")
        col2.markdown(f"**📥 Input**")
        col2.code(step.action_input or "{}", language="json")
    if step.observation and step.observation not in ("(pending)", "Final Answer produced."):
        st.markdown("**📤 Observation**")
        obs = step.observation
        if len(obs) > 1800:
            obs = obs[:1800] + "\n…[truncated]"
        if step.error:
            st.error(obs)
        else:
            st.code(obs, language="text")


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
    """Return (n_files, n_classes, n_functions, n_rules) for the sidebar card."""
    py_files_out = find_files(target, "*.py")
    n_files = py_files_out.count("\n") if "FOUND" in py_files_out else 0
    deps     = map_dependencies(target)
    files    = deps.get("files", [])
    n_cls    = sum(len(parse_file_structure(os.path.join(target, f)).get("classes", [])) for f in files)
    n_fn     = sum(len(parse_file_structure(os.path.join(target, f)).get("functions", [])) for f in files)
    n_rules  = len(extract_business_rule_candidates(target))
    return len(files), n_cls, n_fn, n_rules


# -----------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------
st.set_page_config(
    page_title="Codebase Understanding Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for a clean look
st.markdown("""
<style>
.stTabs [data-baseweb="tab-list"] button { font-size: 0.95rem; }
.metric-card { background:#f0f2f6; border-radius:8px; padding:12px 16px; }
.step-ok  { border-left: 4px solid #21c354; padding-left: 8px; }
.step-err { border-left: 4px solid #e05252; padding-left: 8px; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/source-code.png", width=64)
    st.title("Codebase Agent")
    st.caption("AI-powered code explorer")
    st.divider()

    st.subheader("⚙️ Backend")
    backend = st.selectbox(
        "LLM backend",
        ["simulate", "ollama", "openai"],
        help="simulate = no model needed | ollama = local LLM | openai = hosted API",
    )

    model = host = base_url = api_key = ""
    if backend == "ollama":
        model = st.text_input("Model name", value="qwen2.5-coder:7b",
                              help="Run: ollama pull qwen2.5-coder:7b first")
        host  = st.text_input("Ollama host", value="http://localhost:11434")
    elif backend == "openai":
        model    = st.text_input("Model", value="gpt-4o-mini")
        base_url = st.text_input("Base URL", value="https://api.openai.com/v1")
        api_key  = st.text_input("API key", type="password")

    max_iter = st.slider("Max steps", 3, 20, 12)
    st.divider()

    # Backend health badge
    cfg_test = apply_overrides(get_config(), backend, model, host, base_url, api_key, max_iter)
    if LLMClient(cfg_test).is_available():
        st.success(f"✅ {backend} ready")
    else:
        st.warning(f"⚠️ {backend} unavailable → will use simulate")

    st.divider()
    st.caption("💡 `simulate` runs the full agentic workflow with no model "
               "download. Tools are real; analysis is real.")

# -----------------------------------------------------------------------
# Main area — header
# -----------------------------------------------------------------------
st.title("🤖 Codebase Understanding Agent")
st.markdown(
    "Explore any Python project: the agent **reasons → uses tools → checks results** "
    "in a live ReAct loop, then produces a code-linked report where every claim "
    "cites the exact `file:line`."
)
st.divider()

# -----------------------------------------------------------------------
# Target selection
# -----------------------------------------------------------------------
col_path, col_sample = st.columns([3, 2])

with col_path:
    st.markdown("**📂 Project to analyse**")
    target_input = st.text_input(
        "Path",
        value=SAMPLES["📚 Library Management System"],
        label_visibility="collapsed",
        placeholder="e.g. C:/Users/you/my_project",
    )

with col_sample:
    st.markdown("**⚡ Quick samples**")
    sel = st.selectbox("sample", list(SAMPLES.keys()), label_visibility="collapsed")
    if st.button("Load sample", use_container_width=True):
        target_input = SAMPLES[sel]
        st.session_state["last_target"] = target_input
        st.rerun()

# respect "Load sample" click across reruns
target = st.session_state.get("last_target", target_input)
target = os.path.abspath(target)
valid  = os.path.isdir(target)

if not valid:
    st.error(f"❌ Not a valid directory: `{target}`")

# Project quick-stats card (shown before running, zero LLM calls)
if valid:
    with st.expander("📊 Project snapshot (static analysis)", expanded=True):
        with st.spinner("Scanning…"):
            n_files, n_cls, n_fn, n_rules = quick_project_stats(target)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Python files",  n_files)
        c2.metric("Classes",       n_cls)
        c3.metric("Functions",     n_fn)
        c4.metric("Rule candidates", n_rules)

st.divider()
run_btn = st.button("🚀 Run Agent", type="primary", disabled=not valid,
                    use_container_width=True)

# -----------------------------------------------------------------------
# Run the agent
# -----------------------------------------------------------------------
if run_btn and valid:

    cfg = apply_overrides(get_config(), backend, model, host, base_url, api_key, max_iter)
    llm = LLMClient(cfg)
    if cfg.backend != "simulate" and not llm.is_available():
        st.warning(f"⚠️ {cfg.backend} not available — falling back to **simulate**.")
        cfg.backend = "simulate"
        llm = LLMClient(cfg)

    project_name = os.path.basename(target)

    # ---- Live trace panel ----
    st.markdown("### 🔄 Live Agentic Trace")
    st.caption("Each step appears as the agent reasons and uses tools.")
    trace_container = st.container(border=True)
    step_placeholders: list = []
    all_steps: list = []

    def on_step(step):
        all_steps.append(step)
        ph = trace_container.empty()
        step_placeholders.append(ph)
        with ph.container():
            cls = "step-err" if step.error else "step-ok"
            st.markdown(
                f'<div class="{cls}"><strong>{step_label(step)}</strong></div>',
                unsafe_allow_html=True,
            )
            if step.thought:
                st.caption(f"💭 {step.thought[:200]}{'…' if len(step.thought)>200 else ''}")
            if step.action and step.observation not in ("(pending)", "Final Answer produced."):
                obs_short = step.observation[:300] + "…" if len(step.observation) > 300 else step.observation
                if step.error:
                    st.error(obs_short)
                else:
                    st.success(f"✅ {step.action} returned {len(step.observation)} chars")

    agent = CodebaseAgent(cfg, target, llm)
    t0 = time.time()
    try:
        with st.spinner("Agent is thinking…"):
            result = agent.run(on_step=on_step)
    except LLMError as exc:
        st.error(f"LLM error: {exc}")
        st.stop()
    elapsed = time.time() - t0

    # ---- Summary metrics ----
    st.divider()
    st.markdown("### ✅ Results")
    verified = sum(1 for c in result.citations if c.file_exists and c.line_valid)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Project",   project_name)
    m2.metric("Steps",     result.iterations)
    m3.metric("Citations", len(result.citations))
    m4.metric("Verified",  f"{verified}/{len(result.citations)}")
    m5.metric("Time",      f"{elapsed:.1f}s")

    # ---- Build report ----
    report_md = generate_report(target, result, cfg)

    # ---- Four tabs ----
    tab_rpt, tab_trace, tab_cite, tab_ans = st.tabs(
        ["📄 Full Report", "🧭 Step-by-Step Trace", "✅ Citation Check", "💬 Final Answer"]
    )

    # --- Tab 1: Full report ---
    with tab_rpt:
        st.markdown(report_md, unsafe_allow_html=False)
        st.divider()
        st.download_button(
            label="⬇️ Download Report (.md)",
            data=report_md.encode("utf-8"),
            file_name=f"report_{project_name}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    # --- Tab 2: Step-by-step trace ---
    with tab_trace:
        st.markdown(
            f"The agent completed **{result.iterations} step(s)** "
            f"in **{elapsed:.1f}s**. Expand any step to see the full tool call."
        )
        for step in result.steps:
            with st.expander(step_label(step),
                             expanded=(step == result.steps[-1])):
                render_step(step)

    # --- Tab 3: Citation verification ---
    with tab_cite:
        if result.citations:
            st.markdown(
                f"The agent cited **{len(result.citations)}** code location(s). "
                f"**{verified}** were verified to exist in the real source:"
            )
            for c in result.citations:
                fe = "✅" if c.file_exists else "❌"
                lv = "✅" if c.line_valid  else "⚠️"
                status = "✅ Verified" if (c.file_exists and c.line_valid) else "⚠️ Unverified"
                st.markdown(f"- {status} &nbsp;&nbsp; `{c.raw}` &nbsp; file {fe} &nbsp; line {lv}")
        else:
            st.info("No `file:line` citations were found in the final answer.")

    # --- Tab 4: Final answer ---
    with tab_ans:
        st.markdown(result.final_answer or "_No final answer produced._")
        if result.truncated:
            st.warning("⚠️ The agent reached the iteration limit before finishing.")

    # ---- Save report to disk ----
    os.makedirs(cfg.output_dir, exist_ok=True)
    report_path = os.path.join(cfg.output_dir, f"report_{project_name}.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_md)
    st.caption(f"Report also saved to: `{report_path}`")
