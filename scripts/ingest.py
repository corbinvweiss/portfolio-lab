#!/usr/bin/env python
"""Convenience wrapper: python scripts/ingest.py --start 2005-01-01"""
import sys

from portfolio_lab.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["ingest"] + sys.argv[1:]))
