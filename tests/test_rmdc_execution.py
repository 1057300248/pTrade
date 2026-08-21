# -*- coding: utf-8 -*-
import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ptrade_rmdc_etf as strategy


class _State(object):
    pass


class _Context(object):
    pass


def test_live_source_avoids_unsupported_execution_apis():
    source_path = os.path.join(ROOT, "ptrade_rmdc_etf.py")
    with open(source_path, "r", encoding="utf-8") as source_file:
        source = source_file.read()

    assert "order_target_value" not in source
    assert "get_snapshot" not in source


def test_initialize_registers_safety_schedule_outside_live_trading(monkeypatch):
    scheduled = []

    def capture_run_daily(context, callback, time=None):
        scheduled.append((context, callback, time))

    monkeypatch.setattr(strategy, "g", _State(), raising=False)
    monkeypatch.setattr(strategy, "set_universe", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(strategy, "set_benchmark", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(strategy, "set_commission", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(strategy, "set_slippage", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(strategy, "set_limit_mode", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(strategy, "run_daily", capture_run_daily, raising=False)
    monkeypatch.setattr(strategy, "is_trade", lambda: False, raising=False)

    context = _Context()
    strategy.initialize(context)

    assert [(callback, time) for _, callback, time in scheduled] == [
        (strategy.crash_overlay, "14:45"),
        (strategy.weekly_rebalance, "14:50"),
        (strategy.rebalance_buy, "14:54"),
    ]
    assert all(call_context is context for call_context, _, _ in scheduled)


def test_normalize_security_code_maps_ptrade_suffixes():
    assert strategy._normalize_security_code("510300.XSHG") == "510300.SS"
    assert strategy._normalize_security_code("159915.XSHE") == "159915.SZ"
    assert strategy._normalize_security_code("518880.SS") == "518880.SS"
    assert strategy._normalize_security_code(None) is None


def test_lot_shares_rounds_down_and_rejects_invalid_inputs():
    assert strategy.lot_shares(1550, 10.0) == 100
    assert strategy.lot_shares(50, 10.0) == 0
    assert strategy.lot_shares(1550, 10.0, lot=1) == 155
    assert strategy.lot_shares(1550, 0) == 0
    assert strategy.lot_shares(0, 10.0) == 0


def test_apply_hysteresis_keeps_small_upgrade_and_accepts_large_upgrade():
    small_upgrade = strategy.apply_hysteresis(
        ["A"], ["B"], {"A": 1.0, "B": 1.1}, gap=1.20
    )
    large_upgrade = strategy.apply_hysteresis(
        ["A"], ["B"], {"A": 1.0, "B": 1.5}, gap=1.20
    )

    assert small_upgrade == ["A"]
    assert large_upgrade == ["B"]
