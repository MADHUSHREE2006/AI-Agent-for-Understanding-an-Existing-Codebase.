# Git Push Guide

## Files to push (all essential code and docs)

### ✅ DO PUSH these files:

**Core application:**
- `main.py` — CLI entry point
- `config.py` — configuration (backends, limits, filters)
- `conftest.py` — pytest import configuration
- `requirements.txt` — Python dependencies
- `.gitignore` — git ignore rules

**Source code packages:**
- `agent/` — ReAct loop core (`core.py`, `prompts.py`, `__init__.py`)
- `llm/` — LLM client with 3 backends (`client.py`, `__init__.py`)
- `tools/` — 7 agent tools (`file_explorer.py`, `code_parser.py`, `dependency_mapper.py`, `search.py`, `__init__.py`)
- `output/` — report generator (`report_generator.py`, `__init__.py`)

**Tests and sample project:**
- `tests/test_tools.py` — tool unit tests (21 tests)
- `tests/test_agent.py` — agent integration tests
- `tests/__init__.py`
- `tests/sample_project/` — complete sample target project
  - `library/*.py` — book, member, loan, library modules
  - `main.py` — demo entry point
  - `README.md` — sample project docs

**Documentation:**
- `README.md` — main project documentation (setup, usage, architecture)
- `docs/VIVA_QUESTIONS.md` — 30 viva questions with answers
- `output_reports/report_sample_project.md` — example output report
- `output_reports/.gitkeep` — ensures directory exists

### ❌ DO NOT PUSH (auto-generated or user-specific):

**Python caches (gitignored):**
- `__pycache__/` — Python bytecode cache
- `*.pyc`, `*.pyo` — compiled Python files
- `.pytest_cache/` — pytest cache
- `.mypy_cache/` — type checker cache

**User-generated reports (gitignored):**
- `output_reports/*` (except the sample report)
- Any reports users create when analyzing their own projects

**Virtual environments (gitignored):**
- `.venv/`, `venv/` — Python virtual environments

**IDE/editor files (gitignored):**
- `.vscode/`, `.idea/` — editor settings
- `.DS_Store` — macOS metadata

**Docker working directory (gitignored):**
- `target_project/` — mount point for analysis (we removed Docker files)

## Quick git commands

```bash
# Initialize repo (if not already done)
git init

# Add all files (gitignore will exclude unwanted ones automatically)
git add .

# Check what will be committed
git status

# Commit
git commit -m "Initial commit: Codebase Understanding Agent with agentic workflow"

# Push to remote (replace with your repo URL)
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

## File count summary
- **Total files to push:** ~29 files
- **Python source files:** 18
- **Documentation files:** 4 (README, viva Q&A, sample report, this guide)
- **Test files:** 2 + sample project (7 files)
- **Config files:** 4 (.gitignore, requirements.txt, config.py, conftest.py)

## What happens after push
✅ Anyone who clones your repo gets:
  - Complete working code
  - All tests (can run `pytest -q` immediately)
  - Sample project to analyze
  - Full documentation
  - Example output report

❌ They won't get:
  - Your Python caches (regenerate automatically)
  - Your local virtual environment (they create their own)
  - Your generated reports (they generate new ones)

## Verification before push
```bash
# Make sure tests pass
python -m pytest -q

# Make sure agent works
python main.py tests/sample_project --backend simulate

# Check what git will push
git status
git diff --cached
```
