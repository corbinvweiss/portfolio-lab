# portfolio-lab

A twelve-week, build-it-yourself course in institutional portfolio management, and the
research tool that comes out of it. The code is rebuilt and extended week by week; the
durable output is the written lessons.

```
prices -> signals -> covariance -> risk budget -> weights -> backtest -> attribution
```

By the end the tool ingests survivorship-free equity, bond and international data into
point-in-time snapshots, runs backtests that are structurally protected against lookahead
and report overfitting-adjusted statistics, models financing and basic derivatives, and
recommends exposures for a chosen risk level under three framings.

**Start here:** [docs/SYLLABUS.md](docs/SYLLABUS.md) links every week's brief and lesson.
The design rationale is in [docs/specs](docs/specs/2026-09-14-portfolio-lab-course-design.md).
The code as it stood before week 1 is described in
[docs/reference/starting-point.md](docs/reference/starting-point.md).

## Quick start

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev,ingest]"

.venv/bin/plab run --config configs/synthetic.yaml   # no data or network needed
.venv/bin/python -m pytest
```

Real data requires ingestion first; each week's brief says what to ingest and from where.

## Layout

```
configs/       run YAMLs and universe CSVs
src/           the package (see CLAUDE.md for commands, invariants, extension points)
tests/         the code's tests plus a documentation hygiene test
docs/          syllabus, weekly briefs and lessons, specs, decisions, reference, figures
data/, runs/   gitignored; the ingestion scripts are the reproducible artifact
```
