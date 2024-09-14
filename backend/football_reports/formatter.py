from .datasources.fpl import FPLClient
from . import prompts

class ReportFormatter:
    def __init__(self, fpl_client:FPLClient):
        self.fpl_client = fpl_client

    def format_team_players(self, teams:list[dict], gw_id:int)->None:
        for team in teams:
            response_dict = self.fpl_client.get_picks(team.get('ID'),gw_id)
            team["Starting 11"] = response_dict["picks"][:11]
            team["Subs"] = response_dict["picks"][11:]
            team["Bench Points"] = response_dict["entry_history"]["points_on_bench"]
    
    def format_player_names(self, teams:list[dict])->None:
        players = self.fpl_client.get_player_names()
        for team in teams:
            for selected in team["Starting 11"]:
                for player in players:
                    if player["id"] == selected.get("element"):
                        name = player["first_name"] + " " + player["second_name"]
                        selected["Name"] = name
                        selected["Points"] = player["event_points"]
                if selected["is_captain"]:
                    team["Captain"] = selected["Name"]
                if selected["is_vice_captain"]:
                    team["Vice Captain"] = selected["Name"]
            for selected in team["Subs"]:
                for player in players:
                    if player["id"] == selected.get("element"):
                        name = player["first_name"] + " " + player["second_name"]
                        selected["Name"] = name
                        selected["Points"] = player["event_points"]

    def format_prompt(self, teams:list[dict], league_name:str, gw_id:int)->str:
        formatted_teams = []
        for team in teams:
            formatted_starters = []
            for player in team["Starting 11"]:
                formatted_starters.append(prompts.player_template.format(player_name=player["Name"], player_points=player["Points"]))
            formatted_bench = []
            for player in team["Subs"]:
                formatted_bench.append(prompts.player_template.format(player_name=player["Name"], player_points=player["Points"]))
            formatted_teams.append(prompts.team_template.format(team_name=team["Team Name"],
                                                        team_rank=team["Rank"],
                                                        team_old_rank=team["Previous Rank"],
                                                        team_points=team["Points"],
                                                        team_week_points=team["Week Points"],
                                                        bench_points=team["Bench Points"],
                                                        team_manager=team["Manager"],
                                                        captain=team["Captain"],
                                                        vice_captain=team["Vice Captain"],
                                                        starting_11="\n".join(formatted_starters),
                                                        bench="\n".join(formatted_bench)
                                                        ))
        return prompts.full_prompt_template.format(league_name=league_name, gameweek=gw_id, teams="\n".join(formatted_teams))