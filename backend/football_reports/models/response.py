from pydantic import BaseModel
from .report import Report


class ReportResponse(Report):
    complete:bool = True
    gw_id:int = -1