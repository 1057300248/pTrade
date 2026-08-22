"""Frozen-target tranche scheduling for the Wave 2 ADM research candidate."""


class TrancheBook(object):
    """Split an original holdings-to-target gap across consecutive closes."""

    def __init__(self, n_tranches):
        if isinstance(n_tranches, bool) or n_tranches not in (1, 2, 3, 4):
            raise ValueError("n_tranches must be one of 1, 2, 3, or 4")
        self.n_tranches = int(n_tranches)
        self.cancel()

    def set_weekly_target(self, holdings, target):
        """Freeze a new weekly schedule, replacing any unfinished schedule."""
        self._holdings = dict(holdings)
        self._target = dict(target)
        codes = list(self._holdings)
        codes.extend(code for code in self._target if code not in self._holdings)
        self._codes = tuple(codes)
        self._remaining = self.n_tranches

    def next_target(self, current_holdings=None):
        """Return the next target on the path fixed by the weekly signal.

        ``current_holdings`` is accepted for engine-call compatibility but does
        not alter the frozen path.
        """
        if not self._remaining:
            return None

        step = self.n_tranches - self._remaining + 1
        fraction = float(step) / float(self.n_tranches)
        intermediate = {}
        for code in self._codes:
            original = self._holdings.get(code, 0.0)
            final = self._target.get(code, 0.0)
            if step == self.n_tranches:
                intermediate[code] = final
            else:
                intermediate[code] = original + fraction * (final - original)

        self._remaining -= 1
        return intermediate

    def cancel(self):
        """Drop any unfinished schedule."""
        self._holdings = {}
        self._target = {}
        self._codes = ()
        self._remaining = 0

    def crash_target(self, defensive_target):
        """Cancel scheduled tranches and bypass them with a defensive target."""
        self.cancel()
        return defensive_target

    def active(self):
        """Return whether a tranche remains to be emitted."""
        return bool(self._remaining)
