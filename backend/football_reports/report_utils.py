import logging
from .models.report import Report
from .datasources.fpl import FPLClient
from .datasources.firestore import FirestoreClient
from .formatter import ReportFormatter, SummaryFormatter
from .generator import ReportGenerator

logger = logging.getLogger("Utils")

def create_report(gw_id:int,fpl_client:FPLClient, formatter:ReportFormatter, report_generator:ReportGenerator)->Report:
    teams, league_name = fpl_client.get_teams()
    fpl_client.update_teams(teams,gw_id)
    formatter.format_team_players(teams, gw_id)
    formatter.format_player_names(teams)
    validate_teams(teams)
    task_prompt = formatter.format_prompt(teams,league_name,gw_id)
    return report_generator.run(task_prompt)

def create_summary(firestore_client:FirestoreClient, report_generator:ReportGenerator)->Report:
    reports = firestore_client.get_all_reports_from_db()
    formatter = SummaryFormatter()
    task_prompt = formatter.format_prompt(reports)
    return report_generator.run(task_prompt)

def validate_teams(teams:list[dict]):
    for team in teams:
        if not team.get("Team Name"):
            logger.warning("Team name not found")
            return
        team_name = team.get("Team Name")
        if not team.get("Previous Rank"):
            logger.warning(f"{team_name} has no previous rank")
        if not team.get("Points"):
            logger.warning(f"{team_name} has no points")
        if not team.get("Week Points"):
            logger.warning(f"{team_name} has no week points")
        if team.get("Bench Points") is None:
            logger.warning(f"{team_name} has no bench points")
        if not team.get("Manager"):
            logger.warning(f"{team_name} has no manager")
        if not team.get("Captain"):
            logger.warning(f"{team_name} has no captain")
        if not team.get("Vice Captain"):
            logger.warning(f"{team_name} has no vice captain")