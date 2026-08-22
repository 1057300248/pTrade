# -*- coding: utf-8 -*-
"""Guardrails: Wave 2 research and hysteresis alignment must never leak
into the live PTrade paste files at the repo root.

These tests only read source text / parse ASTs; they never import the
paste files or any research module.
"""
import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RESEARCH = REPO_ROOT / "research"

FORBIDDEN_LEAF_MODULES = {"baostock", "akshare", "stockdb"}
LIVE_FILE_NAME = "ptrade_adm_etf"

PASTE_FILES = sorted(REPO_ROOT.glob("ptrade_*.py"))


def _imported_module_names(source):
    """Return every dotted module path a file imports, including the
    combined ``package.name`` form of ``from package import name``."""
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                names.append(module)
            names.extend(
                "%s.%s" % (module, alias.name) if module else alias.name
                for alias in node.names
            )
    return names


def _is_forbidden_module(dotted):
    for part in dotted.split("."):
        if part in FORBIDDEN_LEAF_MODULES:
            return True
        if part.startswith("wave2_"):
            return True
        if part.startswith("evoquant_loop"):
            return True
    return False


def test_paste_files_present():
    names = {path.name for path in PASTE_FILES}
    assert "ptrade_adm_etf.py" in names
    assert "ptrade_rmdc_etf.py" in names


@pytest.mark.parametrize("path", PASTE_FILES, ids=lambda p: p.name)
def test_paste_files_do_not_import_research_or_vendor_modules(path):
    imported = _imported_module_names(path.read_text(encoding="utf-8"))
    leaked = sorted(set(name for name in imported if _is_forbidden_module(name)))
    assert not leaked, "%s imports forbidden module(s): %s" % (path.name, leaked)


def test_rmdc_hysteresis_source_unchanged():
    source = (REPO_ROOT / "ptrade_rmdc_etf.py").read_text(encoding="utf-8")
    assert "def apply_hysteresis" in source
    assert "g.hysteresis = 1.20" in source


def test_adm_vol_target_and_risk_universe_unchanged():
    source = (REPO_ROOT / "ptrade_adm_etf.py").read_text(encoding="utf-8")
    assert "g.vol_target = 0.16" in source

    risk = None
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "RISK" in targets:
                risk = ast.literal_eval(node.value)
    assert risk == [
        "510300.SS",
        "159915.SZ",
        "513100.SS",
        "518880.SS",
    ]


def test_wave1_loop_still_writes_candidates_report():
    source = (RESEARCH / "evoquant_loop.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    report_strings = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "REPORT_PATH" in targets:
                report_strings = [
                    sub.value
                    for sub in ast.walk(node.value)
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                ]
    assert any(
        value.endswith("evoquant_candidates.md") for value in report_strings
    ), "REPORT_PATH no longer points at evoquant_candidates.md"

    assert re.search(r"open\(\s*REPORT_PATH\s*,\s*['\"]w", source), (
        "evoquant_loop.py no longer writes REPORT_PATH"
    )


def _open_mode(call):
    """Literal mode string of an open() call, 'r' if omitted, None if dynamic."""
    mode_node = None
    if len(call.args) >= 2:
        mode_node = call.args[1]
    for keyword in call.keywords:
        if keyword.arg == "mode":
            mode_node = keyword.value
    if mode_node is None:
        return "r"
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        return mode_node.value
    return None


def _live_path_aliases(tree):
    """Names of variables whose assigned value embeds the live file name,
    e.g. ``LIVE_PATH = os.path.join(ROOT, "ptrade_adm_etf.py")``."""
    aliases = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        has_live_literal = any(
            isinstance(sub, ast.Constant)
            and isinstance(sub.value, str)
            and LIVE_FILE_NAME in sub.value
            for sub in ast.walk(node.value)
        )
        if has_live_literal:
            aliases.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
    return aliases


def _mentions_live_file(node, aliases):
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Constant)
            and isinstance(sub.value, str)
            and LIVE_FILE_NAME in sub.value
        ):
            return True
        if isinstance(sub, ast.Name) and sub.id in aliases:
            return True
    return False


def test_wave2_loop_never_writes_live_paste_file():
    path = RESEARCH / "evoquant_loop_wave2.py"
    if not path.exists():
        pytest.skip("research/evoquant_loop_wave2.py not present")

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    aliases = _live_path_aliases(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "open":
            if _mentions_live_file(node, aliases):
                mode = _open_mode(node)
                assert mode is not None and not set(mode) & set("wax+"), (
                    "evoquant_loop_wave2.py opens %s for write (mode=%r)"
                    % (LIVE_FILE_NAME, mode)
                )
        if isinstance(func, ast.Attribute) and func.attr in (
            "write_text",
            "write_bytes",
        ):
            assert not _mentions_live_file(node, aliases), (
                "evoquant_loop_wave2.py calls %s on %s" % (func.attr, LIVE_FILE_NAME)
            )

    # Any module-level auto-live-edit style boolean flag must be off.
    flag_pattern = re.compile(r"(?i)(auto.*(live|apply|edit)|(live|apply).*edit)")
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and flag_pattern.search(target.id):
                if isinstance(node.value, ast.Constant) and isinstance(
                    node.value.value, bool
                ):
                    assert node.value.value is False, (
                        "%s must stay False in evoquant_loop_wave2.py" % target.id
                    )
