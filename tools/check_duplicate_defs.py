#!/usr/bin/env python3
"""Fail when one Python module defines the same module-level name twice.

The check intentionally follows definitions inside module-level try/if/with blocks,
because those definitions still bind names in the module namespace at import time.
It does not inspect function or class bodies.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys


IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".venv_build",
    "__pycache__",
    "build",
    "cache",
    "dist",
    "release",
    "vendor",
    "venv",
}


MODULE_CONTAINER_TYPES = (
    ast.AsyncFor,
    ast.For,
    ast.If,
    ast.Try,
    ast.While,
    ast.With,
)


def _iter_python_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in path.rglob("*.py"):
            if any(part in IGNORED_PARTS for part in child.parts):
                continue
            files.append(child)
    return sorted(set(files))


def _iter_module_definitions(nodes: list[ast.stmt]):
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno
            continue

        if isinstance(node, MODULE_CONTAINER_TYPES):
            nested: list[ast.stmt] = []
            for attr in ("body", "orelse", "finalbody"):
                nested.extend(getattr(node, attr, []) or [])
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    nested.extend(handler.body or [])
            yield from _iter_module_definitions(nested)
            continue

        if hasattr(ast, "Match") and isinstance(node, ast.Match):
            nested = []
            for case in node.cases:
                nested.extend(case.body or [])
            yield from _iter_module_definitions(nested)


def _duplicates_for_file(path: Path) -> dict[str, list[int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    definitions: dict[str, list[int]] = {}
    for name, lineno in _iter_module_definitions(tree.body):
        definitions.setdefault(name, []).append(lineno)
    return {
        name: lines
        for name, lines in definitions.items()
        if len(lines) > 1
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check duplicate module-level function/class definitions."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path(".")],
        help="Files or directories to scan. Defaults to the current directory.",
    )
    args = parser.parse_args()

    failures: list[tuple[Path, dict[str, list[int]]]] = []
    for path in _iter_python_files(args.paths):
        duplicates = _duplicates_for_file(path)
        if duplicates:
            failures.append((path, duplicates))

    if not failures:
        print("No duplicate module-level definitions found.")
        return 0

    print("Duplicate module-level definitions found:")
    for path, duplicates in failures:
        print(f"- {path}")
        for name, lines in sorted(duplicates.items(), key=lambda item: item[1][0]):
            joined = ", ".join(str(line) for line in lines)
            print(f"  {name}: lines {joined}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
