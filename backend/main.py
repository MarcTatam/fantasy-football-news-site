import requests
import functions_framework
from flask import Request
from langchain_openai.chat_models import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field
from google.cloud.firestore import Client

class Report(BaseModel):
    headline:str = Field("The headline of the report")
    body:str = Field("The body of the report")

team_template = """
<Team>
Team Name: {team_name}

League Rank: {team_rank}
Previous League Rank: {team_old_rank}

Points: {team_points}
This Weeks Points: {team_week_points}

Manager: {team_manager}

Starting 11:

{starting_11}

Bench: 

{bench}

Points on the bench: {bench_points}

Captain: {captain}
Vice Captain: {vice_captain}
</Team>
"""

full_prompt_template = """Generate a report in the style of a new outlet covering the weekends football events for my fantasy football league. Make the headline as eyecatching as possible.

Ensure the body goes into the details on the best and worst performers for each team, and whether leaving the players on the bench was a good decision.

If we are beyond the first week of the game, comment on any narrowing or widening gaps or any position swaps.

The league name is {league_name} and we are in week {gameweek} of 38.

Here are the teams:

{teams}

Note that the captains points are doubled.

Try and make the report at least 350 words long and use paragraphs where possible.
"""

player_template = "Player Name: {player_name}, Player Points:{player_points}"

def get_gameweek():
    response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    response.raise_for_status()
    response_dict = response.json()
    for event in response_dict.get("events"):
        if event["is_current"]:
            return event["id"], event["finished"]

def get_from_db(gw_id:int, client:Client)->Report:
    collection = client.collection("reports")
    doc = collection.document(str(gw_id)).get()
    if doc.exists:
        doc_dict = doc.to_dict()
        if doc_dict.get("complete"):
            return Report.model_validate(doc_dict)

def get_teams():
    response = requests.get(f"https://fantasy.premierleague.com/api/leagues-classic/{161855}/standings/")
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

def format_team_players(teams:list[dict], gw_id:int)->None:
    for team in teams:
        response = requests.get(f"https://fantasy.premierleague.com/api/entry/{team.get('ID')}/event/{gw_id}/picks/")
        response.raise_for_status()
        response_dict = response.json()
        team["Starting 11"] = response_dict["picks"][:11]
        team["Subs"] = response_dict["picks"][11:]
        team["Bench Points"] = response_dict["entry_history"]["points_on_bench"]

def format_player_names(teams:list[dict])->None:
    response = requests.get(f"https://fantasy.premierleague.com/api/bootstrap-static/")
    response.raise_for_status()
    response_dict = response.json()
    players = response_dict["elements"]
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

def format_prompt(teams:list[dict], league_name:str, gw_id:int)->str:
    formatted_teams = []
    for team in teams:
        formatted_starters = []
        for player in team["Starting 11"]:
            formatted_starters.append(player_template.format(player_name=player["Name"], player_points=player["Points"]))
        formatted_bench = []
        for player in team["Subs"]:
            formatted_bench.append(player_template.format(player_name=player["Name"], player_points=player["Points"]))
        formatted_teams.append(team_template.format(team_name=team["Team Name"],
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
    return full_prompt_template.format(league_name=league_name, gameweek=gw_id, teams="\n".join(formatted_teams))

def add_to_db(report:Report, gw_id:int, complete:bool, client:Client):
    collection = client.collection("reports")
    if collection.document(str(gw_id)).get().exists:
        collection.document(str(gw_id)).update({
        "headline" : report.headline,
        "body" : report.body,
        "complete" : complete
    }
        )
    collection.add(document_id=str(gw_id), document_data={
        "headline" : report.headline,
        "body" : report.body,
        "complete" : complete
    })

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

    # Set CORS headers for the main request
    client = Client()
    gw_id, is_complete = get_gameweek()
    if is_complete:
        db_result = get_from_db(gw_id, client)
    if db_result:
        return (db_result.model_dump_json(),200, headers)
    teams, league_name = get_teams()
    format_team_players(teams, gw_id)
    format_player_names(teams)
    task_prompt = format_prompt(teams,league_name,gw_id)
    parser = PydanticOutputParser(pydantic_object=Report)
    llm = ChatOpenAI()
    prompt = PromptTemplate(
        template="{task_instructions}\n\n{format_instructions}",
        input_variables=["query"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = prompt | llm | parser
    generated_report:Report = chain.invoke({"task_instructions": task_prompt})
    add_to_db(generated_report, gw_id, is_complete, client)
    # Set CORS headers for the main request
    headers = {"Access-Control-Allow-Origin": "*"}
    return (generated_report.model_dump_json(),200, headers)

entry_point(None)