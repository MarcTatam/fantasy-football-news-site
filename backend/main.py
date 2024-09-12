import functions_framework
from flask import Request
from football_reports.datasources.fpl import FPLClient
from football_reports.datasources.firestore import FirestoreClient
from football_reports.formatter import ReportFormatter
from football_reports.generator import RerportGenerator

fpl_client = FPLClient()
firestore_client = FirestoreClient()
formatter = ReportFormatter(fpl_client)
report_generator = RerportGenerator()

@functions_framework.http
def entry_point(request:Request):
    # Set CORS headers for the preflight request
    if request.method == "OPTIONS":
        # Allows GET requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }

        return ("", 204, headers)
    gw_id, is_complete = fpl_client.get_gameweek()
    if is_complete:
        db_result = firestore_client.get_from_db(gw_id)
    if db_result:
        return (db_result.model_dump_json(),200, headers)
    teams, league_name = fpl_client.get_teams()
    formatter.format_team_players(teams, gw_id)
    formatter.format_player_names(teams)
    task_prompt = formatter.format_prompt(teams,league_name,gw_id)
    generated_report = report_generator.run(task_prompt)
    firestore_client.add_to_db(generated_report, gw_id, is_complete)
    # Set CORS headers for the main request
    headers = {"Access-Control-Allow-Origin": "*"}
    return (generated_report.model_dump_json(),200, headers)

entry_point(None)