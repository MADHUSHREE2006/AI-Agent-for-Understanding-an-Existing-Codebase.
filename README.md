# Codebase Understanding Agent

An **agentic AI** that reads an existing software project, explores its files,
maps how they connect, identifies the business rules, and produces a clear
explanation linked to the relevant code (`file:line`).

It is built to demonstrate a genuine **agentic workflow**: an autonomous
reasoning loop that uses tools, executes a task step by step, and *checks its
own results* before answering.

> **Problem statement.** Developers spend time understanding unfamiliar code.
> This agent explores files, maps connections, and produces explanations
> linked to the relevant code.

---

## How it works

The agent uses the **ReAct** pattern (Reason → Act → Observe). The LLM is the
"brain"; the tools are its "eyes and hands".

```mermaid
flowchart TD
    A([User: target project]) --> B[Agent ReAct loop]
    B -->|Thought| C{Done?}
    C -->|no| D[Action: choose a tool]
    D --> E[Execute tool]
    E --> F[Observe result]
    F -->|check for errors| G{Result OK?}
    G -->|error| B
    G -->|ok| B
    C -->|yes| H[Final Answer]
    H --> I[Verify citations vs real source]
    I --> J[Generate code-linked report]
    J --> K([report_project.md])
```

The loop demonstrates the three required agentic behaviours:

| Requirement | How it's shown |
|-------------|----------------|
| **Tool use** | The agent reasons, then calls one of 7 tools (directory tree, find files, read file, parse structure, map dependencies, search). |
| **Task execution** | It iterates until it has explored structure, dependencies, and rules — up to a configurable iteration limit. |
| **Checking results** | (1) Every tool output is checked for errors and fed back; (2) the agent re-reads cited code before answering; (3) after the run, every `file:line` citation in the answer is verified against the real source. |

### Agentic workflow in detail

1. **Explore** — `get_directory_tree`, then `find_files` to locate sources.
2. **Understand** — `parse_file_structure` (AST for Python) and `read_file` on
   the entry point and key modules.
3. **Connect** — `map_dependencies` resolves imports (including relative ones)
   to local files and external libraries.
4. **Find rules** — `search_content` for validation/condition patterns; a
   static heuristic also auto-detects rule candidates.
5. **Verify** — re-map dependencies to confirm understanding, then verify every
   citation against the source.

---

## Model choice (local LLMs preferred)

Per the brief, locally running LLMs are preferred. The agent talks to a model
through a thin, dependency-light client with **three interchangeable backends**:

| Backend | What it uses | When to use |
|---------|--------------|-------------|
| `ollama` (default) | A local model via **Ollama** | Preferred — runs offline, free, private. |
| `openai` | Any OpenAI-compatible API (OpenAI, Groq, LM Studio) | When you want a hosted model. |
| `simulate` | No model — scripted adaptive responses | Demos/viva without any LLM installed. |

`simulate` is not a fake: it drives **real tool calls** against the real code and
the report generator performs real static analysis, so it produces a genuine,
code-linked report with verified citations on any machine.

**Recommended local model:** `qwen2.5-coder:7b` (excellent at code, small enough
for a laptop). Other good options: `deepseek-coder-v2`, `llama3.1:8b`, `mistral`.

---

## Setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. (Optional) Install Ollama for local LLMs
- **Windows:** download the installer from <https://ollama.com/download>
- Start it: `ollama serve`
- Pull a model: `ollama pull qwen2.5-coder:7b`

**Note:** If you have limited disk space on C: drive, Ollama stores models in `%USERPROFILE%\.ollama` by default. Use the `simulate` backend instead — it needs no model download and works offline.

### 3. (Optional) OpenAI-compatible API
Set `OPENAI_API_KEY` (and optionally `CBU_OPENAI_BASE_URL` / `CBU_OPENAI_MODEL`).

---

## Usage

```bash
# Demo on the bundled sample project — no LLM needed:
python main.py tests/sample_project --backend simulate

# Use a locally running Ollama model (preferred):
python main.py path/to/your/project --backend ollama --model qwen2.5-coder:7b

# Use an OpenAI-compatible API:
python main.py path/to/your/project --backend openai

# Print the full agentic trace to the console:
python main.py tests/sample_project --backend simulate --trace
```

If the chosen backend is unavailable (e.g. Ollama not running), the CLI
**automatically falls back to `simulate`** with a warning, so a demo never
fails.

### Output
A comprehensive markdown report is saved to `output_reports/report_<projectname>.md` with:
- **Project structure** — directory tree with file sizes
- **Module breakdown** — all classes/functions with exact line numbers
- **Dependency map** — internal imports and external libraries
- **Business rules** — agent's explanation citing exact `file:line` locations
- **Auto-detected rules table** — static analysis of validations/conditions
- **Citation verification** — ✅/⚠️ table showing all citations were checked
- **Full agentic trace** — every tool call and observation (expandable appendix)

---

## Project structure

```
.
├── main.py                     # CLI entry point
├── config.py                   # Config (backend selection, limits, filters)
├── conftest.py                 # makes root importable for pytest
├── requirements.txt
├── agent/
│   ├── core.py                 # ReAct loop + citation verification
│   └── prompts.py              # system prompt + ReAct format
├── tools/
│   ├── file_explorer.py        # tree, find_files, read_file, list_directory
│   ├── code_parser.py          # AST structure + business-rule heuristics
│   ├── dependency_mapper.py    # import graph (relative imports resolved)
│   ├── search.py               # content search (regex)
│   └── __init__.py             # tool registry + dispatch
├── llm/
│   └── client.py               # Ollama / OpenAI / simulate backends
├── output/
│   └── report_generator.py      # markdown report with code links
├── tests/
│   ├── test_tools.py            # tool unit tests
│   ├── test_agent.py            # agent + LLM client tests
│   └── sample_project/          # library mgmt system (the analysis target)
├── output_reports/             # generated reports
│   └── report_<name>.md        # comprehensive markdown report with citations
├── docs/
│   └── VIVA_QUESTIONS.md       # 30 viva Q&A
└── conftest.py                 # pytest config for imports
```

---

## Testing
```bash
python -m pytest -q
```
All tests use the `simulate` backend, so they run anywhere with no model and
complete in well under a second.

---

## Limitations
- **Language support:** Python gets full AST precision; other languages use
  regex heuristics for structure (still useful, less exact).
- **Context window:** local models are small, so file reads are truncated to a
  configurable size; very large files are summarised implicitly by parsing
  rather than reading whole.
- **Rule understanding:** the LLM explains rules from what the tools surface;
  deeply implicit rules (across many files) may need more iterations or a
  larger model. The static heuristic provides a model-independent safety net.
- **Citations:** only `file:line` patterns are auto-verified; prose claims that
  don't cite a location aren't checked.
