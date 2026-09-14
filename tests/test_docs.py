"""Documentation hygiene.

Two cheap checks that stop the docs drifting: every lesson carries the template's
headings, and every relative link in the syllabus points at a file that exists.
"""
import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs"
LESSONS = DOCS / "course" / "lessons"
SYLLABUS = DOCS / "SYLLABUS.md"

REQUIRED_HEADINGS = [
    "## The question this lesson answers",
    "## Concept and derivation",
    "## The experiment",
    "## What the numbers showed",
    "## What went wrong and what I'd do differently",
    "## Pitfalls to remember",
    "## Reading",
]

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _lessons() -> list[Path]:
    return sorted(LESSONS.glob("*.md")) if LESSONS.exists() else []


@pytest.mark.parametrize("lesson", _lessons(), ids=lambda p: p.name)
def test_lesson_has_template_headings(lesson: Path):
    text = lesson.read_text()
    missing = [h for h in REQUIRED_HEADINGS if h not in text]
    assert not missing, f"{lesson.name} is missing headings: {missing}"


def test_lesson_filenames_are_numbered():
    for p in _lessons():
        assert re.match(r"^\d{2}[a-z]?-[a-z0-9-]+\.md$", p.name), p.name


def test_syllabus_links_resolve():
    text = SYLLABUS.read_text()
    broken = []
    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "#")):
            continue
        if not (SYLLABUS.parent / target.split("#")[0]).exists():
            broken.append(target)
    assert not broken, f"broken links in SYLLABUS.md: {broken}"


def test_figures_are_referenced_by_a_lesson_or_readme():
    figures = DOCS / "figures"
    if not figures.exists():
        return
    corpus = "\n".join(p.read_text() for p in _lessons())
    corpus += (DOCS.parent / "README.md").read_text()
    unreferenced = [p.name for p in figures.glob("*.png") if p.name not in corpus]
    assert not unreferenced, f"figures no document references: {unreferenced}"
