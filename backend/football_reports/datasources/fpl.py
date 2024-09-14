import requests
class FPLClient:
    def __init__(self):
        self.league_id = 161855

    def get_gameweek(self)->tuple[int,bool]:
        response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
        response.raise_for_status()
        response_dict = response.json()
        for event in response_dict.get("events"):
            if event["is_current"]:
                return event["id"], event["finished"]
            
    def get_teams(self)->tuple[list[dict],str]:
        response = requests.get(f"https://fantasy.premierleague.com/api/leagues-classic/{self.league_id}/standings/")
        response.raise_for_status()
        response_dict = response.json()
        league_name = response_dict["league"]["name"]
        teams = []
        for team in response_dict["standings"]["results"]:
            player_dict = {}
            player_dict["Team Name"] = team.get("entry_name","")
            player_dict["Manager"] = team.get("player_name","")
            player_dict["Rank"] = team.get("rank","")
            player_dict["Previous Rank"] = team.get("last_rank","")
            player_dict["Points"] = team.get("total","")
            player_dict["Week Points"] = team.get("event_total","")
            player_dict["ID"] = team.get("entry",0)
            teams.append(player_dict)
        return teams, league_name
    
    def get_player_names(self)->list[dict]:
        response = requests.get(f"https://fantasy.premierleague.com/api/bootstrap-static/")
        response.raise_for_status()
        response_dict = response.json()
        players = response_dict["elements"]
        return players
    
    def get_picks(self, team_id:int, gw_id:int)->dict:
        response = requests.get(f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw_id}/picks/")
        response.raise_for_status()
        response_dict = response.json()
        return response_dict
