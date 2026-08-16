"""
Player resolution layer.

Maps free-text player references ("salah", "KDB", "the Arsenal keeper",
"haalnd") onto concrete FPL player records.

Design notes
------------
* NOTHING here hardcodes a player. Teams are 20 stable entities and justify a
  hand-curated dict; players churn every transfer window. The whole index is
  derived from the `elements` payload at construction.
* The one curated layer is NICKNAMES, and it maps abbreviations to NAME
  FRAGMENTS, not to player ids: "kdb" -> "de bruyne". A fragment stays correct
  when the player moves club, retires, or leaves the league. An id does not.
* Lexical matching beats embeddings on proper nouns, so there is no vector
  step. Embeddings would only earn their place on descriptive reference
  ("the pacy Brighton winger"), and the structured path below covers the
  useful half of that far more cheaply.
* Priors (squad membership, minutes, ownership) NEVER override a strong
  lexical match. They only reorder candidates that are already lexically
  tied - which is exactly the "which Silva?" case.
* Ambiguity returns candidates. An FPL agent that silently picks the wrong
  Silva will produce a confident, fluent, completely wrong transfer
  recommendation, and nothing downstream will flag it.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Literal
from rapidfuzz import fuzz, process

from .team import TeamResolver, normalise
from ..types import Player, PlayerCandidate, PlayerQuery, PlayerResolution

#: FPL element_type -> short position code. Type 5 (managers) appeared in
#: 2024/25 and is carried here so the payload does not blow up if you keep it.
POSITIONS: dict[int, str] = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD", 5: "MNG"}

#: Words that identify a position in free text.
POSITION_WORDS: dict[str, tuple[str, ...]] = {
    "GKP": ("keeper", "goalkeeper", "gk", "gkp", "goalie", "stopper", "number one"),
    "DEF": ("defender", "def", "centre back", "center back", "cb", "full back",
            "fullback", "left back", "lb", "right back", "rb", "wing back",
            "defence", "defense", "at the back"),
    "MID": ("midfielder", "mid", "winger", "playmaker", "cm", "cdm", "cam",
            "midfield", "wide man", "number ten"),
    "FWD": ("forward", "striker", "fwd", "st", "attacker", "centre forward",
            "center forward", "number nine", "front man", "frontman"),
}

#: Query words that carry no identifying information and should not reach the
#: fuzzy stage on their own.
_STOPWORDS = {
    "the", "a", "an", "guy", "lad", "player", "one", "that", "this", "他",
    "his", "him", "her", "their", "some", "any", "who", "whos", "is", "at",
    "for", "of", "in", "on", "and", "or", "to", "from", "with", "fpl",
}

Method = Literal[
    "exact",         # web_name or full name hit outright
    "expansion",     # matched via an agent-supplied name expansion
    "surname",       # unique surname
    "descriptive",   # "the Arsenal keeper"
    "fuzzy",         # typo tolerance
    "ambiguous",     # several plausible, caller must ask
    "none",
]

Status = Literal["a", "d", "i", "s", "u", "n"]



class PlayerResolver:
    """Resolve free text to concrete players.

        pr = PlayerResolver(bootstrap["elements"], team_resolver)
        pr.resolve("haaland").player
        pr.resolve("silva", squad=[...]).candidates
        pr.resolve("the arsenal keeper").player
    """

    FUZZY_FLOOR = 82.0
    #: Candidates within this many points of the best lexical score are
    #: treated as tied, and the prior is allowed to order them.
    TIE_BAND = 6.0
    #: Below this margin after priors, refuse to pick.
    DECIDE_MARGIN = 0.04

    def __init__(
        self,
        elements: Iterable[dict[str, Any]],
        teams: TeamResolver | None = None,
    ) -> None:
        self.players: list[Player] = [Player.model_validate(e) for e in elements]
        self._by_id = {p.id: p for p in self.players}
        self.teams = teams

        # surface form -> list of player ids. Lists, not scalars: collisions
        # are the normal case, not the exception.
        self._exact: dict[str, list[int]] = {}
        self._surname: dict[str, list[int]] = {}

        for p in self.players:
            for form in self._surface_forms(p):
                self._exact.setdefault(form, []).append(p.id)
            surname = normalise(p.second_name or p.web_name)
            if surname:
                self._surname.setdefault(surname, []).append(p.id)
                # last token too, for "alexander-arnold" -> "arnold" and
                # for Spanish/Portuguese double surnames
                tokens = surname.split()
                if len(tokens) > 1:
                    self._surname.setdefault(tokens[-1], []).append(p.id)

        self._fuzzy_keys = list(self._exact.keys())

    @staticmethod
    def _surface_forms(p: Player) -> set[str]:
        forms = {
            normalise(p.web_name),
            normalise(p.second_name),
            normalise(f"{p.first_name} {p.second_name}"),
            normalise(f"{p.first_name} {p.web_name}"),
        }
        # initial + surname: "m salah", "b fernandes"
        if p.first_name and p.second_name:
            forms.add(normalise(f"{p.first_name[0]} {p.second_name}"))
        return {f for f in forms if f}

    # -- helpers ------------------------------------------------------------

    def team_of(self, player: Player):
        if self.teams is None:
            return None
        return next(
            (t for t in self.teams.teams.values() if t.id == player.team), None
        )

    def by_id(self, player_id: int) -> Player | None:
        return self._by_id.get(player_id)

    def _prior(self, p: Player) -> float:
        """Form-based likelihood that a vague reference means THIS player.

        Minutes separate a regular starter from a bench player with the same
        surname; ownership breaks what is left. Squad membership is handled
        separately on the candidate, because it is a categorically stronger
        signal than either.
        """
        minutes = min(p.minutes / 2000.0, 1.0)          # ~a full season
        owned = min(p.selected_by_percent / 40.0, 1.0)  # 40%+ is elite-owned
        return round(0.7 * minutes + 0.3 * owned, 6)

    def _rank(
        self, hits: list[tuple[int, float]], method: Method, squad: set[int]
    ) -> list[PlayerCandidate]:
        out = [
            PlayerCandidate(
                player=self._by_id[pid],
                score=score / 100,
                prior=self._prior(self._by_id[pid]),
                in_squad=pid in squad,
                method=method,
            )
            for pid, score in hits
            if pid in self._by_id
        ]
        return sorted(out, key=lambda c: c.combined, reverse=True)

    def _decide(
        self, query: str, cands: list[PlayerCandidate], method: Method
    ) -> PlayerResolution:
        """Pick a winner, or hand back candidates if it is too close."""
        if not cands:
            return PlayerResolution(query=query, method="none")
        if len(cands) == 1:
            return PlayerResolution(
                query=query, player=cands[0].player, method=method, candidates=cands
            )
        best, second = cands[0], cands[1]
        # tie on lexical score AND not separated by prior -> ask
        lexically_tied = (best.score - second.score) * 100 <= self.TIE_BAND
        if lexically_tied and best.combined - second.combined < self.DECIDE_MARGIN:
            return PlayerResolution(
                query=query, method="ambiguous", candidates=cands[:5],
                note=f"{len(cands)} players match {query!r} about equally well.",
            )
        note = None
        if lexically_tied:
            note = (
                f"Several players match {query!r}; picked "
                f"{best.player.web_name} on squad membership, minutes and ownership."
            )
        return PlayerResolution(
            query=query, player=best.player, method=method,
            candidates=cands[:5], note=note,
        )

    # -- descriptive path ---------------------------------------------------

    def _parse_descriptor(self, text: str) -> tuple[str | None, Any, Any]:
        """Pull a position and/or a club out of 'the arsenal keeper'.

        Returns (position, team, unresolved_team_reference). The third value
        is set when the text clearly names a club but that club reference is
        itself ambiguous or out of the league - "city defender" must NOT
        quietly become "any defender".
        """
        position = None
        for pos, words in POSITION_WORDS.items():
            if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
                position = pos
                break

        team = None
        unresolved = None
        if self.teams is not None:
            # longest-first n-gram scan, so "man city" beats "city"
            tokens = text.split()
            for n in range(min(3, len(tokens)), 0, -1):
                for i in range(len(tokens) - n + 1):
                    span = " ".join(tokens[i:i + n])
                    if span in _STOPWORDS:
                        continue
                    res = self.teams.resolve(span)
                    if res.resolved:
                        team = res.team
                        break
                    if unresolved is None and (
                        res.needs_clarification or res.not_in_league
                    ):
                        unresolved = res
                if team:
                    break
        return position, team, unresolved

    def _try_descriptive(
        self, query: str, text: str, squad: set[int]
    ) -> PlayerResolution | None:
        position, team, unresolved = self._parse_descriptor(text)

        # A club was named but could not be pinned down. Never widen the
        # search to every club - that turns "city defender" into a list of
        # Arsenal and Liverpool players.
        if team is None and unresolved is not None:
            if unresolved.not_in_league:
                return PlayerResolution(
                    query=query, method="none",
                    note=f"{unresolved.known_short_name} are not in the Premier "
                    f"League this season, so they have no FPL players.",
                )
            names = [t.name for t in unresolved.alternatives]
            return PlayerResolution(
                query=query, method="ambiguous", team_candidates=names,
                note=f"The club reference is ambiguous between {len(names)} "
                f"clubs, so no player filter was applied.",
            )

        if position is None and team is None:
            return None
        pool = [
            p for p in self.players
            if (position is None or p.position == position)
            and (team is None or p.team == team.id)
        ]
        if not pool:
            return PlayerResolution(
                query=query, method="none",
                note="No player matches that description in the current squad data.",
            )
        # nothing lexical to go on, so this is entirely prior-driven: the
        # "Arsenal keeper" is whoever actually plays.
        cands = sorted(
            (
                PlayerCandidate(
                    player=p, score=0.6, prior=self._prior(p),
                    in_squad=p.id in squad, method="descriptive",
                )
                for p in pool
            ),
            key=lambda c: c.combined,
            reverse=True,
        )
        label = " ".join(x for x in (team.short_name if team else None, position) if x)
        if len(cands) > 1 and cands[0].combined - cands[1].combined < 0.012:
            return PlayerResolution(
                query=query, method="ambiguous", candidates=cands[:5],
                note=f"Several {label} options are plausible.",
            )
        return PlayerResolution(
            query=query, player=cands[0].player, method="descriptive",
            candidates=cands[:5],
            note=f"Read as the {label} with the most minutes.",
        )

    # -- main ---------------------------------------------------------------

    def resolve(
        self,
        query: str | PlayerQuery,
        squad: Iterable[int] | None = None,
        team_hint: int | None = None,
        position_hint: str | None = None,
    ) -> PlayerResolution:
        """Resolve a player reference.

        Accepts either a bare string (convenient for tests and direct calls)
        or a PlayerQuery, which is what the agent tool layer sends. The
        keyword arguments are a shorthand for the equivalent PlayerQuery
        fields and are ignored when a PlayerQuery is passed.
        """
        if isinstance(query, str):
            q = PlayerQuery(
                text=query,
                squad=list(squad or ()),
                position=position_hint,  # type: ignore[arg-type]
            )
            team_id = team_hint
        else:
            q = query
            team_id = None
            if q.team and self.teams is not None:
                tres = self.teams.resolve(q.team)
                if tres.resolved:
                    team_id = tres.team.id
                elif tres.not_in_league:
                    return PlayerResolution(
                        query=q.text, method="none",
                        note=f"{tres.known_short_name} are not in the Premier "
                        f"League this season, so they have no FPL players.",
                    )
                elif tres.needs_clarification:
                    names = [t.name for t in tres.alternatives]
                    return PlayerResolution(
                        query=q.text, method="ambiguous", team_candidates=names,
                        note=f"The club reference {q.team!r} is ambiguous "
                        f"between {len(names)} clubs.",
                    )

        squad_set = set(q.squad)
        position = q.position

        def _filtered(ids: list[int]) -> list[int]:
            out = ids
            if team_id is not None:
                out = [i for i in out if self._by_id[i].team == team_id]
            if position is not None:
                out = [i for i in out if self._by_id[i].position == position]
            return out or ids  # a hint that eliminates everything is a bad hint

        def _lookup(term: str, method: Method) -> PlayerResolution | None:
            """Try one term through the deterministic index."""
            key = normalise(term)
            if not key:
                return None
            if key in self._exact:
                hits = [(pid, 100.0) for pid in _filtered(self._exact[key])]
                return self._decide(q.text, self._rank(hits, method, squad_set), method)
            if key in self._surname:
                hits = [(pid, 100.0) for pid in _filtered(self._surname[key])]
                return self._decide(q.text, self._rank(hits, method, squad_set), method)
            return None

        text = normalise(q.text)
        if not text and not q.expansions:
            return PlayerResolution(query=q.text, method="none")

        # 1. the literal reference, exact then surname
        hit = _lookup(q.text, "exact")
        if hit is not None:
            return hit

        # 2. agent-supplied expansions, in the order given. These carry the
        #    world knowledge this module deliberately does not hold: "KDB",
        #    "the Egyptian King", "Trent". Each is confirmed against the
        #    payload, so a stale or invented guess simply fails.
        for term in q.expansions:
            hit = _lookup(term, "expansion")
            if hit is not None:
                return hit

        # 3. descriptive: "the arsenal keeper", "spurs striker"
        descriptive = self._try_descriptive(q.text, text, squad_set)
        if descriptive is not None:
            return descriptive

        # 4. fuzzy, over the literal text and then each expansion. Same
        #    reasoning as the team resolver: NOT WRatio, whose partial-
        #    substring bonus produces confident wrong matches on shared
        #    tokens. max(ratio, token_sort_ratio) keeps typos high and drops
        #    unrelated names.
        for term, method in [(q.text, "fuzzy")] + [
            (e, "expansion") for e in q.expansions
        ]:
            content = " ".join(
                t for t in normalise(term).split() if t not in _STOPWORDS
            )
            if len(content) < 3:
                continue
            matches = process.extract(
                content, self._fuzzy_keys, scorer=self._score, limit=12
            )
            best_per_player: dict[int, float] = {}
            for form, score, _ in matches:
                if score < self.FUZZY_FLOOR:
                    continue
                for pid in self._exact[form]:
                    if score > best_per_player.get(pid, 0.0):
                        best_per_player[pid] = score
            if not best_per_player:
                continue
            keep = set(_filtered(list(best_per_player)))
            hits = [(pid, sc) for pid, sc in best_per_player.items() if pid in keep]
            return self._decide(
                q.text, self._rank(hits, method, squad_set), method  # type: ignore[arg-type]
            )

        note = None
        if q.expansions:
            note = (
                f"Neither {q.text!r} nor the suggested name(s) "
                f"({', '.join(q.expansions)}) match any player in this "
                f"season's squad list. They may have left the league."
            )
        return PlayerResolution(query=q.text, method="none", note=note)

    @staticmethod
    def _score(a: str, b: str, *, processor=None, score_cutoff=None) -> float:
        return max(fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b))