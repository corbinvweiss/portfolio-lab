# Glossary

Terms as used in this repo. Add an entry the first week a term appears in a lesson; keep
each to two or three sentences and link the lesson that introduced it.

- **Adjusted close.** A vendor price series rescaled so that compounding it reproduces a
  total-return index. Restated every time a dividend is paid. Not a price. (Week 1)
- **Annualised.** Scaled from the observation frequency to per-year. Vol scales by the
  square root of periods; the covariance boundary in this repo is always annualised. (Week 1)
- **As-of / point-in-time.** The data as it looked on a given date, reconstructed by
  replaying only snapshots captured on or before that date. (Week 1)
- **Lookahead.** Any use, at decision time t, of information not available at t. The
  engine's pending-order convention and the truncation test are the two defences. (Week 2)
- **Risk budget.** The constraint side of allocation: a target vol, a gross cap, per-asset
  boxes, and optionally a per-sleeve share of total risk. (Week 4)
- **Sleeve.** A group of assets treated as one exposure for budgeting and attribution:
  equity, duration, credit, real_asset. (Week 1)
- **Snapshot.** One dated, append-only capture of a vendor's data. Never overwritten. (Week 1)
- **Survivorship bias.** Evaluating a strategy on the assets that exist today rather than
  the assets that existed at each decision date. (Week 5)
- **View.** A signal's opinion about an asset, cross-sectionally standardised. Signals emit
  views; allocators turn views into weights. (Week 6)
