import numpy as np
import pytest

from research.wave2_breadth import (
    BOND,
    RISK,
    RISK_DENOMINATOR,
    apply_breadth_cut,
    forced_defensive_target,
    month_gate_breadth,
)


def _gate_map(passing_count):
    """Build a gate map where the first ``passing_count`` RISK codes pass."""
    return {code: index < passing_count for index, code in enumerate(RISK)}


def test_risk_universe_matches_live_strategy():
    assert RISK == ["510300.SS", "159915.SZ", "513100.SS", "518880.SS"]
    assert BOND == "511010.SS"
    assert RISK_DENOMINATOR == 4
    assert len(RISK) == RISK_DENOMINATOR


@pytest.mark.parametrize("passing_count", [0, 1, 2, 3, 4])
def test_month_gate_breadth_is_passing_count_over_four(passing_count):
    breadth = month_gate_breadth(_gate_map(passing_count))
    assert isinstance(breadth, float)
    assert breadth == passing_count / 4.0
    assert 0.0 <= breadth <= 1.0


@pytest.mark.parametrize(
    "passing_count,breadth_cut,forced",
    [
        # cut 0.25: forces only the zero-passing state (1/4 == 0.25 is not < cut)
        (0, 0.25, True),
        (1, 0.25, False),
        (2, 0.25, False),
        (3, 0.25, False),
        (4, 0.25, False),
        # cut 0.50: forces below the two-passing boundary
        (0, 0.50, True),
        (1, 0.50, True),
        (2, 0.50, False),
        (3, 0.50, False),
        (4, 0.50, False),
        # cut 0.75: forces below the three-passing boundary
        (0, 0.75, True),
        (1, 0.75, True),
        (2, 0.75, True),
        (3, 0.75, False),
        (4, 0.75, False),
    ],
)
def test_apply_breadth_cut_grid_boundaries(passing_count, breadth_cut, forced):
    result = apply_breadth_cut(_gate_map(passing_count), breadth_cut)
    if forced:
        assert isinstance(result, dict)
        assert result == {"511010.SS": 0.95}
    else:
        assert result is None


def test_missing_gates_count_as_fail():
    # Only 510300.SS is present and passing; the other three are absent.
    gate_map = {"510300.SS": True}
    assert month_gate_breadth(gate_map) == 0.25

    # Empty map: nothing passes.
    assert month_gate_breadth({}) == 0.0

    # Missing entries push breadth below the cut even though every present
    # gate passes.
    assert apply_breadth_cut({"510300.SS": True}, 0.50) == {BOND: 0.95}


def test_falsey_gate_values_count_as_fail_and_truthy_as_pass():
    gate_map = {
        "510300.SS": True,
        "159915.SZ": False,
        "513100.SS": None,
        "518880.SS": np.bool_(True),  # numpy bool from research pipelines
    }
    assert month_gate_breadth(gate_map) == 0.5


def test_does_not_mutate_gate_map():
    gate_map = {"510300.SS": True, "159915.SZ": False}
    snapshot = dict(gate_map)

    month_gate_breadth(gate_map)
    apply_breadth_cut(gate_map, 0.25)
    apply_breadth_cut(gate_map, 0.75)

    assert gate_map == snapshot


def test_forced_defensive_target_defaults_and_fresh_dict():
    target = forced_defensive_target()
    assert target == {"511010.SS": 0.95}

    # Each call returns a new dict so callers cannot corrupt shared state.
    assert forced_defensive_target() is not target
    assert apply_breadth_cut({}, 0.25) is not apply_breadth_cut({}, 0.25)


def test_forced_defensive_target_overrides():
    assert forced_defensive_target(bond="511880.SS", weight=1.0) == {"511880.SS": 1.0}
    assert apply_breadth_cut({}, 0.25, bond="511880.SS") == {"511880.SS": 0.95}


def test_custom_risk_codes_denominator():
    gate_map = {"A": True, "B": False}
    assert month_gate_breadth(gate_map, risk_codes=["A", "B"]) == 0.5
    assert apply_breadth_cut(gate_map, 0.75, risk_codes=["A", "B"]) == {BOND: 0.95}
    assert apply_breadth_cut(gate_map, 0.50, risk_codes=["A", "B"]) is None
