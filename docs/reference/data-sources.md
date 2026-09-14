# Working notes

## Data access

Some sandboxed environments block finance endpoints at the egress proxy
(`stooq.com`, `query1/2.finance.yahoo.com`, `fred.stlouisfed.org`,
`www.federalreserve.gov` and `markets.newyorkfed.org` have all been seen
returning 403 at CONNECT). Ingestion is therefore a separate step designed to
run wherever the network allows, writing a snapshot that the rest of the
pipeline reads offline.

If you cannot reach a vendor at all, `configs/synthetic.yaml` exercises every
code path without any network.

## Macro data, if you want to add macro signals

- **FRED** (`api.stlouisfed.org/fred/`) is the practical front door to most Fed
  series. Free API key, generous limits, and it re-publishes the Board's own
  releases. `pip install fredapi`.
- **Board of Governors Data Download Program**
  (`federalreserve.gov/datadownload/`) serves the primary releases as CSV/XML —
  Z.1 financial accounts, H.6 money stock, H.8 bank balance sheets, H.4.1
  reserve balances. It is a bulk download interface, not a REST API.
- **NY Fed markets API** (`markets.newyorkfed.org/api/`) is the genuinely
  high-frequency one: SOFR, repo and reverse-repo operations, primary dealer
  positions. No key required.
- **Treasury Fiscal Data** (`api.fiscaldata.treasury.gov`) publishes the Daily
  Treasury Statement — actual daily cash flows in and out of the TGA.

Note the frequency trap: the Z.1 "flow of funds" is **quarterly with roughly a
ten-week lag**. It is the right source for structural questions and the wrong
source for anything resembling a trading signal. The weekly H.4.1/H.8 and the
daily NY Fed series are where the timeliness is.
