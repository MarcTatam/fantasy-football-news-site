from .models.report import Report
from .datasources.fpl import FPLClient
from .formatter import ReportFormatter
from .generator import ReportGenerator

def create_report(gw_id:int,fpl_client:FPLClient, formatter:ReportFormatter, report_generator:ReportGenerator)->Report:
    teams, league_name = fpl_client.get_teams()
    formatter.format_team_players(teams, gw_id)
    formatter.format_player_names(teams)
    task_prompt = formatter.format_prompt(teams,league_name,gw_id)
    return report_generator.run(task_prompt)
