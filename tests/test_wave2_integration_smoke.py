"""Integration smoke tests for the Wave 2 research modules.

The four Wave 2 modules are produced by parallel work streams, so every
test imports its module lazily and skips when the module has not landed
yet. Helpers whose signatures are not frozen yet are bound by parameter
name, so any reasonable naming keeps the smoke checks runnable; a
signature this file cannot bind skips with an explicit reason instead of
erroring.

Live isolation is asserted unconditionally: no ``wave2_`` module may be
imported by the live PTrade strategy files.
"""

import ast
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GENOME_PATH = REPO_ROOT / "research" / "evoquant_genome_wave2.json"
RISK_CODES = ("510300.SS", "159915.SZ", "513100.SS", "518880.SS")
DEFENSIVE_TARGET = {"511010.SS": 0.95}
WAVE2_FAMILIES = ("W2-CROWD", "W2-TRANCHE", "W2-BREADTH")
FIELD_TO_FAMILY = {
    "crowding_percentile": "W2-CROWD",
    "n_tranches": "W2-TRANCHE",
    "breadth_cut": "W2-BREADTH",
}
LIVE_FILES = ("ptrade_adm_etf.py", "ptrade_rmdc_etf.py")

MODULE_SYMBOLS = (
    (
        "research.wave2_crowd",
        (
            "crowd_map_for_index",
            "crowding_component_values",
            "crowding_points_percentile",
        ),
    ),
    ("research.wave2_tranche", ("TrancheBook",)),
    ("research.wave2_breadth", ("apply_breadth_cut",)),
    # build_candidates availability is checked separately because the
    # freeze-per-family loop may land after the module skeleton does.
    ("research.evoquant_loop_wave2", ()),
)


def _call_by_parameter_name(func, patterns):
    """Call ``func`` binding each parameter to a smoke value by its name.

    ``patterns`` is an ordered sequence of ``(substrings, value)`` pairs; a
    parameter receives the first value whose substrings all occur in the
    parameter name. Parameters with defaults may stay unbound. A required
    parameter that matches nothing skips the test, because the frozen
    signature is not one this smoke file anticipated.
    """
    parameters = inspect.signature(func).parameters
    kwargs = {}
    for name, parameter in parameters.items():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        lowered = name.lower()
        for substrings, value in patterns:
            if all(part in lowered for part in substrings):
                kwargs[name] = value
                break
        else:
            if parameter.default is inspect.Parameter.empty:
                pytest.skip(
                    "%s() has a required parameter %r this smoke test "
                    "cannot bind" % (func.__name__, name)
                )
    positional_only = [
        name
        for name, parameter in parameters.items()
        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY
    ]
    if positional_only:
        args = [kwargs[name] for name in parameters if name in kwargs]
        return func(*args)
    return func(**kwargs)


@pytest.mark.parametrize("module_name,symbols", MODULE_SYMBOLS)
def test_wave2_module_exposes_declared_symbols(module_name, symbols):
    module = pytest.importorskip(
        module_name, reason="%s not written yet" % module_name
    )
    missing = [name for name in symbols if not hasattr(module, name)]
    assert not missing, "%s is missing declared symbols: %s" % (
        module_name,
        ", ".join(missing),
    )


def test_tranche_book_two_tranches_produces_two_intermediate_targets():
    module = pytest.importorskip(
        "research.wave2_tranche",
        reason="research.wave2_tranche not written yet",
    )
    book = module.TrancheBook(2)
    book.set_weekly_target({"A": 1.0}, {"B": 1.0})

    first = book.next_target()
    second = book.next_target()

    assert first == pytest.approx({"A": 0.5, "B": 0.5})
    assert second == pytest.approx({"A": 0.0, "B": 1.0})
    assert book.next_target() is None


def test_apply_breadth_cut_zero_passing_gates_forces_defensive_target():
    module = pytest.importorskip(
        "research.wave2_breadth",
        reason="research.wave2_breadth not written yet",
    )
    gate_map = {code: False for code in RISK_CODES}
    proposed_target = {"510300.SS": 0.80, "511010.SS": 0.15}
    patterns = (
        (("breadth", "cut"), 0.25),
        (("cut",), 0.25),
        (("threshold",), 0.25),
        (("gate", "map"), dict(gate_map)),
        (("gate",), [False, False, False, False]),
        (("breadth",), 0.0),
        (("passing",), 0),
        (("count",), 0),
        (("denominator",), 4),
        (("total",), 4),
        (("bond", "target"), dict(DEFENSIVE_TARGET)),
        (("defensive",), dict(DEFENSIVE_TARGET)),
        (("forced",), dict(DEFENSIVE_TARGET)),
        (("target",), dict(proposed_target)),
        (("weight",), dict(proposed_target)),
        (("bond",), "511010.SS"),
        (("risk",), list(RISK_CODES)),
        (("code",), list(RISK_CODES)),
    )

    result = _call_by_parameter_name(module.apply_breadth_cut, patterns)

    assert result == DEFENSIVE_TARGET


def test_crowding_points_percentile_returns_none_before_warmup():
    module = pytest.importorskip(
        "research.wave2_crowd",
        reason="research.wave2_crowd not written yet",
    )
    # 120 sessions cover the 61-bar component window but stay far below
    # the 252 prior observations the genome requires before percentile
    # scoring may replace the incumbent fixed thresholds.
    sessions = 120
    base = np.linspace(0.0, 12.0, sessions)
    closes = 100.0 + 2.0 * np.sin(base) + 0.1 * base
    highs = closes * 1.01
    lows = closes * 0.99
    volumes = 1e6 + 5e4 * np.cos(base)
    amounts = closes * volumes
    current_components = {
        "volume_heat": 1.1,
        "price_extension": 0.02,
        "price_volume_correlation": 0.25,
        "amplitude": 0.02,
    }
    prior_components = {
        name: [value] * 10 for name, value in current_components.items()
    }
    patterns = (
        (("percentile",), 0.95),
        (("session",), 1250),
        (("min",), 252),
        (("prior",), dict(prior_components)),
        (("histor",), dict(prior_components)),
        (("close",), closes),
        (("high",), highs),
        (("low",), lows),
        (("volume",), volumes),
        (("amount",), amounts),
        (("money",), amounts),
        (("current",), dict(current_components)),
        (("component",), dict(current_components)),
        (("value",), dict(current_components)),
        (("code",), "510300.SS"),
    )

    result = _call_by_parameter_name(
        module.crowding_points_percentile, patterns
    )

    assert result is None


def _load_wave2_genome(module):
    loader = getattr(module, "load_genome", None)
    if loader is not None:
        try:
            return loader()
        except TypeError:
            pass
    with open(str(GENOME_PATH), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_wave2_candidates(module):
    build = module.build_candidates
    required = [
        parameter
        for parameter in inspect.signature(build).parameters.values()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
    ]
    if not required:
        return build()
    if len(required) > 1:
        pytest.skip(
            "build_candidates() takes %d required arguments; this smoke "
            "test only knows how to pass the wave 2 genome" % len(required)
        )
    return build(_load_wave2_genome(module))


def _family_of(candidate):
    if isinstance(candidate, dict):
        entries = dict(candidate)
    elif hasattr(candidate, "_asdict"):
        entries = dict(candidate._asdict())
    else:
        entries = dict(vars(candidate))
    found = set()
    for value in entries.values():
        if isinstance(value, str):
            for family in WAVE2_FAMILIES:
                if family in value:
                    found.add(family)
    if not found:
        found = {
            family
            for field, family in FIELD_TO_FAMILY.items()
            if entries.get(field) is not None
        }
    if len(found) == 1:
        return found.pop()
    pytest.fail(
        "cannot attribute candidate %r to exactly one wave 2 family "
        "(matched %s)" % (candidate, sorted(found))
    )


def test_build_candidates_declares_eight_trials_across_three_families():
    module = pytest.importorskip(
        "research.evoquant_loop_wave2",
        reason="research.evoquant_loop_wave2 not written yet",
    )
    if not hasattr(module, "build_candidates"):
        pytest.skip(
            "research.evoquant_loop_wave2.build_candidates not written yet"
        )

    candidates = _build_wave2_candidates(module)

    assert len(candidates) == 8
    families = [_family_of(candidate) for candidate in candidates]
    assert set(families) == set(WAVE2_FAMILIES)
    counts = {family: families.count(family) for family in WAVE2_FAMILIES}
    assert counts == {"W2-CROWD": 2, "W2-TRANCHE": 3, "W2-BREADTH": 3}


@pytest.mark.parametrize("live_name", LIVE_FILES)
def test_live_strategy_files_do_not_import_wave2_modules(live_name):
    live_path = REPO_ROOT / live_name
    assert live_path.is_file(), "%s is missing from the repository" % live_name

    tree = ast.parse(live_path.read_text(encoding="utf-8"), filename=live_name)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
            names.extend(alias.name for alias in node.names)
        else:
            continue
        offenders.extend(name for name in names if "wave2_" in name)

    assert not offenders, "%s imports wave 2 research modules: %s" % (
        live_name,
        ", ".join(offenders),
    )
