"""Glossary term check (ticket agent-gates/06).

Docstrings and comments in the package and tests must not use the curated
avoided terms below. Each one sits on an `_Avoid_:` line in GLOSSARY.md, and
the glossary names the term to use instead. Identifiers and string data are
not scanned. The list is short on purpose: only terms with a history of drift
in review, so ordinary words from the `_Avoid_:` lines are not flagged.
"""

import ast
import io
import re
import textwrap
import tokenize
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = ROOT / "GLOSSARY.md"
SCANNED_DIRS = (ROOT / "src" / "denoisifier", ROOT / "tests")

# Terms caught in review (01 F2, 02 S1, spec failure mode 6). Each must stay on an
# `_Avoid_:` line in GLOSSARY.md; test_curated_terms_are_avoided_in_the_glossary enforces it.
CURATED = ("orientation", "amplitude", "wavelength", "false positive")


class Hit(NamedTuple):
    path: str
    line: int
    term: str
    use: str

    def __str__(self) -> str:
        return (
            f'{self.path}:{self.line}: "{self.term}" is avoided in GLOSSARY.md; '
            f'use "{self.use}" instead'
        )


def avoided_terms(glossary: str) -> dict[str, str]:
    """Map each avoided term (lower case) to the glossary term it stands in for."""
    avoided: dict[str, str] = {}
    current = None
    for raw in glossary.splitlines():
        line = raw.strip()
        if heading := re.fullmatch(r"\*\*(.+?)\*\*:", line):
            current = heading.group(1)
        elif line.startswith("_Avoid_:") and current is not None:
            for term in line.removeprefix("_Avoid_:").split(","):
                avoided[term.strip().lower()] = current
    return avoided


def _pattern(term: str) -> re.Pattern[str]:
    words = r"\s+".join(re.escape(w) for w in term.split())
    return re.compile(rf"\b{words}(?:s|es)?\b", re.IGNORECASE)


def _prose(source: str) -> list[tuple[int, str]]:
    """Docstring and comment text in `source`, each as (first line, text).

    Bare string statements (module, class, function and attribute docstrings) are
    taken as raw source so line numbers are exact. Consecutive comment lines are
    joined, so a term split across two comment lines is still found.
    """
    blocks: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            segment = ast.get_source_segment(source, node.value)
            if segment is not None:
                blocks.append((node.lineno, segment))
    start, text, last = 0, [], -1
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type != tokenize.COMMENT:
            continue
        row = tok.start[0]
        if row != last + 1 and text:
            blocks.append((start, "\n".join(text)))
            text = []
        if not text:
            start = row
        text.append(tok.string.lstrip("#"))
        last = row
    if text:
        blocks.append((start, "\n".join(text)))
    return blocks


def scan(source: str, path: str, terms: dict[str, str]) -> list[Hit]:
    hits = []
    for first, text in _prose(source):
        for term, use in terms.items():
            for match in _pattern(term).finditer(text):
                line = first + text.count("\n", 0, match.start())
                hits.append(Hit(path, line, term, use))
    return sorted(hits)


def curated_terms() -> dict[str, str]:
    avoided = avoided_terms(GLOSSARY.read_text(encoding="utf-8"))
    return {term: avoided[term] for term in CURATED if term in avoided}


def test_curated_terms_are_avoided_in_the_glossary():
    avoided = avoided_terms(GLOSSARY.read_text(encoding="utf-8"))
    missing = [term for term in CURATED if term not in avoided]
    assert not missing, (
        f"CURATED in {Path(__file__).name} lists {missing}, which no `_Avoid_:` line in "
        "GLOSSARY.md names. Keep the list in step with the glossary."
    )


def test_docstrings_and_comments_use_glossary_terms():
    terms = curated_terms()
    hits = []
    for directory in SCANNED_DIRS:
        for path in sorted(directory.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            hits += scan(path.read_text(encoding="utf-8"), rel, terms)
    assert not hits, (
        f"{len(hits)} avoided glossary term(s) in docstrings or comments:\n"
        + "\n".join(f"  {h}" for h in hits)
    )


def test_the_scan_covers_the_package_and_tests():
    scanned = {p.name for d in SCANNED_DIRS for p in d.rglob("*.py")}
    assert {"analysis.py", "synthetic.py", "conftest.py", Path(__file__).name} <= scanned


TERMS = {"orientation": "Angle", "false positive": "False Alarm"}

PLANT = textwrap.dedent(
    '''
    """Module text: Orientation here."""
    orientation = "orientation in data"


    def f(orientation):
        """Line one.

        The orientations of stripes.
        """
        return {"orientation": orientation}  # a false
        # positive across comment lines


    class C:
        x = 1
        """Attribute text: orientation."""
    '''
)


def test_scan_flags_docstrings_and_comments_only():
    assert scan(PLANT, "p.py", TERMS) == [
        Hit("p.py", 2, "orientation", "Angle"),
        Hit("p.py", 9, "orientation", "Angle"),
        Hit("p.py", 11, "false positive", "False Alarm"),
        Hit("p.py", 17, "orientation", "Angle"),
    ]


def test_hit_message_names_file_line_term_and_replacement():
    assert str(Hit("p.py", 3, "orientation", "Angle")) == (
        'p.py:3: "orientation" is avoided in GLOSSARY.md; use "Angle" instead'
    )


def test_glossary_parse_maps_avoided_terms_to_their_entry():
    text = "**Angle**:\nThe tilt.\n_Avoid_: orientation, Tilt Angle\n\n**Period**:\nx\n"
    assert avoided_terms(text) == {"orientation": "Angle", "tilt angle": "Angle"}
