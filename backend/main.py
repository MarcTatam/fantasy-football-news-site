import asyncio
from fastapi import FastAPI, Response
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

@app.options("/")
def pre_flight():
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
    )


@app.get("/")
def create_report_endpoint(response:Response)->Report:
    response.headers.update({"Access-Control-Allow-Origin": "*"})
    gw_id, is_complete = fpl_client.get_current_gameweek()
    if is_complete:
        db_result = firestore_client.get_report_from_db(gw_id)
        if db_result:
            return db_result
    generated_report = create_report(gw_id, fpl_client, formatter,report_generator)
    firestore_client.add_report_to_db(generated_report, gw_id, is_complete)
    return generated_report

@app.get("/reports")
async def get_all_reports_endpoint(response: Response) -> list[ReportResponse]:
    response.headers.update({"Access-Control-Allow-Origin": "*"})
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
def get_report_endpoint(gw_id:int, response:Response)->Report:
    response.headers.update({"Access-Control-Allow-Origin": "*"})
    db_result = firestore_client.get_report_from_db(gw_id)
    if db_result:
        return db_result
    generated_report = create_report(gw_id, fpl_client, formatter,report_generator)
    complete = fpl_client.check_gameweek_complete(gw_id)
    firestore_client.add_report_to_db(generated_report, gw_id, complete)
    return generated_report

@app.get('/summary')
def get_summary_endpoint(response:Response):
    response.headers.update({"Access-Control-Allow-Origin": "*"})
    return create_summary(firestore_client,report_generator)

@app.get('/teams/history')
def get_team_histories(response:Response):
    response.headers.update({"Access-Control-Allow-Origin": "*"})
    return fpl_client.get_teams_history()