"""The agentic core: a ReAct loop for understanding a codebase.

This is where the project demonstrates an agentic workflow:

* **Tool use**       - the agent reasons, picks a tool, and calls it.
* **Task execution** - the agent iteratively explores until the codebase is
  understood.
* **Checking results** - every tool output is checked for errors and fed back
  immediately, the agent is told to re-read cited code before answering, and
  after the run every citation in the final answer is verified against the
  real files (reported as verified / unverified).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import Config
from llm import LLMClient, LLMError
from tools import build_registry, dispatch, tool_descriptions
from .prompts import SYSTEM_PROMPT, USER_TASK_TEMPLATE, FORMAT_REMINDER


@dataclass
class AgentStep:
    """One turn of the ReAct trace."""
    iteration: int
    thought: str
    action: Optional[str]
    action_input: Optional[str]
    observation: str
    error: bool = False


@dataclass
class Citation:
    raw: str
    file: str
    line: Optional[int]
    file_exists: bool
    line_valid: bool


@dataclass
class AgentResult:
    final_answer: str
    steps: List[AgentStep] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    iterations: int = 0
    backend: str = ""
    truncated: bool = False

    def trace_text(self) -> str:
        """Render the full agentic trace for display / debugging."""
        out: List[str] = []
        for s in self.steps:
            out.append(f"--- Iteration {s.iteration} ---")
            out.append(f"Thought: {s.thought}")
            if s.action:
                out.append(f"Action: {s.action}")
                out.append(f"Action Input: {s.action_input}")
            else:
                out.append("(no action parsed)")
            out.append(f"Observation: {s.observation}")
            out.append("")
        verified = sum(1 for c in self.citations if c.file_exists and c.line_valid)
        out.append(
            f"Citations: {len(self.citations)} found, {verified} verified, "
            f"{len(self.citations) - verified} unverified."
        )
        return "\n".join(out)


class CodebaseAgent:
    """Drives a ReAct loop over a target project."""

    # Patterns we recognise as citations in the final answer.
    _CITE_RE = re.compile(
        r"([A-Za-z0-9_./\\-]+\.(?:py|js|ts|jsx|tsx|java|go|cs|rb|php))\s*:(\d+)"
    )

    def __init__(self, config: Config, target_path: str, llm: Optional[LLMClient] = None):
        self.config = config
        self.target_path = os.path.normpath(target_path)
        self.llm = llm or LLMClient(config)
        self.registry = build_registry(config)

    # ------------------------------------------------------------------
    def run(self) -> AgentResult:
        """Execute the agentic loop and return the agent's findings."""
        system = SYSTEM_PROMPT.format(tools=tool_descriptions(self.registry))
        task = USER_TASK_TEMPLATE.format(target=self.target_path)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]

        steps: List[AgentStep] = []
        final_answer = ""
        truncated = False

        for i in range(1, self.config.max_iterations + 1):
            try:
                response = self.llm.chat(messages)
            except LLMError as exc:
                return AgentResult(
                    final_answer=f"[LLM error: {exc}]",
                    steps=steps, iterations=i, backend=self.llm.describe(), truncated=True,
                )

            messages.append({"role": "assistant", "content": response})
            thought, action, action_input, final = self._parse_response(response)
            steps.append(self._make_step(i, thought, action, action_input))

            # Final Answer -> done (after verifying findings).
            if final is not None:
                final_answer = final
                break

            # No parseable action -> nudge the model back to the format.
            if not action:
                messages.append({"role": "user", "content": FORMAT_REMINDER})
                continue

            # ---- Tool use + checking results ------------------------------
            observation = dispatch(self.registry, action, action_input or "")
            is_error = observation.startswith("Error")
            steps[-1].observation = observation
            steps[-1].error = is_error
            messages.append({"role": "user", "content": f"Observation: {observation}"})

            # Checking results: if a tool erred, remind the agent to adapt.
            if is_error:
                messages.append({
                    "role": "user",
                    "content": "That tool call returned an error. Reconsider and try a different approach or path.",
                })
        else:
            truncated = True
            final_answer = (
                "I reached the maximum number of steps before producing a final "
                "answer. Here is what I have gathered so far — see the trace."
            )

        # ---- Checking results: verify every citation ---------------------
        citations = self._verify_citations(final_answer)

        return AgentResult(
            final_answer=final_answer,
            steps=steps,
            citations=citations,
            iterations=len(steps),
            backend=self.llm.describe(),
            truncated=truncated,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_response(response: str):
        """Extract (thought, action, action_input, final_answer) from text.

        ``final_answer`` is non-None when the agent chose to stop.
        """
        final_m = re.search(r"Final Answer:\s*(.*)", response, re.DOTALL)
        if final_m:
            thought = ""
            t = re.search(r"Thought:\s*(.+?)(?:\nFinal Answer:|$)", response, re.DOTALL)
            if t:
                thought = t.group(1).strip()
            return thought, None, None, final_m.group(1).strip()

        thought_m = re.search(r"Thought:\s*(.*?)(?=\nAction:|$)", response, re.DOTALL)
        thought = thought_m.group(1).strip() if thought_m else ""
        action_m = re.search(r"Action:\s*([A-Za-z_][\w]*)", response)
        # Action Input: the rest of that line (JSON), robust to extra prose after.
        input_m = re.search(r"Action Input:\s*(\{.*?\})\s*$", response, re.DOTALL | re.MULTILINE)
        if not input_m:
            input_m = re.search(r"Action Input:\s*(\{.*\})", response, re.DOTALL)
        action = action_m.group(1).strip() if action_m else None
        action_input = input_m.group(1).strip() if input_m else None
        return thought, action, action_input, None

    @staticmethod
    def _make_step(i, thought, action, action_input):
        return AgentStep(
            iteration=i,
            thought=thought,
            action=action,
            action_input=action_input,
            observation="(pending)",
        )

    # ------------------------------------------------------------------
    def _verify_citations(self, text: str) -> List[Citation]:
        """Check that each `file:line` reference in the answer is real."""
        citations: List[Citation] = []
        seen = set()
        for m in self._CITE_RE.finditer(text):
            raw = m.group(0)
            if raw in seen:
                continue
            seen.add(raw)
            file_ref = m.group(1).replace("\\", "/")
            line_no = int(m.group(2))
            # resolve relative to target project
            candidate = file_ref
            if not os.path.isabs(candidate):
                candidate = os.path.normpath(os.path.join(self.target_path, file_ref))
            exists = os.path.isfile(candidate)
            line_valid = False
            if exists:
                try:
                    with open(candidate, "r", encoding="utf-8", errors="replace") as fh:
                        n_lines = sum(1 for _ in fh)
                    line_valid = 1 <= line_no <= n_lines
                except OSError:
                    line_valid = False
            citations.append(
                Citation(raw=raw, file=file_ref, line=line_no,
                         file_exists=exists, line_valid=line_valid)
            )
        return citations
