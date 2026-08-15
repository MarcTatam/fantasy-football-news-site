from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

class Player(BaseModel):
    first_name:str
    second_name:str
    price:float
    player_id:int = Field(alias="id")

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