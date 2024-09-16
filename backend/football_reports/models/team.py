from pydantic import BaseModel

class TeamHistory(BaseModel):
    team_name: str
    points_history: list[int]