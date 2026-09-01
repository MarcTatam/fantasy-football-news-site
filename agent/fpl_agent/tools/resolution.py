from resolvers import PlayerResolver, TeamResolver, GameweekResolver
from core import get_players, get_teams, get_gameweeks

def resolve_player(query:str)->int:
    resolver = PlayerResolver()
    players = get_players()

def resolve_team(query:str)->str:
    teams = get_teams()
    resolver = TeamResolver(teams)
    resolver.resolve(query)


def resolve_gameweek(query:str)->int:
    gameweeks = get_gameweeks()
    resolver = GameweekResolver(gameweeks)
    res = resolver.resolve(query)
    return res.first