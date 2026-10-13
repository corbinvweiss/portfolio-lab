"""Documentation hygiene.

Cheap checks that stop the docs drifting: every lesson notebook carries the template's
headings, every lesson and primer notebook was run top to bottom, and every relative link
in the syllabus points at a file that exists. Notebooks are read as JSON; nothing is executed, so no data is needed.
"""
import json
import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs"
LESSONS = DOCS / "course" / "lessons"
PRIMERS = DOCS / "course" / "primers"
TEMPLATE = DOCS / "course" / "lesson-template.ipynb"
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
    return sorted(LESSONS.glob("*.ipynb")) if LESSONS.exists() else []


def _primers() -> list[Path]:
    return sorted(PRIMERS.glob("*.ipynb")) if PRIMERS.exists() else []


def _cells(nb: Path, kind: str) -> list[dict]:
    return [c for c in json.loads(nb.read_text())["cells"] if c["cell_type"] == kind]


def _markdown(nb: Path) -> str:
    return "\n".join("".join(c["source"]) for c in _cells(nb, "markdown"))


@pytest.mark.parametrize("lesson", [TEMPLATE, *_lessons()], ids=lambda p: p.name)
def test_lesson_has_template_headings(lesson: Path):
    lines = set(_markdown(lesson).splitlines())
    missing = [h for h in REQUIRED_HEADINGS if h not in lines]
    assert not missing, f"{lesson.name} is missing headings: {missing}"


@pytest.mark.parametrize("folder", [LESSONS, PRIMERS], ids=lambda p: p.name)
def test_notebook_filenames_are_numbered(folder: Path):
    for p in folder.iterdir() if folder.exists() else []:
        assert re.match(r"^\d{2}[a-z]?-[a-z0-9-]+\.ipynb$", p.name), p.name


@pytest.mark.parametrize("lesson", [*_lessons(), *_primers()], ids=lambda p: p.name)
def test_notebook_was_run_top_to_bottom(lesson: Path):
    """Executed code cells must be numbered 1, 2, 3... in order: Restart & Run All.

    Out-of-order or skipped counts mean the outputs came from a kernel whose state no
    longer matches the cells above them, so the numbers are not reproducible.
    """
    counts = [c["execution_count"] for c in _cells(lesson, "code") if "".join(c["source"]).strip()]
    ran = [n for n in counts if n is not None]
    if not ran:
        return  # nothing executed yet
    assert counts == list(range(1, len(counts) + 1)), (
        f"{lesson.name} execution counts {counts}: restart the kernel and run all cells"
    )


def test_syllabus_links_resolve():
    text = SYLLABUS.read_text()
    broken = []
    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "#")):
            continue
        if not (SYLLABUS.parent / target.split("#")[0]).exists():
            broken.append(target)
    assert not broken, f"broken links in SYLLABUS.md: {broken}"


def test_figures_are_referenced_by_a_document():
    figures = DOCS / "figures"
    if not figures.exists():
        return
    documents = [*DOCS.rglob("*.md"), DOCS.parent / "README.md"]
    corpus = "\n".join(p.read_text() for p in documents)
    corpus += "\n".join(_markdown(p) for p in _lessons())
    unreferenced = [p.name for p in figures.glob("*.png") if p.name not in corpus]
    assert not unreferenced, f"figures no document references: {unreferenced}"
