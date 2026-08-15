"""
Team resolution layer.

Maps free-text team references ("spurs", "man u", "the gunners", "NFO")
onto canonical FPL team records.

Design notes
------------
* The alias table is keyed by FPL `short_name` (ARS, MUN, NFO...), which is
  stable across seasons. FPL's numeric `id` is NOT stable - it is reassigned
  alphabetically each season as clubs are promoted/relegated - so never
  hard-code it.
* The table deliberately contains a superset of clubs (including ones
  currently outside the Premier League). At construction time the resolver
  binds only to the clubs present in the bootstrap-static payload you pass
  in, so promotions/relegations need no code change.
* TeamResolution is a cascade: exact alias -> prefix -> fuzzy. Every step returns
  a confidence and the runner-up candidates, so the agent can decide whether
  to ask for clarification.
"""
import re
import unicodedata
from typing import Any, Iterable
from rapidfuzz import fuzz, process

from ..types import Team, TeamResolution

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

# Tokens that carry no discriminating information for English clubs.
_NOISE_TOKENS = {"fc", "afc", "cf", "the"}

# Abbreviations folded to a single form. Applied to BOTH the alias table at
# build time and the query at lookup time, so the two sides always agree.
# This is what stops 'manchester utd' from fuzzy-matching Man City.
_TOKEN_SYNONYMS = {
    "utd": "united",
    "man": "manchester",
    "nottm": "nottingham",
    "notts": "nottingham",
    "sheff": "sheffield",
    "brom": "bromwich",
    "wanderers": "wanderers",
    "hotspur": "",
    "hotspurs": "",
}

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Fold a raw user string into a comparable key.

    'Nott'm Forest' -> 'nottm forest'
    'Brighton & Hove Albion FC' -> 'brighton hove albion'
    'Wolverhampton  Wanderers' -> 'wolverhampton wanderers'
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = text.replace("&", " and ")
    text = _PUNCT_RE.sub(" ", text)
    tokens = [t for t in _WS_RE.split(text) if t and t not in _NOISE_TOKENS]
    tokens = [_TOKEN_SYNONYMS.get(t, t) for t in tokens]
    return " ".join(t for t in tokens if t)


# ---------------------------------------------------------------------------
# Alias table
# ---------------------------------------------------------------------------

# short_name -> aliases. Full names, colloquialisms, nicknames, common typos
# and text-speak. Keep adding to this; it is the highest-leverage file in the
# resolution layer and costs nothing to extend.
TEAM_ALIASES: dict[str, list[str]] = {
    "ARS": ["arsenal", "gunners", "the arsenal", "arse"],
    "AVL": ["aston villa", "villa", "villans", "the villa"],
    "BOU": ["bournemouth", "afc bournemouth", "cherries", "boscombe"],
    "BRE": ["brentford", "bees"],
    "BHA": ["brighton", "brighton and hove albion", "brighton hove albion",
            "seagulls", "the albion"],
    "BUR": ["burnley", "clarets"],
    "CHE": ["chelsea", "blues", "the blues", "pensioners"],
    "COV": ["coventry", "coventry city", "ccfc", "the sky blues"],
    "CRY": ["crystal palace", "palace", "eagles", "cpfc"],
    "EVE": ["everton", "toffees", "the toffees"],
    "FUL": ["fulham", "cottagers"],
    "HUL": ["hull", "hull city", "tigers", "the tigers", "hcafc"],
    "IPS": ["ipswich", "ipswich town", "tractor boys", "blues of suffolk"],
    "LEE": ["leeds", "leeds united", "whites", "peacocks"],
    "LEI": ["leicester", "leicester city", "foxes"],
    "LIV": ["liverpool", "pool", "the kop", "lfc"],
    "LUT": ["luton", "luton town", "hatters"],
    "MID": ["middlesbrough", "boro", "the boro", "smoggies"],
    "MCI": ["man city", "manchester city", "city of manchester", "citizens",
            "cityzens", "mancity", "mcfc", "citeh", "the citizens"],
    "MUN": ["man utd", "man united", "manchester united", "man u", "manu",
            "united of manchester", "red devils", "mufc", "mu"],
    "NEW": ["newcastle", "newcastle united", "toon", "magpies", "the toon",
            "nufc", "toon army", "the toon army"],
    "NFO": ["nottingham forest", "nottm forest", "notts forest", "forest",
            "tricky trees", "nffc"],
    "NOR": ["norwich", "norwich city", "canaries"],
    "SHU": ["sheffield united", "sheff utd", "sheff united", "blades"],
    "SOU": ["southampton", "saints", "the saints"],
    "STO": ["stoke", "stoke city", "potters"],
    "SUN": ["sunderland", "black cats", "mackems"],
    "TOT": ["tottenham", "tottenham hotspur", "spurs", "the spurs", "thfc",
            "lilywhites"],
    "WAT": ["watford", "hornets"],
    "WBA": ["west brom", "west bromwich albion", "west bromwich", "baggies",
            "throstles", "wba"],
    "WHU": ["west ham", "west ham united", "hammers", "irons", "the irons",
            "whufc"],
    "WOL": ["wolves", "wolverhampton", "wolverhampton wanderers", "wanderers"],
}

# Bare words that genuinely map to more than one club. Never silently pick a
# winner for these - surface them and let the agent disambiguate, ideally
# using conversation context (e.g. the fixture under discussion).
AMBIGUOUS_ALIASES: dict[str, list[str]] = {
    "united": ["MUN", "NEW", "WHU", "LEE", "SHU"],
    "city": ["MCI", "LEI", "NOR", "STO", "COV", "HUL"],
    "reds": ["LIV", "MUN", "NFO"],
    "albion": ["BHA", "WBA"],
    "town": ["IPS", "LUT"],
    # Coventry are *the* Sky Blues, but Man City wear the same nickname often
    # enough that guessing is not worth it.
    "sky blues": ["COV", "MCI"],
    # Chelsea dominate "the Blues" nationally, but Ipswich and Everton both
    # use it. Drop IPS/EVE from this list if you would rather default to CHE.
    "blues": ["CHE", "IPS", "EVE"],
    # 'man' normalises to 'manchester', so this catches both bare forms.
    "manchester": ["MUN", "MCI"],
}


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class TeamResolver:
    """Resolve free text to a Team.

    Construct from the `teams` array of bootstrap-static:

        payload = requests.get(BOOTSTRAP_URL).json()
        resolver = TeamResolver(payload["teams"])
        resolver.resolve("spurs").team.name  # -> 'Spurs'
    """

    #: below this fuzzy score we return nothing rather than guess
    FUZZY_FLOOR = 82
    #: if the top two fuzzy candidates are this close, treat as ambiguous
    FUZZY_MARGIN = 6

    def __init__(self, teams: Iterable[Team]):
        self.teams = teams

        # alias key -> short_name, restricted to clubs actually in the payload
        self._index: dict[str, str] = {}
        # alias key -> short_name for clubs we recognise but which are absent
        # from this season's payload. Checked BEFORE fuzzy, so 'Leeds United'
        # reports "not in the league" instead of fuzzy-matching Man Utd.
        self._absent: dict[str, str] = {}
        for short_name, aliases in TEAM_ALIASES.items():
            target = self._index if short_name in self.teams else self._absent
            for alias in aliases:
                target[normalise(alias)] = short_name

        # the payload's own strings, which may differ from our aliases
        for short_name, team in self.teams.items():
            self._index.setdefault(normalise(team.name), short_name)
            self._index.setdefault(normalise(team.short_name), short_name)

        self._ambiguous: dict[str, list[str]] = {
            normalise(k): [s for s in v if s in self.teams]
            for k, v in AMBIGUOUS_ALIASES.items()
        }

        # Fuzzy runs over in-league AND absent clubs, so a typo'd relegated
        # club still lands on "not in the league" rather than a wrong club.
        self._keys = list(self._index.keys())
        self._all_keys = self._keys + list(self._absent.keys())

    # -- public API ---------------------------------------------------------

    def resolve(self, query: str) -> TeamResolution:
        key = normalise(query)
        if not key:
            return TeamResolution(query=query)

        # 1. ambiguous bare words - refuse to guess.
        #    Note the candidate list is filtered to this season's clubs, so a
        #    form that WAS ambiguous can collapse to a single live club.
        if self._ambiguous.get(key):
            candidates = [self.teams[s] for s in self._ambiguous[key]]
            if len(candidates) == 1:
                return TeamResolution(
                    query=query, team=candidates[0],
                    confidence=0.85, method="alias",
                )
            return TeamResolution(
                query=query, method="ambiguous", alternatives=candidates,
            )

        # 2. exact alias hit
        if key in self._index:
            team = self.teams[self._index[key]]
            method = "exact" if key == normalise(team.name) else "alias"
            return TeamResolution(query=query, team=team, confidence=1.0, method=method)

        # 3. a club we know, but not one playing in the league this season
        if key in self._absent:
            return TeamResolution(
                query=query, confidence=1.0, method="not_in_league",
                known_short_name=self._absent[key],
            )

        # 4. unique prefix - handles 'tottenh', 'wolverhamp'
        prefixed = {self._index[k] for k in self._keys if k.startswith(key)}
        if len(prefixed) == 1 and len(key) >= 3:
            return TeamResolution(
                query=query, team=self.teams[prefixed.pop()],
                confidence=0.9, method="prefix",
            )

        # 5. fuzzy fallback - typos, spacing, phone-keyboard mangling.
        #    NOT WRatio: its partial-substring bonus scores 'leeds united'
        #    against 'united of manchester' at 85, i.e. confidently wrong.
        #    Plain ratio (with token_sort for word-order shuffles) keeps every
        #    genuine typo above 85 while dropping those pairs below 40.
        matches = process.extract(
            key, self._all_keys, scorer=self._score, limit=8
        )
        matches = [m for m in matches if m[1] >= self.FUZZY_FLOOR]
        if not matches:
            return TeamResolution(query=query, method="none")

        ranked: list[tuple[str, float]] = []
        seen: set[str] = set()
        for alias, score, _ in matches:
            short = self._index.get(alias) or self._absent[alias]
            if short in seen:
                continue
            seen.add(short)
            ranked.append((short, score))

        best_short, best_score = ranked[0]
        if len(ranked) > 1 and best_score - ranked[1][1] < self.FUZZY_MARGIN:
            alts = [self.teams[s] for s, _ in ranked[:3] if s in self.teams]
            return TeamResolution(
                query=query, method="ambiguous", alternatives=alts,
            )

        if best_short not in self.teams:
            return TeamResolution(
                query=query, confidence=best_score / 100,
                method="not_in_league", known_short_name=best_short,
            )

        return TeamResolution(
            query=query, team=self.teams[best_short],
            confidence=best_score / 100, method="fuzzy",
        )

    @staticmethod
    def _score(a: str, b: str) -> float:
        return max(fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b))

    def resolve_many(self, queries: Iterable[str]) -> list[TeamResolution]:
        return [self.resolve(q) for q in queries]

    def by_short_name(self, short_name: str) -> Team | None:
        return self.teams.get(short_name.upper())

    def all_teams(self) -> list[Team]:
        return sorted(self.teams.values(), key=lambda t: t.name)