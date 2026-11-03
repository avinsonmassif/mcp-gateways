"""Offline test: real espn-api parsing on synthetic ESPN JSON, no network."""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

os.environ.update(
    ESPN_S2="x", ESPN_SWID="{x}", ESPN_LEAGUE_ID="12345", ESPN_SEASON="2027", ESPN_TEAM_ID="1"
)

from espn_api.requests import espn_requests as er  # noqa: E402

DAY_MS = 86_400_000
BASE = 1_792_000_000_000  # an arbitrary epoch ms (late Oct 2026)


def stat_split(prefix, avg):
    # ESPN stat ids: 0 PTS,1 BLK,2 STL,3 AST,6 REB,11 TO,13 FGM,14 FGA,15 FTM,16 FTA,17 3PM,19 FG%,20 FT%,40 MIN,42 GP
    keys = {"0": avg[0], "1": avg[1], "2": avg[2], "3": avg[3], "6": avg[4], "11": avg[5],
            "13": 8.0, "14": 16.0, "15": 4.0, "16": 5.0, "17": avg[6], "19": 0.5, "20": 0.8,
            "40": 34.0}
    total = {k: v * 5 for k, v in keys.items()}
    total["42"] = 5
    return {"id": prefix + "2027", "seasonId": 2027, "scoringPeriodId": 0,
            "appliedTotal": 0, "appliedAverage": 0, "stats": total, "averageStats": keys}


def player(pid, name, pro, inj="ACTIVE"):
    return {
        "playerId": pid, "lineupSlotId": 0, "acquisitionType": "DRAFT",
        "playerPoolEntry": {"player": {
            "id": pid, "fullName": name, "defaultPositionId": 1, "eligibleSlots": [0, 5, 11],
            "proTeamId": pro, "injuryStatus": inj,
            "stats": [stat_split("00", [25, 1, 1.2, 6, 10, 3, 2]),
                      stat_split("01", [30, 2, 2, 7, 12, 2, 3])],
        }},
    }


def team(tid, name, players, values):
    return {
        "id": tid, "abbrev": name[:3].upper(), "name": name, "divisionId": 0,
        "record": {"overall": {"wins": 1, "losses": 0, "ties": 0, "pointsFor": 0, "pointsAgainst": 0}},
        "playoffSeed": 1 if tid == 1 else 2, "owners": [], "transactionCounter": {},
        "roster": {"entries": players}, "valuesByStat": values,
    }


def score(tid, w, l, cats):
    return {"teamId": tid, "totalPoints": w, "pointsByScoringPeriod": {"1": 0, "2": 0, "3": 0},
            "cumulativeScore": {"wins": w, "losses": l, "ties": 0, "scoreByStat": cats},
            "rosterForMatchupPeriod": {"entries": []}}


CATS_A = {"19": {"score": 0.48, "result": "WIN"}, "20": {"score": 0.79, "result": "LOSS"},
          "17": {"score": 30, "result": "WIN"}, "6": {"score": 120, "result": "WIN"},
          "3": {"score": 70, "result": "WIN"}, "2": {"score": 20, "result": "LOSS"},
          "1": {"score": 12, "result": "WIN"}, "11": {"score": 40, "result": "LOSS"},
          "0": {"score": 300, "result": "WIN"}}
CATS_B = {k: {"score": v["score"], "result": "LOSS" if v["result"] == "WIN" else "WIN"} for k, v in CATS_A.items()}

LEAGUE = {
    "seasonId": 2027, "scoringPeriodId": 2,
    "status": {"currentMatchupPeriod": 1, "firstScoringPeriod": 1, "finalScoringPeriod": 160,
               "previousSeasons": []},
    "settings": {
        "name": "Example League", "size": 2,
        "scheduleSettings": {"matchupPeriodCount": 16, "matchupPeriods": {"1": [1, 2, 3], "2": [4, 5, 6]},
                             "playoffTeamCount": 6, "playoffSeedingRule": "H2H"},
        "tradeSettings": {"vetoVotesRequired": 4},
        "draftSettings": {"keeperCount": 0},
        "scoringSettings": {"matchupTieRule": "NONE", "playoffMatchupTieRule": "NONE",
                            "scoringType": "H2H_MOST_CATEGORIES"},
        "acquisitionSettings": {"isUsingAcquisitionBudget": False},
    },
    "teams": [
        team(1, "Home Team", [player(1, "Nikola Jokic", 7), player(2, "Stephen Curry", 9, "OUT")],
             {"0": 900, "1": 30, "2": 40, "3": 250, "6": 400, "11": 120, "13": 300, "14": 600, "15": 100, "16": 125, "17": 90}),
        team(5, "Rivals", [player(3, "Rival Guy", 2)],
             {"0": 800, "1": 50, "2": 45, "3": 200, "6": 350, "11": 100, "13": 280, "14": 620, "15": 90, "16": 100, "17": 70}),
    ],
    "schedule": [{"matchupPeriodId": 1, "winner": "UNDECIDED",
                  "home": score(1, 6, 3, CATS_A), "away": score(5, 3, 6, CATS_B)}],
    "members": [],
}


def games(team_id, days):
    return {str(d): [{"awayProTeamId": team_id, "homeProTeamId": 30 if team_id != 30 else 1,
                      "date": BASE + d * DAY_MS}] for d in days}


PRO = {"settings": {"proTeams": [
    {"id": 0}, {"id": 7, "proGamesByScoringPeriod": games(7, [1, 2, 3, 5])},
    {"id": 9, "proGamesByScoringPeriod": games(9, [2, 3])},
    {"id": 2, "proGamesByScoringPeriod": games(2, [1, 3, 4, 6])},
]}}


def fake_league_get(self, params=None, headers=None, extend=""):
    view = (params or {}).get("view")
    if view == "kona_player_info":
        return {"players": [player(10, "Waiver Wire Guy", 2)]}
    return LEAGUE


er.EspnFantasyRequests.get_league = lambda self: LEAGUE
er.EspnFantasyRequests.get_pro_players = lambda self: [{"id": 1, "fullName": "Nikola Jokic"}]
er.EspnFantasyRequests.get_pro_schedule = lambda self: PRO
er.EspnFantasyRequests.get_league_draft = lambda self: {"draftDetail": {"drafted": False}}
er.EspnFantasyRequests.league_get = fake_league_get

import espn_cats as ec  # noqa: E402


def test_all():
    m = ec.cats_matchup()
    mine = m["matchups"][0]
    assert mine["is_my_matchup"] and mine["home"]["wins"] == 6
    assert mine["home"]["categories"]["FG%"] == {"value": 0.48, "result": "WIN"}
    assert mine["away"]["categories"]["TO"]["result"] == "WIN"

    s = ec.cats_player_stats()
    assert [p["name"] for p in s["players"]] == ["Nikola Jokic", "Stephen Curry"]
    assert s["players"][0]["per_game"]["PTS"] == 25 and s["players"][0]["games_played"] == 5
    s7 = ec.cats_player_stats(player_names=["rival"], free_agents=5, split="last_7")
    assert {p["name"] for p in s7["players"]} == {"Rival Guy", "Waiver Wire Guy"}
    assert s7["players"][0]["per_game"]["PTS"] == 30

    lp = ec.cats_league_profile()
    me = next(t for t in lp["teams"] if t["team_id"] == 1)
    assert me["totals"]["FG%"] == 0.5 and me["ranks"]["PTS"] == 1
    assert me["ranks"]["TO"] == 2  # 120 TO is worse than 100

    g = ec.cats_games_this_week()
    assert g["today_scoring_period"] == 2 and len(g["days"]) == 3
    assert g["days"][0]["played"] is True and g["days"][0]["first_tip"].endswith(" UTC")
    mine = g["rosters"][0]
    assert mine["team_name"] == "Home Team"
    jokic = next(p for p in mine["players"] if p["name"] == "Nikola Jokic")
    assert jokic["games"] == 3 and jokic["remaining"] == 2
    # Curry is OUT, so only Jokic counts toward usable starts on days 2 and 3
    assert mine["remaining_usable_starts"] == 2
    assert g["rosters"][1]["team_name"] == "Rivals"
    den = next(t for t in g["nba_teams"] if t["team"] == "DEN")
    assert den["games"] == 3 and den["remaining"] == 2

    assert ec.cats_refresh()["teams"] == 2

    # /healthz is served on the Streamable HTTP app and opens no MCP session
    # (no lifespan, so the session manager is never started).
    from starlette.testclient import TestClient
    r = TestClient(ec.mcp.streamable_http_app()).get("/healthz")
    assert r.status_code == 200 and r.text == "ok"
    access = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "%s - \"%s %s HTTP/%s\" %d",
                               ("127.0.0.1:1", "GET", "/healthz", "1.1", 200), None)
    assert not ec._SkipHealthz().filter(access)
    access.args = ("127.0.0.1:1", "POST", "/mcp", "1.1", 200)
    assert ec._SkipHealthz().filter(access)
    print(json.dumps(g["days"], indent=1))
    print("ALL OK")


if __name__ == "__main__":
    test_all()
