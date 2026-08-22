# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import pytest


RESEARCH = Path(__file__).parents[1] / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import backtest_rmdc_etf as backtest


def _stub_weekly_inputs(monkeypatch, challenger_score):
    monkeypatch.setattr(backtest, "GROWTH", ["INCUMBENT", "CHALLENGER"])
    monkeypatch.setattr(backtest, "DIVERSIFIER", [])
    monkeypatch.setattr(backtest, "growth_breadth", lambda returns, codes: 0.5)
    monkeypatch.setattr(backtest, "median_vol", lambda vols, codes: 0.2)
    monkeypatch.setattr(backtest, "classify_state", lambda breadth, vol, lockdown: "balanced")
    monkeypatch.setattr(
        backtest, "eligible", lambda codes, snap, require_trend: list(codes)
    )
    monkeypatch.setattr(
        backtest, "filter_correlated", lambda codes, returns, limit: list(codes)
    )
    monkeypatch.setattr(backtest, "mean_pairwise_corr", lambda returns, codes: 0.0)
    monkeypatch.setattr(
        backtest,
        "build_targets",
        lambda *args: {"CHALLENGER": 0.60, "INCUMBENT": 0.03},
    )
    return {
        "scores": {"INCUMBENT": 1.0, "CHALLENGER": challenger_score},
        "ret20": {},
        "ret63": {},
        "vols": {},
        "ret60": {},
    }


@pytest.mark.parametrize("challenger_score", [1.19, 1.20])
def test_weekly_target_keeps_incumbent_without_twenty_percent_improvement(
    monkeypatch, challenger_score
):
    snap = _stub_weekly_inputs(monkeypatch, challenger_score)

    target = backtest.weekly_target(snap, lockdown=False, current_held=["INCUMBENT"])

    assert target == {"INCUMBENT": 0.03}


def test_weekly_target_replaces_incumbent_above_hysteresis_gap(monkeypatch):
    snap = _stub_weekly_inputs(monkeypatch, challenger_score=1.21)

    target = backtest.weekly_target(snap, lockdown=False, current_held=["INCUMBENT"])

    assert target == {"CHALLENGER": 0.60}
