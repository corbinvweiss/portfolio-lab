# portfolio-lab

A twelve-week, self-directed course in institutional portfolio management, worked
through by building the research tool one week at a time. Corbin Weiss is the student
and the author of every lesson. The code is the exercise; the written lessons are the
point.

```
prices -> signals -> covariance -> risk budget -> weights -> backtest -> attribution
```

By the end the tool ingests equity, bond and international data into point-in-time
snapshots (the data exactly as it was known on a given date, including companies that
later delisted, so results are not flattered by survivorship bias), runs backtests that
are structurally protected against lookahead (no decision can see a price from its own
future), reports statistics adjusted for how many strategies were tried, models financing
and basic derivatives, and recommends exposures for a chosen risk level under three
framings.

**Status, October 2026:** the week 1 tools are built and its lesson is in progress; the
remaining weeks are planned in the syllabus and marked pending until their lesson is written.

## How the course works

Each week follows the same three steps.

1. **Claude writes the brief.** Claude, Anthropic's AI model, acts as the instructor. It
   writes the week's brief: the concept, the mathematics derived rather than cited, the
   reading, and the acceptance tests the implementation must pass. Briefs live in
   [docs/course/briefs](docs/course/briefs).
2. **Corbin implements the tools.** Every line of the package in `src/` is written by
   Corbin, under test-driven development, against the brief's acceptance tests. Claude
   reviews the implementation and probes understanding before the week moves on.
3. **Corbin runs the experiments and writes the lesson.** Using the tools just built,
   Corbin runs the week's experiments in a notebook and writes up what the numbers
   showed, what went wrong, and what to remember. That notebook is the lesson, and the
   week is done when it is written. Lessons live in
   [docs/course/lessons](docs/course/lessons).

The split is deliberate. An instructor can hand over a derivation and a test suite, but
the understanding only arrives by typing the implementation and watching the experiment
run. The design rationale, including the decision to rebuild the pre-existing engine
rather than extend it, is in the
[course spec](docs/specs/2026-09-14-portfolio-lab-course-design.md).

## Reading this as a visitor

Nothing needs to be installed or run. GitHub renders the notebooks with their saved
outputs.

1. Start with [docs/SYLLABUS.md](docs/SYLLABUS.md), which lays out the four phases and
   links every week's brief and lesson.
2. Read a lesson. [Lesson 1: data integrity and return math](docs/course/lessons/01-data-integrity.ipynb)
   is the worked example: the prose and the code that produced its numbers sit together,
   run top to bottom.
3. If you want to see the assignment behind a lesson, open the matching brief, for example
   [brief 1](docs/course/briefs/01-data-integrity.md).
4. [docs/reference/starting-point.md](docs/reference/starting-point.md) describes the code
   as it stood before week 1, which later weeks rebuild and use as an oracle.

The [glossary](docs/reference/glossary.md) and [reading list](docs/reference/reading-list.md)
cover the terms and sources the lessons lean on.

## Running it yourself

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev,ingest]"

.venv/bin/plab run --config configs/synthetic.yaml   # no data or network needed
.venv/bin/python -m pytest
```

Real data requires ingestion first; each week's brief says what to ingest and from where.

### Layout

```
configs/       run YAMLs and universe CSVs
src/           the package (see CLAUDE.md for commands, invariants, extension points)
tests/         the code's tests plus a documentation hygiene test
docs/          syllabus, weekly briefs and lessons, specs, decisions, reference, figures
data/, runs/   gitignored; the ingestion scripts are the reproducible artifact
```
