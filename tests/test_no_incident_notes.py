"""Comments explain the rule, never the incident.

This repo is public. A comment that says what a check protects against is
documentation; one that says when it went wrong, who did what and which Sentry
issue it opened is operational history published for ever, and it belongs in
`doc/operations.md` or in Linear instead. This walks every comment, docstring,
spec, workflow, migration and template comment for the two shapes such a note
reliably has — a sentence dated to a day (a preposition, a day, a month and a
year) and a Sentry issue id — so the rule in CLAUDE.md is a test rather than a
preference. Dates in data and in content are not comments and are not scanned.
"""

import ast
import io
import os
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"venv", "node_modules", ".git", ".playwright-mcp", ".context", "__pycache__"}

MONTH = "January|February|March|April|May|June|July|August|September|October|November|December"
NARRATIVE = re.compile(
    rf"\bDINKYDASH-\d+\b"
    rf"|\b(?:on|until|since|before|after|from)\s+\d{{1,2}}\s+(?:{MONTH})\s+20\d\d\b")


def walk(suffixes, under=ROOT):
    for directory, dirnames, filenames in os.walk(under):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(suffixes):
                yield Path(directory) / name


def runs(lines):
    """Consecutive comment lines joined, so a sentence split over two lines still reads."""
    run = []
    for text in lines:
        if text is None:
            if run:
                yield " ".join(run)
            run = []
        else:
            run.append(text)
    if run:
        yield " ".join(run)


def python_notes(path):
    source = path.read_text()
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    yield from runs(
        token.string.lstrip("#").strip() if token.type == tokenize.COMMENT
        else None if token.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)
        else ""
        for token in tokens)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if doc:
                yield " ".join(doc.split())


def line_notes(path, marker):
    yield from runs(
        line.strip()[len(marker):].strip() if line.strip().startswith(marker) else None
        for line in path.read_text().splitlines())


def template_notes(path):
    for match in re.finditer(r"\{#(.*?)#\}|<!--(.*?)-->", path.read_text(), re.S):
        yield " ".join((match.group(1) or match.group(2) or "").split())


def notes():
    for path in walk((".py",)):
        yield from ((path, note) for note in python_notes(path))
    for path in list(walk((".yaml", ".yml"), ROOT / ".do")) + list(walk((".yml", ".yaml"), ROOT / ".github")) \
            + list(walk((".toml",), ROOT / ".conductor")) + list(walk((".sh",))):
        yield from ((path, note) for note in line_notes(path, "#"))
    for path in walk((".sql",), ROOT / "migrations"):
        yield from ((path, note) for note in line_notes(path, "--"))
    for path in list(walk((".html",), ROOT / "web" / "templates")) + list(walk((".html",), ROOT / "website" / "templates")):
        yield from ((path, note) for note in template_notes(path))


def test_no_dated_narrative_or_sentry_ids_in_comments():
    found = [(str(path.relative_to(ROOT)), NARRATIVE.search(note).group())
             for path, note in notes() if NARRATIVE.search(note)]
    assert not found, found
