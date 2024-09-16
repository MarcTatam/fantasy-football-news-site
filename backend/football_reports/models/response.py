from pydantic import BaseModel
from .report import Report
from .team import TeamHistory


class ReportResponse(Report):
    complete:bool = True
    gw_id:int = -1

class TeamHistoryResponse(BaseModel):
    teams: list[TeamHistory]