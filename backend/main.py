import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from football_reports.datasources.fpl import FPLClient
from football_reports.datasources.firestore import FirestoreClient
from football_reports.formatter import ReportFormatter
from football_reports.generator import ReportGenerator
from football_reports.models.response import ReportResponse
from football_reports.models.report import Report
from football_reports.report_utils import create_report, create_summary
from functools import partial
from dotenv import load_dotenv

load_dotenv()

fpl_client = FPLClient()
firestore_client = FirestoreClient()
formatter = ReportFormatter(fpl_client)
report_generator = ReportGenerator()

app = FastAPI()

allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
    max_age=3600,
)


@app.get("/")
def create_report_endpoint()->Report:
    gw_id, is_complete = fpl_client.get_current_gameweek()
    if is_complete:
        db_result = firestore_client.get_report_from_db(gw_id)
        if db_result:
            return db_result
    generated_report = create_report(gw_id, fpl_client, formatter,report_generator)
    firestore_client.add_report_to_db(generated_report, gw_id, is_complete)
    return generated_report

@app.get("/reports")
async def get_all_reports_endpoint() -> list[ReportResponse]:
    reports = firestore_client.get_all_reports_from_db()
    gw_id, _ = fpl_client.get_current_gameweek()
    
    if len(reports) != gw_id:
        missing = set(range(1, gw_id + 1))
        for report in reports:
            missing.remove(report.gw_id)
        missing = list(missing)
        
        partial_create = partial(create_report, fpl_client=fpl_client, formatter=formatter, report_generator=report_generator)
        
        # Use asyncio.gather without asyncio.run
        missing_reports: list[Report] = await asyncio.gather(*[asyncio.to_thread(partial_create, missing_id) for missing_id in missing])
        
        formatted_missing = [
            ReportResponse(
                headline=missing_reports[i].headline,
                body=missing_reports[i].body,
                gw_id=missing[i],
                complete=False if missing[i] == gw_id else True
            )
            for i in range(len(missing))
        ]
        
        reports += formatted_missing
    
    return reports

@app.get("/report/{gw_id}")
def get_report_endpoint(gw_id:int)->Report:
    db_result = firestore_client.get_report_from_db(gw_id)
    if db_result:
        return db_result
    generated_report = create_report(gw_id, fpl_client, formatter,report_generator)
    complete = fpl_client.check_gameweek_complete(gw_id)
    firestore_client.add_report_to_db(generated_report, gw_id, complete)
    return generated_report

@app.get('/summary')
def get_summary_endpoint():
    return create_summary(firestore_client,report_generator)

@app.get('/teams/history')
def get_team_histories():
    return fpl_client.get_teams_history()