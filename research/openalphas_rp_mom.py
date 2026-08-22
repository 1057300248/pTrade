"""Research-only reproduction of the OpenAlphas risk-parity ETF rotator.

The engine deliberately has no dependency on any live ``ptrade_*.py`` module.
Signals and fills both use the rebalance day's close, matching the article.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from typing import Any, Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ArticleParams:
    start_date: str = "2018-01-01"
    end_date: str = "2024-03-31"
    initial_cash: float = 100_000.0
    volatility_threshold: tuple[float, float] = (0.08, 0.28)
    corr_window: int = 500
    vol_window: int = 250
    momentum_window: int = 20
    rebalance_freq: str = "W-FRI"
    top_n_corr: int = 5
    top_n_momentum: int = 2
    transaction_cost: float = 0.001
    min_trade: float = 10.0


DEFAULT_PARAMS = asdict(ArticleParams())


def _coerce_params(params: Mapping[str, Any] | ArticleParams | None) -> dict[str, Any]:
    result = dict(DEFAULT_PARAMS)
    if params is None:
        return result
    if isinstance(params, ArticleParams):
        result.update(asdict(params))
    else:
        result.update(dict(params))
    return result


def _clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        raise ValueError("prices must be a non-empty DataFrame")
    clean = prices.copy()
    clean.index = pd.DatetimeIndex(pd.to_datetime(clean.index)).tz_localize(None)
    clean = clean.apply(pd.to_numeric, errors="coerce")
    clean = clean.sort_index().loc[~clean.index.duplicated(keep="last")]
    clean = clean.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if clean.empty or (clean <= 0.0).any().any():
        raise ValueError("prices must contain aligned, finite, positive closes")
    return clean.astype(float)


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Return unfilled close-to-close returns for the supplied price history."""
    return prices.astype(float).pct_change(fill_method=None)


def annualized_volatility(returns: pd.DataFrame | pd.Series) -> pd.Series | float:
    """Annualize the sample standard deviation of returns using 252 sessions."""
    result = returns.std(ddof=1) * sqrt(252.0)
    if isinstance(result, pd.Series):
        return result
    return float(result)


def trailing_annualized_volatility(
    returns: pd.DataFrame, window: int
) -> pd.DataFrame:
    """Annualized rolling volatility; each row uses that row and earlier rows."""
    return returns.rolling(int(window), min_periods=int(window)).std(ddof=1) * sqrt(
        252.0
    )


def mean_absolute_correlation(returns: pd.DataFrame) -> pd.Series:
    """Mean absolute correlation with all other names, excluding the diagonal."""
    if returns.shape[1] < 2:
        return pd.Series(np.nan, index=returns.columns, dtype=float)
    corr = returns.corr().abs()
    corr = corr.mask(np.eye(len(corr), dtype=bool))
    return corr.mean(axis=1, skipna=True)


def momentum_score(closes: pd.Series | np.ndarray) -> tuple[float, float]:
    """Return the article's annualized log-trend score and its regression R²."""
    values = np.asarray(closes, dtype=float).reshape(-1)
    if values.size < 2 or not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        return float("nan"), float("nan")

    t = np.arange(values.size, dtype=float)
    log_prices = np.log(values)
    centered_t = t - t.mean()
    centered_log = log_prices - log_prices.mean()
    denominator = float(np.sum(centered_t * centered_t))
    beta = float(np.sum(centered_t * centered_log) / denominator)
    fitted = log_prices.mean() + beta * centered_t
    residual_ss = float(np.sum((log_prices - fitted) ** 2))
    total_ss = float(np.sum(centered_log**2))
    r_squared = 0.0 if total_ss == 0.0 else 1.0 - residual_ss / total_ss
    score = float(np.expm1(beta * 252.0) * r_squared)
    return score, r_squared


def filter_by_volatility(
    volatilities: pd.Series, thresholds: tuple[float, float]
) -> pd.Series:
    """Keep finite annual volatilities inside the inclusive article bounds."""
    low, high = (float(thresholds[0]), float(thresholds[1]))
    numeric = pd.to_numeric(volatilities, errors="coerce")
    return numeric[numeric.notna() & numeric.between(low, high, inclusive="both")]


def inverse_volatility_weights(volatilities: pd.Series) -> pd.Series:
    """Normalize inverse positive volatility to fully invested target weights."""
    numeric = pd.to_numeric(volatilities, errors="coerce")
    if numeric.empty or numeric.isna().any() or (numeric <= 0.0).any():
        raise ValueError("volatilities must be finite and positive")
    inverse = 1.0 / numeric
    return inverse / inverse.sum()


def build_rebalance_signal(
    prices: pd.DataFrame,
    as_of: str | pd.Timestamp,
    params: Mapping[str, Any] | ArticleParams | None = None,
) -> dict[str, Any] | None:
    """Build one signal using only closes at or before ``as_of``.

    ``None`` means the article's fewer-than-five guard fired (or an indicator
    did not have enough complete history), so existing holdings must be kept.
    """
    cfg = _coerce_params(params)
    history = _clean_prices(prices)
    history = history.loc[: pd.Timestamp(as_of)]
    if history.empty:
        return None

    returns = daily_returns(history)
    vol_window = int(cfg["vol_window"])
    if len(returns) < vol_window + 1:
        return None
    vol = annualized_volatility(returns.tail(vol_window))
    survivors = filter_by_volatility(vol, tuple(cfg["volatility_threshold"]))
    top_n_corr = int(cfg["top_n_corr"])
    if len(survivors) < top_n_corr:
        return None

    corr_window = int(cfg["corr_window"])
    survivor_returns = returns.loc[:, survivors.index].dropna(how="any")
    if len(survivor_returns) < corr_window:
        return None
    correlations = mean_absolute_correlation(survivor_returns.tail(corr_window))
    correlations = correlations.dropna()
    if len(correlations) < top_n_corr:
        return None
    low_corr = correlations.nsmallest(top_n_corr, keep="first").index.tolist()

    momentum_window = int(cfg["momentum_window"])
    if len(history) < momentum_window:
        return None
    scores: dict[str, float] = {}
    r_squared: dict[str, float] = {}
    for ticker in low_corr:
        score, r2 = momentum_score(history[ticker].tail(momentum_window))
        if np.isfinite(score):
            scores[ticker] = score
            r_squared[ticker] = r2
    top_n_momentum = int(cfg["top_n_momentum"])
    if len(scores) < top_n_momentum:
        return None
    ranked = pd.Series(scores, dtype=float).nlargest(
        top_n_momentum, keep="first"
    )
    selected = ranked.index.tolist()
    weights = inverse_volatility_weights(vol.loc[selected])
    return {
        "as_of": history.index[-1],
        "volatility": vol,
        "survivors": survivors.index.tolist(),
        "mean_abs_correlation": correlations,
        "low_correlation": low_corr,
        "momentum_scores": pd.Series(scores, dtype=float),
        "momentum_r_squared": pd.Series(r_squared, dtype=float),
        "selected": selected,
        "weights": weights,
    }


def performance_metrics(values: pd.Series) -> dict[str, float]:
    """Compute the exact CAGR, drawdown and daily Sharpe formulas requested."""
    series = pd.Series(values, dtype=float).dropna()
    if series.empty:
        raise ValueError("portfolio values are empty")
    n_bars = len(series)
    cagr = float((series.iloc[-1] / series.iloc[0]) ** (252.0 / n_bars) - 1.0)
    max_drawdown = float((series / series.cummax() - 1.0).min())
    returns = series.pct_change(fill_method=None).dropna()
    standard_deviation = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = (
        float(returns.mean() / standard_deviation * sqrt(252.0))
        if standard_deviation > 0.0
        else 0.0
    )
    return {
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "final_value": float(series.iloc[-1]),
        "n_bars": int(n_bars),
    }


def _trade_to_target(
    date: pd.Timestamp,
    row: pd.Series,
    cash: float,
    positions: dict[str, float],
    weights: pd.Series,
    portfolio_value: float,
    transaction_cost: float,
    min_trade: float,
) -> tuple[float, dict[str, float], list[dict[str, Any]]]:
    target_names = set(weights.index)
    trades: list[dict[str, Any]] = []

    # Article order: liquidate non-targets first.
    for ticker in list(positions):
        if ticker in target_names:
            continue
        price = float(row[ticker])
        notional = float(positions[ticker] * price)
        if abs(notional) < min_trade:
            continue
        shares = positions.pop(ticker)
        cash += notional * (1.0 - transaction_cost)
        trades.append(
            {
                "date": date,
                "ticker": ticker,
                "side": "SELL",
                "shares": float(shares),
                "notional": notional,
            }
        )

    # Then resize selected names. Buys explicitly pay notional * (1 + cost).
    for ticker, weight in weights.items():
        price = float(row[ticker])
        current_shares = float(positions.get(ticker, 0.0))
        current_value = current_shares * price
        target_value = portfolio_value * float(weight)
        difference = target_value - current_value
        if abs(difference) < min_trade:
            continue
        shares = abs(difference) / price
        if difference > 0.0:
            cash -= difference * (1.0 + transaction_cost)
            positions[ticker] = current_shares + shares
            side = "BUY"
        else:
            cash += (-difference) * (1.0 - transaction_cost)
            remaining = current_shares - shares
            if abs(remaining * price) < 1e-10:
                positions.pop(ticker, None)
            else:
                positions[ticker] = remaining
            side = "SELL"
        trades.append(
            {
                "date": date,
                "ticker": ticker,
                "side": side,
                "shares": float(shares),
                "notional": float(abs(difference)),
            }
        )
    return cash, positions, trades


def run_article_backtest(
    prices: pd.DataFrame,
    params: Mapping[str, Any] | ArticleParams | None = None,
) -> dict[str, Any]:
    """Run the article-faithful same-close weekly simulation."""
    cfg = _coerce_params(params)
    clean_prices = _clean_prices(prices)
    start = pd.Timestamp(cfg["start_date"])
    end = pd.Timestamp(cfg["end_date"])
    simulation_prices = clean_prices.loc[start:end]
    if simulation_prices.empty:
        raise ValueError("no aligned prices in requested backtest window")

    scheduled_fridays = pd.date_range(start=start, end=end, freq=cfg["rebalance_freq"])
    rebalance_dates = simulation_prices.index.intersection(scheduled_fridays)
    rebalance_set = set(rebalance_dates)

    cash = float(cfg["initial_cash"])
    positions: dict[str, float] = {}
    values: list[float] = []
    trades: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    skipped_rebalances: list[pd.Timestamp] = []

    for date, row in simulation_prices.iterrows():
        value_before_trade = cash + sum(
            float(shares) * float(row[ticker])
            for ticker, shares in positions.items()
        )
        if date in rebalance_set:
            signal = build_rebalance_signal(clean_prices, date, cfg)
            if signal is None:
                skipped_rebalances.append(date)
            else:
                cash, positions, new_trades = _trade_to_target(
                    date=date,
                    row=row,
                    cash=cash,
                    positions=positions,
                    weights=signal["weights"],
                    portfolio_value=value_before_trade,
                    transaction_cost=float(cfg["transaction_cost"]),
                    min_trade=float(cfg["min_trade"]),
                )
                trades.extend(new_trades)
                signals.append(signal)
        marked_value = cash + sum(
            float(shares) * float(row[ticker])
            for ticker, shares in positions.items()
        )
        values.append(marked_value)

    portfolio = pd.Series(
        values, index=simulation_prices.index, name="strategy", dtype=float
    )
    panel_returns = daily_returns(simulation_prices)
    benchmark_daily = panel_returns.mean(axis=1, skipna=True).fillna(0.0)
    benchmark = (
        float(cfg["initial_cash"]) * (1.0 + benchmark_daily).cumprod()
    ).rename("benchmark")

    trade_columns = ["date", "ticker", "side", "shares", "notional"]
    return {
        "params": cfg,
        "portfolio": portfolio,
        "benchmark": benchmark,
        "metrics": performance_metrics(portfolio),
        "benchmark_metrics": performance_metrics(benchmark),
        "trades": pd.DataFrame(trades, columns=trade_columns),
        "signals": signals,
        "rebalance_dates": rebalance_dates,
        "skipped_rebalances": pd.DatetimeIndex(skipped_rebalances),
        "final_cash": float(cash),
        "final_positions": dict(positions),
    }
