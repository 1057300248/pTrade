from pathlib import Path

import pytest

from research import evoquant_loop_wave2 as wave2


def test_build_candidates_declares_eight_one_field_trials():
    candidates = wave2.build_candidates()

    assert len(candidates) == 8
    assert [candidate["key"] for candidate in candidates] == [
        "W2-CROWD-P90",
        "W2-CROWD-P95",
        "W2-TRANCHE-N2",
        "W2-TRANCHE-N3",
        "W2-TRANCHE-N4",
        "W2-BREADTH-C25",
        "W2-BREADTH-C50",
        "W2-BREADTH-C75",
    ]
    mutable_fields = set(wave2.FAMILY_FIELDS.values())
    for candidate in candidates:
        assert set(candidate) == {"family", "field", "value", "key"}
        assert candidate["field"] in mutable_fields
        assert sum(
            field == candidate["field"] for field in mutable_fields
        ) == 1


def test_freeze_family_winner_uses_is_only_and_lower_value_tie_break():
    lower_value = {
        "config": {
            "family": "W2-CROWD",
            "field": "crowding_percentile",
            "value": 0.90,
            "key": "W2-CROWD-P90",
        },
        "is": {"sharpe": 1.0, "cagr": 0.12, "mdd": -0.15},
        "oos": {"sharpe": -100.0, "cagr": -1.0},
        "stress": {"2024-02": {"return": -1.0}},
    }
    higher_value = {
        "config": {
            "family": "W2-CROWD",
            "field": "crowding_percentile",
            "value": 0.95,
            "key": "W2-CROWD-P95",
        },
        "is": {"sharpe": 1.0, "cagr": 0.12, "mdd": -0.15},
        "oos": {"sharpe": 100.0, "cagr": 10.0},
        "stress": {"2024-02": {"return": 10.0}},
    }

    selected = wave2.freeze_family_winner(
        [higher_value, lower_value]
    )

    assert selected is lower_value


def test_live_file_hash_guard_detects_a_change(tmp_path):
    live_file = tmp_path / "ptrade_adm_etf.py"
    live_file.write_text("before\n", encoding="utf-8")
    initial_hash = wave2.file_sha256(str(live_file))

    assert wave2.assert_live_file_unchanged(
        initial_hash, str(live_file)
    ) == initial_hash
    live_file.write_text("after\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="live ADM file changed"):
        wave2.assert_live_file_unchanged(initial_hash, str(live_file))


def test_wave2_report_path_does_not_overwrite_wave1_report():
    report_path = Path(wave2.REPORT_PATH)

    assert report_path.name == "evoquant_candidates_wave2.md"
    assert report_path.name != "evoquant_candidates.md"
