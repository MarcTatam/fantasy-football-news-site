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