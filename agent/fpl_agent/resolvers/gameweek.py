"""
Gameweek resolution layer.

Maps free-text gameweek references ("GW12", "next 3", "the double", "rest of
the season") onto concrete gameweek ids.

Design notes
------------
* This is a GRAMMAR, not a fuzzy matcher. The vocabulary is small and closed,
  so ordered regex rules beat similarity scoring: "GW13" and "GW18" are one
  character apart and must never be confused, which is exactly the case fuzzy
  matching handles worst.
* Every query resolves to a RANGE. A single gameweek is a range of length one.
  Most real questions ("next 5 fixtures", "the run-in") are ranges anyway, and
  a uniform return type keeps the agent layer simple.
* `now` is injected, never read from the clock inside the resolver. Deadline
  boundaries are where this layer breaks, so they have to be testable.
* The current/next distinction is derived from deadlines and `now` rather than
  trusted from the payload's is_current/is_next flags, which go stale the
  moment you cache bootstrap-static.
* Doubles and blanks are derived from the fixtures list, which is optional.
  Without it those queries return a clear "not available" rather than a guess -
  doubles are often not known until cup rounds resolve.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from ..types import Gameweek, GameweekResolution, SEASON_LENGTH

#: How resolution terminated. Literal so a typo in a branch fails loudly.
Method = Literal[
    "absolute",      # "GW12"
    "range",         # "GW12-15"
    "relative",      # "this" / "next" / "last"
    "count",         # "next 5"
    "season",        # "rest of the season"
    "special",       # "the double" / "the blank"
    "out_of_range",  # parsed fine, but outside 1..38 or the season is over
    "unavailable",   # understood, but the data needed is missing
    "none",
]


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "a couple of": 2, "a couple": 2, "a few": 3, "few": 3,
}

#: Words that mean "gameweek". `mw` and `matchweek` are broadcast usage.
_GW_WORD = r"(?:gw|gws|gameweeks?|game\s*weeks?|matchweeks?|mw|weeks?)"

_RANGE_RE = re.compile(
    rf"{_GW_WORD}?\s*(\d{{1,2}})\s*(?:-|–|—|to|through|thru|till|until)\s*"
    rf"{_GW_WORD}?\s*(\d{{1,2}})\b",
    re.I,
)
_ABSOLUTE_RE = re.compile(rf"\b{_GW_WORD}\s*#?\s*(\d{{1,2}})\b", re.I)
_COUNT_RE = re.compile(
    rf"\bnext\s+(\d{{1,2}}|{'|'.join(_NUMBER_WORDS)})\s*{_GW_WORD}?\b", re.I
)
_SEASON_RE = re.compile(
    r"\b(rest of (?:the )?season|remaining (?:gameweeks|fixtures)|"
    r"run.?in|until the end|end of (?:the )?season)\b",
    re.I,
)
_RELATIVE_RE = re.compile(
    rf"\b(this|current|coming|upcoming|next|following|last|previous|prior)\s*"
    rf"(?:{_GW_WORD})?\b",
    re.I,
)
_DOUBLE_RE = re.compile(r"\b(double\s*(?:gameweek|gw)?s?|dgw)\b", re.I)
_BLANK_RE = re.compile(r"\b(blank\s*(?:gameweek|gw)?s?|bgw)\b", re.I)
_ONWARDS_RE = re.compile(
    rf"(?:\bfrom\s+{_GW_WORD}?\s*(\d{{1,2}})\b(?!\s*(?:-|–|to|through)))"
    rf"|(?:{_GW_WORD}?\s*(\d{{1,2}})\s*(?:onwards?|and (?:on|after|beyond)|\+))",
    re.I,
)


class GameweekResolver:
    """Resolve free text to concrete gameweeks.

        payload = requests.get(BOOTSTRAP_URL).json()
        fixtures = requests.get(FIXTURES_URL).json()
        r = GameweekResolver(payload["events"], fixtures, now=datetime.now(timezone.utc))
        r.resolve("next 3").ids  # -> [12, 13, 14]
    """

    def __init__(
        self,
        gameweeks: Iterable[Gameweek],
        fixtures: Iterable[dict[str, Any]] | None = None,
        now: datetime | None = None,
    ) -> None:
        self.gameweeks = gameweeks
        self._by_id = {g.id: g for g in self.gameweeks}
        self.now = now or datetime.now(timezone.utc)
        if self.now.tzinfo is None:
            raise ValueError("`now` must be timezone-aware")

        self._fixtures = list(fixtures) if fixtures is not None else None
        self._counts: dict[int, dict[int, int]] | None = None
        self._team_ids: set[int] = set()
        if self._fixtures is not None:
            self._index_fixtures()

    def _index_fixtures(self) -> None:
        assert self._fixtures is not None
        counts: dict[int, dict[int, int]] = {}
        for fx in self._fixtures:
            for side in ("team_h", "team_a"):
                if fx.get(side) is not None:
                    self._team_ids.add(fx[side])
            event = fx.get("event")
            if event is None:  # unscheduled - this is how blanks arise
                continue
            per_team = counts.setdefault(event, {})
            for side in ("team_h", "team_a"):
                if fx.get(side) is not None:
                    per_team[fx[side]] = per_team.get(fx[side], 0) + 1
        self._counts = counts

    # -- temporal anchors ---------------------------------------------------

    @property
    def upcoming(self) -> Gameweek | None:
        """The first gameweek whose deadline has not passed.

        This is the ACTIONABLE gameweek - the one the user can still make
        transfers for. It is the anchor for almost every relative query.
        """
        return next((g for g in self.gameweeks if g.deadline_time > self.now), None)

    @property
    def in_progress(self) -> Gameweek | None:
        """The gameweek whose deadline has passed but whose matches are not
        all finished. None between gameweeks."""
        started = [g for g in self.gameweeks if g.deadline_time <= self.now]
        if not started:
            return None
        last = started[-1]
        return None if last.finished else last

    @property
    def season_over(self) -> bool:
        return self.upcoming is None

    # -- special gameweeks --------------------------------------------------

    def doubles(self, at_or_after: int = 1) -> list[int]:
        """Gameweek ids where at least one team plays twice or more."""
        if self._counts is None:
            return []
        return sorted(
            gw for gw, per_team in self._counts.items()
            if gw >= at_or_after and any(n >= 2 for n in per_team.values())
        )

    def blanks(self, at_or_after: int = 1) -> list[int]:
        """Gameweek ids where at least one team has no fixture."""
        if self._counts is None or not self._team_ids:
            return []
        out = []
        for gw in self._by_id:
            if gw < at_or_after:
                continue
            per_team = self._counts.get(gw, {})
            if not per_team:
                continue  # nothing scheduled at all: not yet published
            if any(t not in per_team for t in self._team_ids):
                out.append(gw)
        return sorted(out)

    # -- resolution ---------------------------------------------------------

    def resolve(self, query: str) -> GameweekResolution:
        text = (query or "").strip().lower()
        if not text:
            return GameweekResolution(query=query)

        # Order matters: ranges before absolutes, or "12-15" yields just 12.
        for handler in (
            self._try_range,
            self._try_special,
            self._try_count,
            self._try_season,
            self._try_onwards,
            self._try_absolute,
            self._try_relative,
        ):
            result = handler(query, text)
            if result is not None:
                return result
        return GameweekResolution(query=query, method="none")

    # -- handlers -----------------------------------------------------------

    def _span(self, start: int, end: int) -> tuple[list[Gameweek], bool]:
        clamped = end > SEASON_LENGTH or start < 1
        start, end = max(1, start), min(SEASON_LENGTH, end)
        return [self._by_id[i] for i in range(start, end + 1) if i in self._by_id], clamped

    def _try_range(self, query: str, text: str) -> GameweekResolution | None:
        m = _RANGE_RE.search(text)
        if not m:
            return None
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            a, b = b, a
        if a < 1 or a > SEASON_LENGTH:
            return GameweekResolution(
                query=query, method="out_of_range",
                note=f"GW{a} is outside the 1-{SEASON_LENGTH} season.",
            )
        gws, clamped = self._span(a, b)
        return GameweekResolution(
            query=query, gameweeks=gws, method="range", clamped=clamped,
            note=f"Requested range ran past GW{SEASON_LENGTH}; truncated."
            if clamped else None,
        )

    def _try_onwards(self, query: str, text: str) -> GameweekResolution | None:
        m = _ONWARDS_RE.search(text)
        if not m:
            return None
        n = int(m.group(1) or m.group(2))
        if n < 1 or n > SEASON_LENGTH:
            return GameweekResolution(
                query=query, method="out_of_range",
                note=f"GW{n} is outside the 1-{SEASON_LENGTH} season.",
            )
        gws, _ = self._span(n, SEASON_LENGTH)
        return GameweekResolution(
            query=query, gameweeks=gws, method="range",
            note=f"GW{n} to the end of the season.",
        )

    def _try_absolute(self, query: str, text: str) -> GameweekResolution | None:
        m = _ABSOLUTE_RE.search(text)
        if not m:
            return None
        n = int(m.group(1))
        if n < 1 or n > SEASON_LENGTH:
            return GameweekResolution(
                query=query, method="out_of_range",
                note=f"GW{n} is outside the 1-{SEASON_LENGTH} season.",
            )
        gw = self._by_id.get(n)
        if gw is None:
            return GameweekResolution(
                query=query, method="unavailable",
                note=f"GW{n} is not present in the events payload.",
            )
        note = None
        if gw.deadline_time <= self.now:
            note = f"GW{n}'s deadline has passed; transfers can no longer be made."
        return GameweekResolution(
            query=query, gameweeks=[gw], method="absolute", note=note
        )

    def _try_count(self, query: str, text: str) -> GameweekResolution | None:
        m = _COUNT_RE.search(text)
        if not m:
            return None
        raw = m.group(1)
        n = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
        anchor = self.upcoming
        if anchor is None:
            return GameweekResolution(
                query=query, method="out_of_range",
                note="The season has finished; there are no upcoming gameweeks.",
            )
        gws, clamped = self._span(anchor.id, anchor.id + n - 1)
        note = f"Counted from GW{anchor.id}, the next gameweek you can still act on."
        if clamped:
            note += f" Only {len(gws)} remain this season."
        return GameweekResolution(
            query=query, gameweeks=gws, method="count", clamped=clamped, note=note
        )

    def _try_season(self, query: str, text: str) -> GameweekResolution | None:
        if not _SEASON_RE.search(text):
            return None
        anchor = self.upcoming
        if anchor is None:
            return GameweekResolution(
                query=query, method="out_of_range", note="The season has finished.",
            )
        gws, _ = self._span(anchor.id, SEASON_LENGTH)
        return GameweekResolution(
            query=query, gameweeks=gws, method="season",
            note=f"GW{anchor.id} to GW{SEASON_LENGTH}.",
        )

    def _try_special(self, query: str, text: str) -> GameweekResolution | None:
        is_double = bool(_DOUBLE_RE.search(text))
        is_blank = bool(_BLANK_RE.search(text))
        if not (is_double or is_blank):
            return None
        label = "double" if is_double else "blank"
        if self._counts is None:
            return GameweekResolution(
                query=query, method="unavailable",
                note=f"Cannot identify {label} gameweeks without the fixtures list.",
            )
        anchor = self.upcoming.id if self.upcoming else 1
        found = self.doubles(anchor) if is_double else self.blanks(anchor)
        if not found:
            return GameweekResolution(
                query=query, method="unavailable",
                note=f"No {label} gameweek is scheduled from GW{anchor} onwards. "
                f"These are often confirmed late, once cup rounds are played.",
            )
        wants_all = bool(re.search(r"\b(all|every|which|any)\b", text))
        ids = found if wants_all else found[:1]
        return GameweekResolution(
            query=query,
            gameweeks=[self._by_id[i] for i in ids if i in self._by_id],
            method="special",
            note=f"{label.title()} gameweek(s) from GW{anchor}: "
            + ", ".join(f"GW{i}" for i in found),
        )

    def _try_relative(self, query: str, text: str) -> GameweekResolution | None:
        m = _RELATIVE_RE.search(text)
        if not m:
            return None
        word = m.group(1)
        live = self.in_progress
        upcoming = self.upcoming

        if word in {"last", "previous", "prior"}:
            ref = live.id - 1 if live else (upcoming.id - 1 if upcoming else SEASON_LENGTH)
            gw = self._by_id.get(ref)
            if gw is None:
                return GameweekResolution(
                    query=query, method="out_of_range",
                    note="No gameweek has been completed yet.",
                )
            return GameweekResolution(
                query=query, gameweeks=[gw], method="relative",
                note=f"GW{gw.id}, the most recently completed gameweek.",
            )

        if upcoming is None:
            return GameweekResolution(
                query=query, method="out_of_range", note="The season has finished.",
            )

        # "this" during live matches means the one being played; otherwise it
        # means the one you can still pick for. "next" tracks the same anchor,
        # because in FPL usage "next gameweek" almost always means the next
        # deadline, not the one after it.
        if word in {"this", "current"} and live is not None:
            return GameweekResolution(
                query=query, gameweeks=[live], method="relative",
                note=f"GW{live.id} is in progress. Its deadline has passed, so "
                f"the next gameweek you can change is GW{upcoming.id}.",
            )
        return GameweekResolution(
            query=query, gameweeks=[upcoming], method="relative",
            note=f"GW{upcoming.id}, the next deadline "
            f"({upcoming.deadline_time:%a %d %b %H:%M} UTC).",
        )