import requests
from typing import Literal
from time import time
from fpl_agent.types import Player

class FPLCaller:
    def __init__(self):
        self._refresh_data()

    def _refresh_data(self):
        res = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
        res.raise_for_status()
        self.expiry = time() + 60*60
        self.data = res.json()

    def _valid_cache(self):
        return time() < self.expiry


    def get_data(self):
        if not self._valid_cache():
            self._refresh_data()
        return self.data

def search_players(position:Literal["gk", "def", "mid", "fwd"], max_price:float, min_form:float, team:int, sort_by:Literal["ascending", "descending"], limit:int)->list[Player]:
    pass

def get_player_detail(player_id:int)->dict:
    pass

def compare_players(player_ids:list[int])->list[dict]:
    pass

def get_fixtures(team_id:int, next_n:int)->list:
    pass

def get_gameweek_status():
    pass