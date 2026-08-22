import pytest

from research.wave2_tranche import TrancheBook


@pytest.mark.parametrize("n_tranches", [1, 2, 3, 4])
def test_equal_pieces_follow_the_frozen_original_gap(n_tranches):
    holdings = {"KEEP": 0.6, "SELL": 0.4}
    target = {"KEEP": 0.2, "BUY": 0.8}
    book = TrancheBook(n_tranches)
    book.set_weekly_target(holdings, target)

    outputs = []
    for step in range(1, n_tranches + 1):
        assert book.active()
        output = book.next_target(current_holdings={"IGNORED": 1.0})
        fraction = float(step) / n_tranches
        assert output == pytest.approx(
            {
                "KEEP": 0.6 + fraction * (0.2 - 0.6),
                "SELL": 0.4 + fraction * (0.0 - 0.4),
                "BUY": 0.0 + fraction * (0.8 - 0.0),
            }
        )
        assert sum(output.values()) == pytest.approx(
            1.0 + fraction * (1.0 - 1.0)
        )
        outputs.append(output)

    assert outputs[-1] == {"KEEP": 0.2, "SELL": 0.0, "BUY": 0.8}
    for previous, current in zip(outputs, outputs[1:]):
        assert current["KEEP"] - previous["KEEP"] == pytest.approx(
            (0.2 - 0.6) / n_tranches
        )
        assert current["SELL"] - previous["SELL"] == pytest.approx(
            (0.0 - 0.4) / n_tranches
        )
        assert current["BUY"] - previous["BUY"] == pytest.approx(
            (0.8 - 0.0) / n_tranches
        )

    assert not book.active()
    assert book.next_target() is None


def test_inputs_are_frozen_and_current_holdings_do_not_refresh_schedule():
    holdings = {"A": 1.0}
    target = {"B": 1.0}
    book = TrancheBook(2)
    book.set_weekly_target(holdings, target)

    holdings["A"] = 0.0
    target["B"] = 0.0

    assert book.next_target({"A": 0.9, "B": 0.1, "OTHER": 0.5}) == pytest.approx(
        {"A": 0.5, "B": 0.5}
    )
    assert book.next_target({"A": 0.1, "B": 0.9}) == pytest.approx(
        {"A": 0.0, "B": 1.0}
    )


def test_cancel_drops_unfinished_schedule():
    book = TrancheBook(3)
    book.set_weekly_target({"A": 1.0}, {"B": 1.0})
    book.next_target()

    book.cancel()

    assert not book.active()
    assert book.next_target() is None


def test_crash_target_bypasses_and_cancels_schedule():
    defensive_target = {"BOND": 0.95}
    book = TrancheBook(4)
    book.set_weekly_target({"RISK": 1.0}, {"GOLD": 1.0})

    result = book.crash_target(defensive_target)

    assert result is defensive_target
    assert result == {"BOND": 0.95}
    assert not book.active()
    assert book.next_target() is None


def test_new_weekly_target_replaces_unfinished_schedule():
    book = TrancheBook(2)
    book.set_weekly_target({"OLD": 1.0}, {"STALE": 1.0})
    assert book.next_target() == pytest.approx({"OLD": 0.5, "STALE": 0.5})

    book.set_weekly_target({"NEW": 0.6}, {"FINAL": 0.9})

    assert book.next_target() == pytest.approx({"NEW": 0.3, "FINAL": 0.45})
    assert book.next_target() == pytest.approx({"NEW": 0.0, "FINAL": 0.9})
    assert book.next_target() is None
