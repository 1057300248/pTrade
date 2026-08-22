"""W2-BREADTH: Keller-style cross-asset breadth cut for ADM (Wave 2).

Implements the frozen candidate from ``research/evoquant_wave2_plan.md``:

- At the weekly signal close, the caller evaluates the existing ``month_gate``
  for each of the four ``RISK`` assets and passes the results here.
- Breadth is the passing count divided by the fixed denominator four.
- If ``breadth < breadth_cut``, force the incumbent defensive target
  ``{511010.SS: 0.95}``.
- Otherwise return ``None`` and the caller runs incumbent ADM selection and
  volatility scaling unchanged.

The crash overlay and three-session lockdown are outside this module and take
priority in the caller.  Grid only ``breadth_cut in {0.25, 0.50, 0.75}``:
with four assets these are exact one-, two-, and three-passing-asset
boundaries.
"""

__all__ = [
    "RISK",
    "BOND",
    "RISK_DENOMINATOR",
    "BREADTH_CUT_GRID",
    "month_gate_breadth",
    "forced_defensive_target",
    "apply_breadth_cut",
]

# Mirrors RISK/BOND in ptrade_adm_etf.py (live strategy must not be imported
# or edited by research code).
RISK = [
    "510300.SS",
    "159915.SZ",
    "513100.SS",
    "518880.SS",
]
BOND = "511010.SS"
RISK_DENOMINATOR = 4

BREADTH_CUT_GRID = (0.25, 0.50, 0.75)


def month_gate_breadth(gate_map, risk_codes=None):
    """gate_map: dict code->bool. Count True among the 4 RISK names. Return float in [0,1].

    A code that is missing from ``gate_map`` counts as a failed gate, as do
    ``None``/``False`` values.  Truthiness (not ``is True``) decides passing so
    numpy bools from research pipelines are honoured.  The input mapping is
    never mutated.
    """
    codes = RISK if risk_codes is None else list(risk_codes)
    passing = sum(1 for code in codes if gate_map.get(code, False))
    return passing / float(len(codes))


def forced_defensive_target(bond=BOND, weight=0.95):
    """Return the incumbent defensive target as a fresh dict."""
    return {bond: weight}


def apply_breadth_cut(gate_map, breadth_cut, risk_codes=None, bond=BOND):
    """If month_gate_breadth < breadth_cut: return forced_defensive_target.
    Else return None. Do not pick winners here."""
    breadth = month_gate_breadth(gate_map, risk_codes=risk_codes)
    if breadth < breadth_cut:
        return forced_defensive_target(bond=bond)
    return None
