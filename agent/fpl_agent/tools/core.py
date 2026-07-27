from typing import Literal

def search_players(position:Literal["gk", "def", "mid", "fwd"], max_price:float, min_form:float, team:int, sort_by:Literal["ascending", "descending"], limit:int)->list:
    pass

def get_player_detail(player_id:int)->dict:
    pass

def compare_players(player_ids:list[int])->list[dict]:
    pass

def get_fixtures(team_id:int, next_n:int)->list:
    pass

def get_gameweek_status():
    pass