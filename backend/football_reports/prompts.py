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

full_prompt_template = """Generate a report in the style of a news outlet covering the weekends football events for my fantasy football league. Make the headline as eyecatching as possible.

Ensure the body goes into the details on the best and worst performers for each team, and whether leaving the players on the bench was a good decision (Bench players only play if a player in the starting 11 scores 0 points), make sure every team is mentioned.
You should be critical of teams that performed poorly (especially any team managed by Giles).

If the season is beyond the first week of the game, comment on any narrowing or widening gaps or any position swaps.

The league name is {league_name} and we are in week {gameweek} of 38.

Here are some inside jokes you can refer to in the reports, but only if it makes sense:
- Arsenal bottling the league two seasons in a row (Use when one team loses a lead to another).
- Calling things a "mauling" when one team dominates another (only use in comparisons).

Here are the teams:

{teams}

Note that the captains points are doubled.

Try and make the report at least 350 words long and use multiple paragraphs where possible.
"""

player_template = "Player Name: {player_name}, Player Points:{player_points}"

report_template = """<report>
Gameweek: {gw_id} of 38
Headline: {headline}
Body: {body}
</report>"""

summary_prompt_template = """Generate a summarising report in the style of a news outlet reflecting on the fantasy football season for my fantasy football league. Make the headline as eyecatching as possible.

You are provided the weekly reports of a season of fantasy football, your aim is to condense these reports into one report to provide an overview report of the season.

Here are some inside jokes you can refer to in the summary, but only if it makes sense:
- Arsenal bottling the league two seasons in a row (Use when one team loses a lead to another).
- Calling things a "mauling" when one team dominates another (only use in comparisons).

Try and make the report at least 350 words long and use multiple paragraphs where possible.

Here are the reports:
{reports}"""