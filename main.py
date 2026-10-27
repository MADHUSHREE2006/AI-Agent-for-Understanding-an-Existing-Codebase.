"""Codebase Understanding Agent — command-line entry point.

Usage examples:

    # Demo on the bundled sample project, no LLM required:
    python main.py tests/sample_project

    # Use a locally running Ollama model (preferred):
    python main.py path/to/project --backend ollama --model qwen2.5-coder:7b

    # Use any OpenAI-compatible API:
    python main.py path/to/project --backend openai

    # Print the full agentic trace to the console:
    python main.py path/to/project --trace
"""

from __future__ import annotations

import argparse
import os
import sys

from config import Config, get_config
from agent import CodebaseAgent
from llm import LLMClient, LLMError
from output.report_generator import generate_report, save_report


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="codebase-agent",
        description="An agentic AI that reads a codebase and explains its "
                    "structure, dependencies, and business rules.",
    )
    p.add_argument("target", help="Path to the project to analyse.")
    p.add_argument("--backend", choices=["ollama", "openai", "simulate"],
                   help="LLM backend (default: ollama, falls back to simulate).")
    p.add_argument("--model", help="Model name (overrides config for the backend).")
    p.add_argument("--ollama-host", help="Ollama host URL (default http://localhost:11434).")
    p.add_argument("--openai-base-url", help="OpenAI-compatible base URL.")
    p.add_argument("--output", help="Output directory for reports (default output_reports).")
    p.add_argument("--max-iterations", type=int, help="Max agentic steps (default 15).")
    p.add_argument("--trace", action="store_true",
                   help="Print the full agentic trace to the console.")
    return p


def main(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)

    target = os.path.abspath(args.target)
    if not os.path.isdir(target):
        print(f"Error: target is not a directory: {target}", file=sys.stderr)
        return 2

    # Build config from environment, then apply CLI overrides.
    cfg = get_config()
    if args.backend:
        cfg.backend = args.backend
    if args.model:
        if cfg.backend == "ollama":
            cfg.ollama_model = args.model
        else:
            cfg.openai_model = args.model
    if args.ollama_host:
        cfg.ollama_host = args.ollama_host
    if args.openai_base_url:
        cfg.openai_base_url = args.openai_base_url
    if args.output:
        cfg.output_dir = args.output
    if args.max_iterations:
        cfg.max_iterations = args.max_iterations

    # Sensible default: if the chosen backend is unavailable, drop to simulate
    # so the demo always works (with a clear warning).
    llm = LLMClient(cfg)
    if cfg.backend != "simulate" and not llm.is_available():
        print(
            f"⚠️  Backend '{cfg.backend}' is not available "
            f"({'Ollama not running' if cfg.backend == 'ollama' else 'no API key'}). "
            f"Falling back to 'simulate' so the agentic workflow still runs.",
            file=sys.stderr,
        )
        cfg.backend = "simulate"
        llm = LLMClient(cfg)

    print(f"Codebase Understanding Agent")
    print(f"  Target : {target}")
    print(f"  Backend: {llm.describe()}")
    print(f"  Max iters: {cfg.max_iterations}")
    print("-" * 60)

    agent = CodebaseAgent(cfg, target, llm)
    try:
        result = agent.run()
    except LLMError as exc:
        print(f"\n❌ LLM error: {exc}", file=sys.stderr)
        print("Tip: run with --backend simulate to demo without a model.", file=sys.stderr)
        return 1

    print(f"\n✅ Agent finished in {result.iterations} step(s).")

    # Generate and save the code-linked report from real analysis + the answer.
    report = generate_report(target, result, cfg)
    path = save_report(report, target, cfg)

    verified = sum(1 for c in result.citations if c.file_exists and c.line_valid)
    print(f"   Report saved : {path}")
    print(f"   Citations    : {verified}/{len(result.citations)} verified against source")
    if result.truncated:
        print("   ⚠️  Reached the iteration limit before a final answer.")

    if args.trace:
        print("\n" + "=" * 60)
        print("AGENTIC TRACE")
        print("=" * 60)
        print(result.trace_text())
        print("\n" + "=" * 60)
        print("FINAL ANSWER")
        print("=" * 60)
        print(result.final_answer)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
