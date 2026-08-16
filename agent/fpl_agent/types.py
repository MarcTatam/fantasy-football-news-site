from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

class Team(BaseModel):
    """A club as it exists in the current season's bootstrap-static payload.

    Built straight from a bootstrap-static `teams` entry, which carries many
    more keys than we need; extras are ignored rather than rejected so a new
    FPL field does not break the resolver mid-season.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int = Field(description="Season-specific FPL id. Do not persist.")
    code: int = Field(description="Cross-season club code. Safe to persist.")
    name: str
    short_name: str
    strength: int | None = None

    @field_validator("short_name")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    def __str__(self) -> str:
        return self.name

#: Every way resolution can terminate. Literal rather than str so a typo in a
#: branch of the cascade fails at construction instead of silently creating an
#: unhandled method the agent layer will never match on.
Method = Literal[
    "exact", "alias", "prefix", "fuzzy", "ambiguous", "not_in_league", "none"
]

class TeamResolution(BaseModel):
    """Outcome of one resolution attempt.

    Intentionally never raises on a miss: the agent needs to distinguish
    "wrong club" from "club not in the league" from "I have no idea", and
    exceptions collapse all three.
    """

    model_config = ConfigDict(frozen=True)

    query: str
    team: Team | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    method: Method = "none"
    alternatives: list[Team] = Field(default_factory=list)
    known_short_name: str | None = Field(
        default=None,
        description=(
            "Set when method == 'not_in_league': the club we recognised but "
            "which is absent from this season's payload, e.g. 'WBA'."
        ),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved(self) -> bool:
        return self.team is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def needs_clarification(self) -> bool:
        return self.team is None and bool(self.alternatives)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def not_in_league(self) -> bool:
        return self.method == "not_in_league"

    def clarifying_question(self) -> str | None:
        """Question to put to the user, or None if no ambiguity."""
        if not self.needs_clarification:
            return None
        names = [t.name for t in self.alternatives]
        opts = ", ".join(names[:-1]) + f" or {names[-1]}"
        return f"Did you mean {opts}?"

SEASON_LENGTH = 38

class Gameweek(BaseModel):
    """One entry from bootstrap-static's `events` array."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int = Field(ge=1, le=SEASON_LENGTH)
    name: str
    deadline_time: datetime
    finished: bool = False
    is_previous: bool = False
    is_current: bool = False
    is_next: bool = False

    def __str__(self) -> str:
        return f"GW{self.id}"

class GameweekResolution(BaseModel):
    """Outcome of one gameweek resolution attempt."""

    model_config = ConfigDict(frozen=True)

    query: str
    gameweeks: list[Gameweek] = Field(default_factory=list)
    method: Method = "none"
    note: str | None = Field(
        default=None,
        description="Why this resolution was made, when it is not obvious. "
        "Surface it to the user for anything deadline- or clamp-related.",
    )
    clamped: bool = Field(
        default=False,
        description="True when the requested range ran past GW38 and was cut.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved(self) -> bool:
        return bool(self.gameweeks)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ids(self) -> list[int]:
        return [gw.id for gw in self.gameweeks]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_single(self) -> bool:
        return len(self.gameweeks) == 1

    @property
    def first(self) -> Gameweek | None:
        return self.gameweeks[0] if self.gameweeks else None

    def describe(self) -> str:
        if not self.gameweeks:
            return "no gameweek"
        if len(self.gameweeks) == 1:
            return f"GW{self.gameweeks[0].id}"
        return f"GW{self.gameweeks[0].id}-{self.gameweeks[-1].id}"

class Player(BaseModel):
    """One entry from bootstrap-static's `elements` array."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int = Field(description="Season-scoped FPL id. Do not persist.")
    code: int = Field(description="Cross-season player code. Safe to persist.")
    first_name: str = ""
    second_name: str = ""
    web_name: str
    team: int = Field(description="Season-scoped team id, matches Team.id.")
    element_type: int
    now_cost: int = 0
    total_points: int = 0
    minutes: int = 0
    status: str = "a"
    selected_by_percent: float = 0.0
    chance_of_playing_next_round: int | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def position(self) -> str:
        return POSITIONS.get(self.element_type, "UNK")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.second_name) if p)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def price(self) -> float:
        """now_cost is in tenths of a million."""
        return self.now_cost / 10

    @computed_field  # type: ignore[prop-decorator]
    @property
    def available(self) -> bool:
        return self.status == "a"

    @property
    def status_text(self) -> str:
        return STATUS_TEXT.get(self.status, self.status)

    def __str__(self) -> str:
        return f"{self.web_name} ({self.position}, £{self.price}m)"


class PlayerQuery(BaseModel):
    """Tool input schema for player resolution.

    This model IS the tool contract - its JSON schema is what the agent sees,
    so the field descriptions are load-bearing prompt text, not comments.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        description="The player reference exactly as the user wrote it, "
        "unmodified. Used for matching, logging and clarifying questions.",
    )
    expansions: list[str] = Field(
        default_factory=list,
        description=(
            "Full or surname forms you believe `text` refers to, best guess "
            "first. Fill this whenever `text` is an abbreviation, nickname, "
            "diminutive or indirect reference that is not the player's actual "
            "name: 'KDB' -> ['de bruyne'], 'the Egyptian King' -> ['salah'], "
            "'Trent' -> ['alexander-arnold']. Give several when unsure; they "
            "are tried in order. Guesses are checked against the current "
            "squad list, so a wrong or outdated guess returns no match rather "
            "than the wrong player - it is safe to guess. Leave empty when "
            "`text` is already a name."
        ),
    )
    team: str | None = Field(
        default=None,
        description="Club mentioned or implied by the user, free text "
        "('Arsenal', 'spurs'). Narrows candidates; ignored if it eliminates "
        "every match.",
    )
    position: Literal["GKP", "DEF", "MID", "FWD"] | None = Field(
        default=None,
        description="Position mentioned or implied by the user.",
    )
    squad: list[int] = Field(
        default_factory=list,
        description="FPL element ids in the user's own team. Pass these "
        "whenever known: they are the strongest available disambiguator, "
        "since references like 'my Silva' or 'who replaces X' almost always "
        "mean a player the user owns.",
    )


class PlayerCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    player: Player
    score: float = Field(ge=0.0, le=1.0, description="Lexical match strength.")
    prior: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Form-based likelihood from minutes and ownership.",
    )
    in_squad: bool = Field(
        default=False, description="Player is in the user's own team."
    )
    method: Method = "none"

    #: Squad membership is by far the strongest disambiguator available -
    #: "who replaces my Silva" is nearly always about the Silva they own - so
    #: it gets its own weight, large enough to settle a lexical tie on its
    #: own. The continuous prior is a weaker nudge and needs a wide gap to
    #: decide anything.
    SQUAD_WEIGHT: ClassVar[float] = 0.20
    PRIOR_WEIGHT: ClassVar[float] = 0.08

    @computed_field  # type: ignore[prop-decorator]
    @property
    def combined(self) -> float:
        """Lexical score dominates; context only separates near-ties."""
        return round(
            self.score
            + self.SQUAD_WEIGHT * float(self.in_squad)
            + self.PRIOR_WEIGHT * self.prior,
            6,
        )


class PlayerResolution(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    player: Player | None = None
    method: Method = "none"
    candidates: list[PlayerCandidate] = Field(default_factory=list)
    team_candidates: list[str] = Field(
        default_factory=list,
        description="Set when the query named a club that could not be pinned "
        "down (e.g. 'city'). These are the club names in contention; the "
        "search was NOT widened to all clubs.",
    )
    note: str | None = Field(
        default=None,
        description="Declarative explanation of the outcome. Never a question "
        "- the agent phrases those.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved(self) -> bool:
        return self.player is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def needs_clarification(self) -> bool:
        return self.player is None and len(self.candidates) > 1