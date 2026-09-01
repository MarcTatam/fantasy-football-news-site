import requests
from typing import Literal, TypeVar
from time import time
from pydantic import BaseModel
from fpl_agent.types import Player, Gameweek, Team

T = TypeVar("T", bound=BaseModel)

class FPLCaller:
    def __init__(self):
        self._refresh_data()

    def _refresh_data(self):
        res = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
        res.raise_for_status()
        self.expiry = time() + 60*60
        self.data:dict = res.json()

    def _valid_cache(self):
        return time() < self.expiry


    def get_data(self):
        if not self._valid_cache():
            self._refresh_data()
        return self.data

    def parse_data(self, key:str, model: type[T])->list[type[T]]:
        if not self._valid_cache():
            self._refresh_data()
        unparsed = self.data.get(key,[])
        parsed = [model.model_validate(u) for u in unparsed]
        return parsed

caller = FPLCaller()

def get_gameweeks()->list[Gameweek]:
    return caller.parse_data("events", Gameweek)

def get_players()->list[Player]:
    return caller.parse_data("elements", Player)

def get_teams()->list[Team]:
    return caller.parse_data("teams", Team)

def search_players(position:Literal["gk", "def", "mid", "fwd"], max_price:float, min_form:float, team:int, sort_by:Literal["ascending", "descending"], limit:int)->list[Player]:
    pass

def get_player_detail(player_id:int)->Player:
    players = get_players()
    for player in players:
        if player.id == player_id:
            return player
    raise NameError(name=player_id)

def compare_players(player_ids:list[int])->list[dict]:
    pass

def get_fixtures(team_id:int, next_n:int)->list:
    pass

def get_gameweek_status():
    pass