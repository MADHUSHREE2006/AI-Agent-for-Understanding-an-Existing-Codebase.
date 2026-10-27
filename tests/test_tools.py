"""Unit tests for the agent's tools.

These run against the bundled sample project and need no LLM, so they are
fast and deterministic. Run with: ``pytest -q`` from the project root.
"""

from __future__ import annotations

import os

import pytest

from config import Config
from tools.file_explorer import find_files, get_directory_tree, read_file, list_directory
from tools.code_parser import parse_file_structure, extract_business_rule_candidates
from tools.dependency_mapper import map_dependencies
from tools.search import search_content

SAMPLE = os.path.normpath(os.path.join(os.path.dirname(__file__), "sample_project"))


# ---------------------------------------------------------------------
# File explorer
# ---------------------------------------------------------------------
def test_directory_tree_lists_sample_project():
    tree = get_directory_tree(SAMPLE, max_depth=3)
    assert "DIRECTORY TREE" in tree
    assert "library/" in tree
    assert "main.py" in tree


def test_find_files_returns_python_sources():
    result = find_files(SAMPLE, "*.py")
    assert "library/book.py" in result
    assert "main.py" in result
    assert "library/library.py" in result


def test_read_file_has_line_numbers():
    out = read_file(os.path.join(SAMPLE, "main.py"))
    assert "FILE:" in out
    # line 9 of main.py imports the library package
    assert "9 | from library import" in out


def test_list_directory_on_missing_dir_errors():
    assert "not a directory" in list_directory("does/not/exist")


# ---------------------------------------------------------------------
# Code parser
# ---------------------------------------------------------------------
def test_parse_python_extracts_classes_and_methods():
    info = parse_file_structure(os.path.join(SAMPLE, "library", "book.py"))
    assert info["language"] == "python"
    names = {c["name"] for c in info["classes"]}
    assert {"Book", "BookType"} <= names
    book = next(c for c in info["classes"] if c["name"] == "Book")
    method_names = {m["name"] for m in book["methods"]}
    assert "check_out" in method_names
    assert "return_copy" in method_names
    # check_out starts on line 25 of book.py
    assert book["line"] == 10  # class Book on line 10


def test_parse_file_records_import_level_for_relative_imports():
    info = parse_file_structure(os.path.join(SAMPLE, "library", "library.py"))
    rel_imp = next(i for i in info["imports"] if i["module"] == "book")
    assert rel_imp["kind"] == "from"
    assert rel_imp["level"] == 1  # `from .book import ...`


def test_extract_business_rule_candidates_flags_validations():
    cands = extract_business_rule_candidates(SAMPLE)
    # at least the age-negative check and the copy-availability check
    funcs = {c["function"] for c in cands}
    assert "check_out" in funcs
    assert "is_minor" in funcs
    assert "calculate_fine" in funcs
    # every candidate has a line number and a category
    for c in cands:
        assert c["line"] > 0
        assert c["category"] in ("validation", "condition", "computation")


# ---------------------------------------------------------------------
# Dependency mapper
# ---------------------------------------------------------------------
def test_map_dependencies_resolves_relative_imports():
    deps = map_dependencies(SAMPLE)
    assert "error" not in deps
    # library.py should depend on book, member, loan (relative imports)
    adj = deps["adjacency"]
    assert "library/book.py" in adj["library/library.py"]
    assert "library/member.py" in adj["library/library.py"]
    assert "library/loan.py" in adj["library/library.py"]
    # main.py depends on the package __init__
    assert "library/__init__.py" in adj["main.py"]


def test_map_dependencies_external_only_lists_real_libraries():
    deps = map_dependencies(SAMPLE)
    external = deps["external_imports"]
    # datetime is the only real external import; book/member/loan are local now
    assert "datetime" in external
    assert "book" not in external
    assert "member" not in external
    assert "loan" not in external


def test_map_dependencies_does_not_double_count_files():
    deps = map_dependencies(SAMPLE)
    assert len(deps["files"]) == 6


# ---------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------
def test_search_finds_raises():
    out = search_content(SAMPLE, r"raise ValueError")
    assert "library/book.py:32" in out
    assert "library/library.py:50" in out


def test_search_invalid_regex_returns_error():
    assert "invalid regex" in search_content(SAMPLE, "([unterminated")
