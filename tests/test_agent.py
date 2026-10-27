"""Tests for the agentic core (ReAct loop) and the LLM client.

All tests use the ``simulate`` backend so they run anywhere with no model.
"""

from __future__ import annotations

import os

import pytest

from config import Config
from agent import CodebaseAgent
from agent.core import AgentResult
from llm import LLMClient
from output.report_generator import generate_report, save_report

SAMPLE = os.path.normpath(os.path.join(os.path.dirname(__file__), "sample_project"))
SAMPLE2 = os.path.normpath(os.path.join(os.path.dirname(__file__), "sample_grading"))


def _sim_config() -> Config:
    cfg = Config()
    cfg.backend = "simulate"
    cfg.max_iterations = 15
    return cfg


# ---------------------------------------------------------------------
# LLM client (simulate)
# ---------------------------------------------------------------------
def test_simulate_client_produces_react_format():
    cfg = _sim_config()
    client = LLMClient(cfg)
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": f"Target project: {SAMPLE}\nExplain it."},
    ]
    resp = client.chat(messages)
    assert "Thought:" in resp
    assert "Action:" in resp
    assert "Action Input:" in resp
    assert client.is_available() is True
    assert "simulate" in client.describe()


def test_simulate_client_first_turn_is_exploration():
    """The first simulated turn should kick off directory-tree exploration."""
    cfg = _sim_config()
    client = LLMClient(cfg)
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": f"Target project: {SAMPLE}\nExplain it."},
    ]
    resp = client.chat(messages)
    assert "Action: get_directory_tree" in resp


def test_simulate_final_answer_cites_real_files():
    """A real agent run (with real tool output) yields a cited final answer."""
    cfg = _sim_config()
    result = CodebaseAgent(cfg, SAMPLE).run()
    assert ".py:" in result.final_answer


# ---------------------------------------------------------------------
# Agent end-to-end (simulate)
# ---------------------------------------------------------------------
def test_agent_runs_full_loop_on_sample_project():
    cfg = _sim_config()
    agent = CodebaseAgent(cfg, SAMPLE)
    result = agent.run()

    assert isinstance(result, AgentResult)
    assert result.iterations > 0
    assert len(result.steps) > 0
    assert result.final_answer.strip() != ""
    # every step that called a tool should have a real (non-pending) observation
    tool_steps = [s for s in result.steps if s.action]
    assert all(s.observation != "(pending)" for s in tool_steps)


def test_agent_citations_verify_against_source():
    cfg = _sim_config()
    result = CodebaseAgent(cfg, SAMPLE).run()
    assert len(result.citations) > 0, "expected the agent to cite some code"
    for c in result.citations:
        assert c.file_exists, f"citation references missing file: {c.raw}"
        assert c.line_valid, f"citation line out of range: {c.raw}"


def test_agent_works_on_second_sample_grading():
    """The agent must generalise to a different domain (grading system)."""
    cfg = _sim_config()
    result = CodebaseAgent(cfg, SAMPLE2).run()
    assert result.iterations > 0
    assert result.final_answer.strip() != ""
    assert len(result.citations) > 0
    for c in result.citations:
        assert c.file_exists, f"citation references missing file: {c.raw}"
        assert c.line_valid, f"citation line out of range: {c.raw}"
    # the final answer should name the grading modules, not the library ones
    assert "course" in result.final_answer or "student" in result.final_answer


def test_agent_error_handling_on_bad_tool_path():
    """Tool dispatch with a bad path returns an error string, never raises."""
    from tools import build_registry, dispatch
    cfg = _sim_config()
    registry = build_registry(cfg)
    out = dispatch(registry, "read_file", {"path": "no/such/file.py"})
    assert out.startswith("Error")
    # unknown tool name is also handled gracefully
    out2 = dispatch(registry, "not_a_tool", {})
    assert "unknown tool" in out2


def test_report_generator_writes_file(tmp_path):
    cfg = _sim_config()
    cfg.output_dir = str(tmp_path)
    result = CodebaseAgent(cfg, SAMPLE).run()
    report = generate_report(SAMPLE, result, cfg)
    assert "# Codebase Understanding Report" in report
    assert "## 3. Module Breakdown" in report
    assert "## 6. Business Rules" in report
    path = save_report(report, SAMPLE, cfg)
    assert os.path.isfile(path)


def test_parse_response_extracts_final_answer():
    from agent.core import CodebaseAgent as _A
    thought, action, action_input, final = _A._parse_response(
        "Thought: done.\nFinal Answer: The project does X."
    )
    assert final == "The project does X."
    assert action is None


def test_parse_response_extracts_action():
    from agent.core import CodebaseAgent as _A
    thought, action, action_input, final = _A._parse_response(
        'Thought: look at tree\nAction: get_directory_tree\n'
        'Action Input: {"path": "."}'
    )
    assert action == "get_directory_tree"
    assert action_input == '{"path": "."}'
    assert final is None
