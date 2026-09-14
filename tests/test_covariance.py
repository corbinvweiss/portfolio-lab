"""Does the covariance estimator recover the structure we planted?"""
import numpy as np

from portfolio_lab.risk import covariance as cov_mod


def test_estimators_recover_planted_covariance(synth):
    prices, truth = synth
    rets = np.log(prices).diff().dropna()
    # Align: the price frame comes back in pivot (alphabetical) order, the
    # ground truth in universe order. Comparing them positionally is a bug that
    # looks exactly like a broken estimator.
    true_cov = truth["true_cov_annual"].reindex(index=rets.columns, columns=rets.columns)

    for method in ("sample", "ewma", "shrunk"):
        est = cov_mod.estimate(rets, method=method)
        # Compare annualised vols: within 25% is a generous but meaningful bar.
        est_vol = np.sqrt(np.diag(est.to_numpy()))
        true_vol = np.sqrt(np.diag(true_cov.to_numpy()))
        rel_err = np.abs(est_vol - true_vol) / true_vol
        assert rel_err.max() < 0.25, f"{method} vol error {rel_err.max():.2%}"


def test_estimates_are_psd(synth):
    prices, _ = synth
    rets = np.log(prices).diff().dropna().iloc[:60]  # short sample -> ill-conditioned
    for method in ("sample", "ewma", "shrunk"):
        est = cov_mod.estimate(rets, method=method)
        eigenvalues = np.linalg.eigvalsh(est.to_numpy())
        assert eigenvalues.min() > -1e-10, f"{method} produced a non-PSD matrix"


def test_shrinkage_beats_sample_in_small_samples(synth):
    """The reason shrinkage exists: less error when observations are scarce."""
    prices, truth = synth
    rets = np.log(prices).diff().dropna().iloc[:40]
    true_cov = truth["true_cov_annual"].reindex(
        index=rets.columns, columns=rets.columns
    ).to_numpy()

    sample_err = np.linalg.norm(cov_mod.estimate(rets, "sample").to_numpy() - true_cov)
    shrunk_err = np.linalg.norm(cov_mod.estimate(rets, "shrunk").to_numpy() - true_cov)
    assert shrunk_err < sample_err


def test_risk_contributions_sum_to_one(synth):
    import pandas as pd
    prices, _ = synth
    rets = np.log(prices).diff().dropna()
    cov = cov_mod.estimate(rets)
    w = pd.Series(1.0 / len(cov), index=cov.index)
    assert abs(cov_mod.risk_contributions(w, cov).sum() - 1.0) < 1e-9
