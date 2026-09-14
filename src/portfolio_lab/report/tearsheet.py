"""Comparison tearsheet: one figure, four panels, N allocators.

Deliberate choices worth copying into your own charts:
  - one y-axis per panel, never two
  - equity indexed to 100 so the three allocators are directly comparable
  - direct end-of-line labels in addition to the legend, so identity survives
    printing, colour-blindness and low contrast
  - weights aggregated to sleeves, because a twelve-colour stacked area is
    unreadable; past ~8 categories you aggregate or facet
  - a 2px surface-coloured gap between stacked fills so segments separate
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from ..backtest.metrics import drawdown_series
from ..risk.covariance import risk_contributions
from .style import CATEGORICAL, GRID, SURFACE, TEXT_MUTED, TEXT_SECONDARY, apply_style


def build_tearsheet(
    results: dict,
    sleeve_map: dict[str, str] | None = None,
    cov: pd.DataFrame | None = None,
    focus: str | None = None,
    title: str = "Signals + risk budget",
    outfile: str | Path = "runs/tearsheet.png",
) -> Path:
    apply_style()
    names = list(results)
    focus = focus or names[0]
    colors = {n: CATEGORICAL[i] for i, n in enumerate(names)}

    fig, axes = plt.subplots(2, 2, figsize=(13, 8.2))
    fig.suptitle(title, x=0.045, y=0.975, ha="left", fontsize=14, fontweight="semibold")

    _equity_panel(axes[0, 0], results, colors)
    _drawdown_panel(axes[0, 1], results, colors)
    _weights_panel(axes[1, 0], results[focus], sleeve_map, focus)
    _risk_panel(axes[1, 1], results[focus], cov, focus)

    fig.tight_layout(rect=(0.0, 0.015, 1.0, 0.945))
    out = Path(outfile)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def _equity_panel(ax, results, colors) -> None:
    ax.set_title("Growth of 100, net of costs")
    ends = {}
    for name, res in results.items():
        eq = 100 * res.equity
        ax.plot(eq.index, eq.values, color=colors[name], label=name.replace("_", " "))
        ends[name] = (eq.index[-1], float(eq.iloc[-1]))

    ax.set_ylabel("index")
    ax.margins(x=0.20)
    # Direct labels at the line ends - the relief that keeps low-contrast hues
    # legible. Strategies that finish close together would overprint, so spread
    # the label positions vertically while leaving the lines where they are.
    _labelled_ends(ax, ends, colors)
    ax.legend(loc="upper left", ncols=len(results))
    _clean(ax)


def _labelled_ends(ax, ends: dict, colors: dict, min_gap_frac: float = 0.062) -> None:
    """Place one label per series at its final value, de-colliding vertically."""
    lo, hi = ax.get_ylim()
    span = hi - lo
    if span <= 0:
        return
    min_gap = span * min_gap_frac

    items = sorted(ends.items(), key=lambda kv: kv[1][1])
    placed: list[float] = []
    for _, (_, value) in items:
        y = value if not placed else max(value, placed[-1] + min_gap)
        placed.append(y)

    for (name, (x, value)), y in zip(items, placed):
        # Anchor the TEXT at the de-collided y, not at the raw value - that is
        # the whole point of computing `placed`.
        ax.annotate(
            f"{name.replace('_', ' ')}  {value:,.0f}",
            xy=(x, y), xytext=(10, 0), textcoords="offset points",
            va="center", ha="left", fontsize=8.5, color=TEXT_SECONDARY,
            annotation_clip=False,
        )
        if abs(y - value) > min_gap * 0.2:
            # Leader line so a nudged label still points at its series.
            ax.annotate(
                "", xy=(x, value), xytext=(x, y), textcoords="data",
                arrowprops=dict(arrowstyle="-", color=colors[name], linewidth=0.8, alpha=0.7),
            )


def _drawdown_panel(ax, results, colors) -> None:
    ax.set_title("Drawdown")
    worst = None
    for name, res in results.items():
        dd = 100 * drawdown_series(res.returns)
        ax.plot(dd.index, dd.values, color=colors[name], label=name.replace("_", " "))
        if worst is None or dd.min() < worst[1]:
            worst = (dd.idxmin(), float(dd.min()), name)

    # Annotate only the single deepest trough. Labelling every series here
    # produced overlapping text for no extra information - the table carries
    # per-strategy max drawdown already.
    if worst is not None:
        trough, value, name = worst
        # Flip the label inward when the trough sits in the right half, so the
        # text never runs off the axes.
        x0, x1 = ax.get_xlim()
        right_half = ax.convert_xunits(trough) > (x0 + x1) / 2
        ax.annotate(
            f"worst: {name.replace('_', ' ')} {value:.1f}%",
            xy=(trough, value),
            xytext=(-8, 12) if right_half else (8, 12),
            textcoords="offset points",
            ha="right" if right_half else "left",
            fontsize=8.5, color=TEXT_SECONDARY,
        )
    ax.set_ylabel("percent from peak")
    ax.axhline(0, color=GRID, linewidth=1.0)
    ax.margins(y=0.16)
    ax.legend(loc="lower left", ncols=len(results))
    _clean(ax)


def _weights_panel(ax, res, sleeve_map, focus) -> None:
    ax.set_title(f"Allocation by sleeve  ·  {focus.replace('_', ' ')}")
    w = res.weights
    if sleeve_map:
        grouped = w.T.groupby(lambda t: sleeve_map.get(t, "other")).sum().T
    else:
        grouped = w
    grouped = grouped.reindex(sorted(grouped.columns), axis=1)
    # Downsample for display. At daily resolution the fill boundaries turn into
    # visual noise and the separator stroke stops separating anything.
    if len(grouped) > 400:
        grouped = grouped.resample("W-FRI").last().dropna(how="all")

    ax.stackplot(
        grouped.index,
        [grouped[c].values for c in grouped.columns],
        labels=[c.replace("_", " ") for c in grouped.columns],
        colors=CATEGORICAL[: len(grouped.columns)],
        edgecolor=SURFACE, linewidth=0.8,  # surface gap between stacked fills
    )
    ax.set_ylabel("weight")
    ax.set_ylim(0, max(1.0, float(grouped.sum(axis=1).max()) * 1.05))
    ax.legend(loc="upper left", ncols=min(4, len(grouped.columns)))
    _clean(ax)


def _risk_panel(ax, res, cov, focus) -> None:
    ax.set_title(f"Share of portfolio risk  ·  {focus.replace('_', ' ')}")
    if res.targets.empty:
        ax.text(0.5, 0.5, "no rebalances", ha="center", va="center", color=TEXT_MUTED)
        _clean(ax)
        return

    latest = res.targets.iloc[-1]
    if cov is not None:
        rc = risk_contributions(latest, cov).sort_values()
        xlabel = "percent of total risk"
    else:
        rc = (latest / latest.abs().sum()).sort_values()
        xlabel = "percent of capital (no covariance supplied)"

    ax.barh(rc.index, rc.values * 100, color=CATEGORICAL[0], height=0.62)
    for ticker, value in rc.items():
        ax.annotate(
            f"{value * 100:.1f}%", xy=(value * 100, ticker), xytext=(4, 0),
            textcoords="offset points", va="center", fontsize=8.5, color=TEXT_SECONDARY,
        )
    ax.set_xlabel(xlabel)
    ax.margins(x=0.20)
    ax.grid(axis="y", visible=False)
    _clean(ax)


def _clean(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def metrics_table(results: dict) -> pd.DataFrame:
    """The table view -- required relief whenever chart contrast is marginal,
    and the thing you will actually read anyway."""
    rows = {name: res.metrics for name, res in results.items()}
    df = pd.DataFrame(rows).T
    cols = [
        "cagr", "ann_vol", "sharpe", "max_drawdown", "calmar",
        "ann_turnover", "avg_gross", "hit_rate",
    ]
    return df[[c for c in cols if c in df.columns]]
