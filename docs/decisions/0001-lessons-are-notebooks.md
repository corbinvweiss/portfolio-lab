# 0001. Lessons are notebooks

Date: 2026-09-30 · Week: 1 · Status: accepted

## Context

The spec (sections 1, 2, 8 and 10) made each lesson a markdown file and rejected a
notebook-first course, keeping notebooks as gitignored scratch. Working through week 1
showed the cost of that split: the exploration that produced every number lived in a
scratch notebook, and the lesson had to restate the numbers without the code that made
them. Corbin wants to run the examples and explain them in the same place.

## Decision

- A lesson is a Jupyter notebook at `docs/course/lessons/NN-topic.ipynb`, started from
  `docs/course/lesson-template.ipynb`. The template's `##` headings are markdown cells and
  stay required.
- The code that produces a number sits in the cell beneath the prose that claims it.
  Library code still lives in `src/portfolio_lab/` under TDD; a lesson imports it and
  never defines functions the rest of the course depends on.
- Notebooks are committed **with outputs**, from one Kernel > Restart & Run All, so the
  numbers are readable on GitHub without the data. Executed code cells must be numbered
  1, 2, 3... in order.
- Plots render inline and need not go to `docs/figures/`. That folder remains for images
  the README or a markdown doc references.
- `notebooks/` stays gitignored scratch for dead ends.
- Every table still cites the config, git SHA and snapshot date beside it.

## Consequences

- `tests/test_docs.py` reads lessons as JSON: required headings, numbered `.ipynb`
  filenames, and in-order execution counts. It executes nothing, so tests still never
  touch `data/`.
- The `lab` extra installs `ipykernel`; run `pip install -e ".[dev,ingest,lab]"`.
- A lesson is not reproducible from a clean checkout without `data/`: its snapshot date
  names the capture to replay with `load_prices(as_of=...)`. The committed outputs are
  the record.
- Notebook diffs are noisy. Review lessons on GitHub's rendered view, not `git diff`.
