# Viva Questions & Answers — Codebase Understanding Agent

Thirty questions covering the problem statement, architecture, tools, model
choice, implementation, testing, limitations, and team contributions. Answers
reflect the actual implementation in this repository.

---

## Problem statement

**Q1. What problem does this project solve, and why does it matter?**
Developers spend significant time understanding unfamiliar code before they can
change it. This agent automates that onboarding step: it explores a software
project, maps how files connect, extracts the business rules, and produces an
explanation where every claim is linked to the exact `file:line` in the source.
That reduces the time a new developer needs to become productive on a codebase.

**Q2. Why is "understanding code" hard to automate?**
Code understanding is not a single lookup; it requires exploring structure,
following dependencies across files, and inferring intent (business rules) from
logic. A fixed script can't anticipate what's important in every project, so we
use an agent that decides dynamically what to read next based on what it has
already seen.

---

## Architecture

**Q3. Describe the overall architecture.**
Four layers: (1) **LLM client** — a thin wrapper over Ollama, OpenAI, or a
simulator; (2) **Tools** — filesystem/code-analysis functions the agent can call;
(3) **Agent core** — a ReAct reasoning loop that orchestrates the tools; and
(4) **Report generator** — turns the agent's findings plus deterministic static
analysis into a Markdown report. `main.py` wires them together as a CLI.

**Q4. What is the ReAct pattern and why use it here?**
ReAct = Reason + Act. The model emits a *Thought*, then an *Action* (a tool call)
with an *Action Input* (JSON). The system executes the tool, returns an
*Observation*, and the loop repeats until a *Final Answer*. We use it because it
makes the agent's reasoning and tool use explicit, inspectable, and easy to
verify — which is exactly what "agentic workflow with tool use and checking
results" requires.

**Q5. How does the agent decide which tool to call next?**
In the real backends the LLM itself chooses, guided by a system prompt that
lists the tools and tells it to explore systematically (tree → find → parse → read
→ map → search → verify). In `simulate` mode a scripted-but-adaptive plan makes
the same sensible choices by inspecting the real tool output, so the workflow is
demonstrable without a model.

**Q6. What are the main components and how do they interact?**
`main.py` builds a `Config`, creates an `LLMClient` and `CodebaseAgent`, calls
`agent.run()`, then `generate_report()` and `save_report()`. The agent holds a
tool registry; each turn it parses the LLM response, dispatches the named tool
through `tools.dispatch`, and appends the observation to the conversation.

**Q7. Why separate the LLM client, tools, and report generator?**
Separation of concerns and testability. The agent talks only to the client's
`chat()` method, so any backend can be swapped without touching the loop. Tools
are pure functions that don't know about the LLM. The report generator calls the
same deterministic analysis functions directly, so a useful report can be
produced even in simulation mode.

---

## Tools

**Q8. List the agent's tools and their purpose.**
- `get_directory_tree` — indented layout view (first exploration step).
- `list_directory` — immediate contents of one directory.
- `find_files` — glob-based file discovery (e.g. `*.py`).
- `read_file` — file contents with line numbers, truncated for small models.
- `parse_file_structure` — imports, classes, methods, functions with line numbers.
- `map_dependencies` — internal import graph + external libraries.
- `search_content` — regex grep across the project, returns `file:line` matches.

**Q9. How does the code parser work, and why use Python's `ast`?**
For `.py` files we parse with the built-in `ast` module, which gives exact line
numbers, base classes, arguments, and docstrings with zero ambiguity. For other
languages we fall back to tuned regex heuristics that capture the same shape
(classes, functions/methods, imports). AST is preferred because it is precise and
dependency-free.

**Q10. How does the dependency mapper resolve imports to local files?**
It collects every `.py` file's dotted module name, then for each import it
computes the full dotted name and checks candidate paths (`mod.py`,
`mod/__init__.py`) on disk. Crucially, it tracks the import `level` (number of
leading dots) and resolves *relative* imports against the file's own package, so
`from .book import X` inside `library/library.py` correctly maps to
`library/book.py` rather than being misclassified as external.

**Q11. How does `search_content` help find business rules?**
Business rules are often encoded as guards — `raise ValueError(...)`,
comparisons, or `if` conditions. The agent searches for patterns like
`raise |ValueError|if .* not|assert` and gets back `file:line` hits it can cite.
Combined with reading the surrounding code, it can state the rule and where it
lives.

**Q12. How are tools registered and dispatched?**
Each tool module exposes a `TOOL_SPECS` list (name, description, parameters,
`func`). `tools.build_registry` aggregates them; `tools.dispatch(name, args)`
validates the JSON, calls the function, and catches all exceptions — returning
an error *string* instead of raising, so one bad call never crashes the loop.

---

## Model choice

**Q13. Why prefer locally running LLMs?**
They run offline, keep the codebase private (nothing leaves the machine), are
free, and avoid API rate limits. The brief explicitly asks to prefer local LLMs
where hardware supports them, which is why `ollama` is the default backend.

**Q14. What is Ollama and why was it chosen?**
Ollama is a local LLM runtime that serves models over a simple REST API on
`localhost:11434`. It's chosen because it's easy to install on Windows/Mac/Linux,
supports many open models, and exposes an OpenAI-compatible interface, so our
client code stays simple.

**Q15. Which model is recommended and why?**
`qwen2.5-coder:7b` by default. It's specifically tuned for code understanding,
performs well at explaining structure and rules, and the 7B size runs on a
typical laptop with ~6–8 GB RAM. Alternatives: `deepseek-coder-v2` (strong code),
`llama3.1:8b` or `mistral` (general purpose).

**Q16. What are the three backends and how do they differ?**
`ollama` calls a local model's `/api/chat`. `openai` calls any OpenAI-compatible
`/chat/completions` endpoint (needs an API key). `simulate` needs no model — it
returns scripted ReAct steps that drive *real* tools, and the report generator
supplies the analysis. All three share one `chat()` interface.

**Q17. What is the `simulate` mode and why is it valuable?**
It lets the full agentic workflow run with no LLM installed — essential for a
viva/demo on any machine. It's not a stub: it executes the real tools, the
conversation contains genuine observations, and the final report is built from
real static analysis with verified citations.

---

## Implementation

**Q18. Walk through one full agentic run on the sample project.**
(1) `get_directory_tree` reveals the layout. (2) `find_files *.py` lists the 6
sources. (3) `parse_file_structure` on `main.py` shows its `main()` function and
imports. (4) `read_file` on `main.py` reveals the demo logic. (5)
`map_dependencies` shows `main.py → library/__init__.py` and
`library/library.py → book/member/loan`. (6) `search_content` finds 19
validation/condition sites. (7) `read_file` on `book.py` captures copy rules.
(8) re-`map_dependencies` to verify. (9) Final Answer with citations, all
verified.

**Q19. How does "checking results" work — the three mechanisms?**
(1) **Tool-output validation:** if a tool returns an error string, the loop
feeds it straight back and reminds the agent to change approach. (2)
**Pre-answer verification:** the system prompt instructs the agent to re-read
cited code before its Final Answer (the simulator re-maps dependencies as a
verification step). (3) **Post-run citation verification:** every `file:line`
reference in the Final Answer is checked against the real files — existence and
line range — and a pass/fail table is added to the report.

**Q20. How are citations verified against the source?**
After the loop, the agent regex-scans the Final Answer for
`name.py:line` patterns. For each, it resolves the path relative to the target
project, checks the file exists, and — if a line is given — checks it falls
within the file's line count. The report's section 7 shows ✅/⚠️ for each.

**Q21. How is the report generated and what sections does it have?**
The generator calls the deterministic analysis functions (tree, parse every
file, dependency map, rule heuristics) and merges them with the agent's narrative
answer. Sections: (1) Executive summary, (2) Project structure, (3) Module
breakdown with line-linked classes/functions, (4) Dependencies, (5) Agent
business-rule explanation, (6) Auto-detected rules table, (7) Citation
verification, (8) Full agentic trace appendix.

**Q22. How does the agent handle a tool error or an invalid path?**
Tools never raise to the loop — they return a string starting with `Error:`.
The agent core detects that prefix, appends a reminder to reconsider, and
continues. The same applies to unknown tool names and bad JSON, all handled in
`dispatch`.

**Q23. What happens if the agent hits the iteration limit?**
The loop runs up to `max_iterations` (default 15). If no Final Answer is reached,
it returns a partial result flagged `truncated=True`, the report notes it, and
the gathered trace is still included — so the run degrades gracefully rather than
failing.

**Q24. How did you fix relative imports being misclassified as external?**
Initially `from .book import` was stripped to `book` and looked for at the root,
so `library/book.py` wasn't found and `book` was wrongly listed as an external
library. The fix records the import `level` and resolves relative imports
against the file's own package (`library`), yielding `library.book` →
`library/book.py`. A test (`test_map_dependencies_resolves_relative_imports`)
locks this in.

---

## Testing

**Q25. What is tested and why use the simulate backend for tests?**
Tools are unit-tested against the sample project (tree, find, read, parse,
dependency resolution, search, error paths). The agent is tested end-to-end for
loop completion, citation verification, and report writing. Tests use `simulate`
so they're fast (sub-second), deterministic, and need no LLM — ideal for CI.

**Q26. What does the sample project demonstrate?**
A Mini Library Management System with clear, citable business rules: a 5-loan
member limit, a 14-day loan period, $0.50/day overdue fines, a minor-cannot-
borrow-reference rule, and availability guards. It's small enough to inspect
manually but rich enough to exercise every tool and the citation verifier.

---

## Limitations

**Q27. What are the main limitations?**
Python has full AST precision; other languages use regex heuristics. File reads
are truncated for small local models, so huge files are understood via parsing
rather than full reads. Implicit rules spread across many files may need more
iterations or a bigger model. Only `file:line` citations are auto-verified; prose
claims without a location aren't checked.

**Q28. How does it behave on non-Python projects?**
The directory, find, read, and search tools work for any text. `parse_file_structure`
uses regex heuristics for JS/TS/Java/etc. and may miss language-specific
constructs. `map_dependencies` is Python-focused (import resolution), so for
other ecosystems the dependency section is less complete — a clear extension
target.

---

## Contributions & future work

**Q29. How was the work divided among the team members?**
*(Replace names with your actual team.)*
- **Member A — Agent & LLM integration:** the ReAct loop, prompt design, the
  multi-backend LLM client (Ollama/OpenAI/simulate), and the simulation logic.
- **Member B — Tools & static analysis:** file explorer, AST code parser,
  dependency mapper with relative-import resolution, search, and the rule
  heuristics.
- **Member C — Reporting, testing & sample project:** the report generator,
  the citation verifier, the test suite, the sample library project, the README,
  and this viva document.

**Q30. What would you improve next?**
Add tree-sitter for accurate multi-language parsing; support call-graph edges
(not just imports) so the agent can trace data flow; add iterative refinement
where the report generator asks the agent to expand thin sections; cache tool
results to cut LLM turns on large repos; and add a web UI that renders the
report with clickable line links.
