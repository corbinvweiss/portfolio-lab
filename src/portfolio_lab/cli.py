"""Command line entry point: `plab run`, `plab ingest`, `plab ingest-rates`, `plab snapshots`."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from .data.store import ParquetDuckStore
from .data.universe import SLEEVES, TICKERS, Universe
from .experiment import load_config, run_experiment
from .report.tearsheet import build_tearsheet, metrics_table
from .risk import covariance as cov_mod

DEFAULT_SERIES = "DTB3"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plab", description="portfolio-lab")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run a backtest from a config file")
    run_p.add_argument("--config", default="configs/baseline.yaml")
    run_p.add_argument("--outdir", default="runs")
    run_p.add_argument("--no-chart", action="store_true")

    ing_p = sub.add_parser("ingest", help="fetch prices and write a snapshot")
    ing_p.add_argument("--start", default="2005-01-01")
    ing_p.add_argument("--end", default=None)
    ing_p.add_argument("--universe", default=None, help="path to csv universe of assets")

    ing_r = sub.add_parser("ingest-rates", help="fetch rates and write a snapshot")
    ing_r.add_argument("--series", default=DEFAULT_SERIES)
    ing_r.add_argument("--start", default="2015-01-01")

    diff_p = sub.add_parser("diff-snapshots", help="diff snapshots between two dates")
    diff_p.add_argument("earlier", type=date.fromisoformat)
    diff_p.add_argument("later", type=date.fromisoformat)

    sub.add_parser("snapshots", help="list captured snapshots")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        from .data.ingest import ingest
        tickers = Universe.from_csv(path=args.universe).tickers if args.universe else TICKERS
        path, df = ingest(ParquetDuckStore(), tickers, start=args.start, end=args.end)
        print(f"wrote {path}  ({len(df):,} rows, {df['ticker'].nunique()} tickers)")
        return 0

    if args.command == "ingest-rates":
        from .data.ingest import ingest_rates
        path, df = ingest_rates(ParquetDuckStore(), series_id=args.series, start=args.start)
        print(f"wrote {path} ({len(df):,} rows)")
        return 0

    if args.command == "snapshots":
        for d in ParquetDuckStore().snapshots():
            print(d.isoformat())
        return 0

    if args.command == "diff-snapshots":
        from .data.snapshots import snapshot_diff
        df = snapshot_diff(ParquetDuckStore(), args.earlier, args.later)
        print(df.to_string(index=False))
        print(f"{len(df)} restated rows between {args.earlier} and {args.later}")
        return 0

    cfg = load_config(args.config)
    results = run_experiment(cfg)

    table = metrics_table(results)
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    print(f"\n{cfg.get('name', 'run')}\n{'-' * 72}")
    print(table.to_string())

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    table.to_csv(outdir / f"{cfg.get('name', 'run')}_metrics.csv")

    if not args.no_chart:
        from .experiment import load_prices
        prices = load_prices(cfg)
        rets = prices.pct_change().dropna()
        cov = cov_mod.estimate(rets.iloc[-cfg["risk"].get("cov_window", 252):])
        out = build_tearsheet(
            results, sleeve_map=SLEEVES, cov=cov,
            title=f"{cfg.get('name', 'run')}  ·  target vol {cfg['budget']['target_vol']:.0%}",
            outfile=outdir / f"{cfg.get('name', 'run')}_tearsheet.png",
        )
        print(f"\nchart: {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
