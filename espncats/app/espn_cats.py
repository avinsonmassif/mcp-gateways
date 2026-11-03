"""
espn-cats: a small, read-only MCP server for ESPN fantasy basketball category
(9-cat, H2H Most Categories) analysis. Built on cwendt94/espn-api.

Meant to sit next to tlo1216/espn-fantasy-mcp and to cover only what that
server lacks: per-category matchup scores, per-category player stats, league
category profiles, and games per week. It never writes to ESPN.

Environment (same names as espn-fantasy-mcp, so one shared env file works):
  ESPN_S2, ESPN_SWID   ESPN session cookies (SWID includes the curly braces)
  ESPN_LEAGUE_ID       your league id, from the league URL (leagueId=...)
  ESPN_SEASON          season end year, e.g. 2027 for 2026-27
  ESPN_TEAM_ID         your team id, used as the default "my team"
  ESPN_CACHE_SECONDS   optional, league cache lifetime (default 300)
  TZ                   optional, IANA timezone for first_tip times (default UTC)

Transport (defaults suit local stdio use):
  MCP_TRANSPORT        stdio (default) or streamable-http
  MCP_HOST, MCP_PORT   HTTP listen address (default 127.0.0.1:8000, path /mcp)
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from espn_api.basketball import League
from espn_api.requests.espn_requests import ESPNAccessDenied
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

CATS = ["FG%", "FT%", "3PM", "REB", "AST", "STL", "BLK", "TO", "PTS"]
LOWER_IS_BETTER = {"TO"}
SPLITS = {
    "season": "total",
    "last_7": "last_7",
    "last_15": "last_15",
    "last_30": "last_30",
    "projected": "projected",
}
ET = ZoneInfo("America/New_York")


def _local_tz() -> ZoneInfo:
    """The display timezone from TZ (an IANA name such as Europe/London),
    falling back to UTC when TZ is unset or not a known zone."""
    try:
        return ZoneInfo(os.environ.get("TZ", "").strip() or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


LOCAL_TZ = _local_tz()
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True)

mcp = FastMCP(
    "espn-cats",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
)

_lock = threading.Lock()
_cache: dict = {"league": None, "at": 0.0}


def _env(name: str, required: bool = True) -> str | None:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise RuntimeError(f"{name} is not set in the container environment.")
    return value or None


def _league(refresh: bool = False) -> League:
    """Build (or reuse) the League object. Construction costs about four ESPN
    requests, so it is cached for ESPN_CACHE_SECONDS."""
    ttl = int(os.environ.get("ESPN_CACHE_SECONDS", "300"))
    with _lock:
        fresh = _cache["league"] is not None and time.time() - _cache["at"] < ttl
        if fresh and not refresh:
            return _cache["league"]
        try:
            league = League(
                league_id=int(_env("ESPN_LEAGUE_ID")),
                year=int(_env("ESPN_SEASON")),
                espn_s2=_env("ESPN_S2"),
                swid=_env("ESPN_SWID"),
            )
        except ESPNAccessDenied as exc:
            raise RuntimeError(
                "ESPN refused the request (401). The ESPN_S2/ESPN_SWID cookies have "
                "probably expired: refresh them in the shared env file and restart "
                "both ESPN containers."
            ) from exc
        _cache.update(league=league, at=time.time())
        return league


def _my_team_id() -> int | None:
    raw = _env("ESPN_TEAM_ID", required=False)
    return int(raw) if raw else None


def _team_label(team) -> dict:
    if team is None or isinstance(team, int):
        return {"team_id": team or 0, "team_name": "BYE" if not team else str(team)}
    return {"team_id": team.team_id, "team_name": team.team_name}


def _round(cat: str, value):
    if value is None:
        return None
    return round(value, 3 if cat in ("FG%", "FT%") else 1)


def _period_days(league: League, matchup_period: int) -> list[int]:
    periods = league.settings.matchup_periods or {}
    days = periods.get(str(matchup_period)) or periods.get(matchup_period) or []
    return sorted(int(d) for d in days)


def _team_games(league: League, pro_team_id: int, days: list[int]) -> list[int]:
    games = league.pro_schedule.get(pro_team_id, {}) or {}
    return [d for d in days if games.get(str(d))]


def _day_dates(league: League, days: list[int]) -> dict[int, dict]:
    """Earliest tip-off per scoring period, in US Eastern and local (TZ) time."""
    out: dict[int, dict] = {}
    for games in league.pro_schedule.values():
        for day, entries in (games or {}).items():
            day = int(day)
            if day not in days or not entries:
                continue
            ts = entries[0].get("date")
            if ts is None:
                continue
            if day not in out or ts < out[day]["_ts"]:
                out[day] = {"_ts": ts}
    for day, info in out.items():
        tip = datetime.fromtimestamp(info.pop("_ts") / 1000, tz=timezone.utc)
        info["us_date"] = tip.astimezone(ET).strftime("%a %d %b")
        info["first_tip"] = tip.astimezone(LOCAL_TZ).strftime("%a %d %b %H:%M %Z")
    return out


@mcp.tool(annotations=READ_ONLY)
def cats_matchup(matchup_period: int | None = None) -> dict:
    """Category-by-category scores for every H2H matchup in a matchup period
    (one fantasy week). Defaults to the current week. For each side: the
    category wins/losses/ties so far and each of the 9 categories (FG%, FT%,
    3PM, REB, AST, STL, BLK, TO, PTS) with its value and WIN/LOSS/TIE result.
    TO is lower-is-better. ESPN may only fold a day's stats in after that day's
    games finish. Use this, not espn-fantasy-mcp's get_matchups, for any
    question about who is winning which categories."""
    league = _league()
    period = matchup_period or league.currentMatchupPeriod
    my_id = _my_team_id()
    matchups = []
    for box in league.box_scores(matchup_period=period):
        sides = {}
        for side in ("home", "away"):
            team = getattr(box, f"{side}_team")
            stats = getattr(box, f"{side}_stats", {}) or {}
            sides[side] = {
                **_team_label(team),
                "wins": getattr(box, f"{side}_wins", 0),
                "losses": getattr(box, f"{side}_losses", 0),
                "ties": getattr(box, f"{side}_ties", 0),
                "categories": {
                    cat: {
                        "value": _round(cat, stats.get(cat, {}).get("value")),
                        "result": stats.get(cat, {}).get("result"),
                    }
                    for cat in CATS
                },
            }
        ids = {sides["home"]["team_id"], sides["away"]["team_id"]}
        matchups.append({"is_my_matchup": my_id in ids, **sides})
    return {
        "matchup_period": period,
        "current_matchup_period": league.currentMatchupPeriod,
        "my_team_id": my_id,
        "matchups": matchups,
    }


@mcp.tool(annotations=READ_ONLY)
def cats_player_stats(
    team_id: int | None = None,
    player_names: list[str] | None = None,
    free_agents: int = 0,
    split: str = "season",
) -> dict:
    """Per-game 9-category averages for players, plus games played and minutes.
    Choose who to include with any mix of:
      team_id: a fantasy team's whole roster (0 or omitted with nothing else
               set means your own team, ESPN_TEAM_ID)
      player_names: exact or partial names, searched across all rosters
      free_agents: the top N free agents and waiver players by % owned (max 100)
    split is one of: season, last_7, last_15, last_30, projected.
    Use this for category fit when weighing adds, drops, starts and trades."""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {', '.join(SPLITS)}")
    league = _league()
    key = f"{league.year}_{SPLITS[split]}"
    if team_id is None and not player_names and not free_agents:
        team_id = _my_team_id()

    picked: list[tuple[str, object]] = []
    owner = {p.playerId: t.team_name for t in league.teams for p in t.roster}
    if team_id:
        team = next((t for t in league.teams if t.team_id == team_id), None)
        if team is None:
            raise ValueError(f"No team with id {team_id} in this league.")
        picked += [(team.team_name, p) for p in team.roster]
    if player_names:
        wanted = [n.lower() for n in player_names]
        for t in league.teams:
            for p in t.roster:
                if any(w in p.name.lower() for w in wanted):
                    picked.append((t.team_name, p))
    if free_agents:
        for p in league.free_agents(size=max(1, min(int(free_agents), 100))):
            picked.append(("FREE AGENT", p))

    seen, players = set(), []
    for fantasy_team, p in picked:
        if p.playerId in seen:
            continue
        seen.add(p.playerId)
        block = p.stats.get(key) or {}
        avg = block.get("avg") or {}
        total = block.get("total") or {}
        players.append(
            {
                "name": p.name,
                "player_id": p.playerId,
                "fantasy_team": owner.get(p.playerId, fantasy_team),
                "nba_team": p.proTeam,
                "position": p.position,
                "injury_status": p.injuryStatus,
                "games_played": total.get("GP"),
                "minutes": _round("MIN", avg.get("MIN")),
                "per_game": {cat: _round(cat, avg.get(cat)) for cat in CATS},
                "fga_per_game": _round("FGA", avg.get("FGA")),
                "fta_per_game": _round("FTA", avg.get("FTA")),
            }
        )
    note = (
        "FG% and FT% matter in proportion to attempts: a high-volume shooter "
        "moves the team percentage far more than a low-volume one."
    )
    return {"split": split, "season": league.year, "players": players, "note": note}


@mcp.tool(annotations=READ_ONLY)
def cats_league_profile() -> dict:
    """Season-to-date 9-category totals for every team, with each team's rank
    in each category (1 = best; TO ranks lowest as best), plus record and
    playoff seed. Use it to find each team's strengths and weaknesses, and
    trade partners who are strong where we are weak and weak where we are
    strong."""
    league = _league()
    rows = []
    for t in league.teams:
        s = t.stats or {}
        cats = {}
        for cat in CATS:
            if cat == "FG%" and s.get("FGA"):
                value = s["FGM"] / s["FGA"]
            elif cat == "FT%" and s.get("FTA"):
                value = s["FTM"] / s["FTA"]
            else:
                value = s.get(cat)
            cats[cat] = _round(cat, value)
        rows.append(
            {
                **_team_label(t),
                "record": f"{t.wins}-{t.losses}-{t.ties}",
                "seed": t.standing,
                "totals": cats,
                "ranks": {},
            }
        )
    for cat in CATS:
        valued = [r for r in rows if r["totals"][cat] is not None]
        valued.sort(key=lambda r: r["totals"][cat], reverse=cat not in LOWER_IS_BETTER)
        for rank, r in enumerate(valued, start=1):
            r["ranks"][cat] = rank
    rows.sort(key=lambda r: (r["seed"] or 99))
    return {"season": league.year, "my_team_id": _my_team_id(), "teams": rows}


@mcp.tool(annotations=READ_ONLY)
def cats_games_this_week(
    matchup_period: int | None = None, team_id: int | None = None
) -> dict:
    """Games per NBA team in a matchup period (fantasy week), total and still
    to play, plus the same per player for a fantasy roster (default: your
    team) and its opponent. Daily lineups cap starters at 10 a day, so roster
    games above that on a busy day are wasted: check the per-day counts.
    Use it for streaming and for start/sit volume decisions."""
    league = _league()
    period = matchup_period or league.currentMatchupPeriod
    days = _period_days(league, period)
    if not days:
        raise ValueError(f"No scoring days found for matchup period {period}.")
    today = league.scoringPeriodId
    remaining_days = [d for d in days if d >= today]
    dates = _day_dates(league, days)

    from espn_api.basketball.constant import PRO_TEAM_MAP

    nba = []
    for pro_id, abbrev in PRO_TEAM_MAP.items():
        if pro_id == 0:
            continue
        played = _team_games(league, pro_id, days)
        nba.append(
            {
                "team": abbrev,
                "games": len(played),
                "remaining": len([d for d in played if d >= today]),
            }
        )
    nba.sort(key=lambda r: (-r["remaining"], -r["games"], r["team"]))

    abbrev_to_id = {v: k for k, v in PRO_TEAM_MAP.items()}

    def roster_view(team) -> dict:
        players, per_day = [], {d: 0 for d in remaining_days}
        for p in team.roster:
            g = _team_games(league, abbrev_to_id.get(p.proTeam, 0), days)
            left = [d for d in g if d >= today]
            for d in left:
                if p.injuryStatus not in ("OUT", "INJURY_RESERVE"):
                    per_day[d] += 1
            players.append(
                {
                    "name": p.name,
                    "nba_team": p.proTeam,
                    "injury_status": p.injuryStatus,
                    "games": len(g),
                    "remaining": len(left),
                }
            )
        usable = sum(min(n, 10) for n in per_day.values())
        return {
            **_team_label(team),
            "remaining_player_games": sum(p["remaining"] for p in players),
            "remaining_usable_starts": usable,
            "healthy_players_with_games_by_day": {
                str(d): n for d, n in per_day.items()
            },
            "players": sorted(players, key=lambda r: -r["remaining"]),
        }

    me_id = team_id or _my_team_id()
    rosters = []
    me = next((t for t in league.teams if t.team_id == me_id), None)
    if me is not None:
        rosters.append(roster_view(me))
        opp = None
        for box in league.scoreboard(period):
            home, away = box.home_team, box.away_team
            if getattr(home, "team_id", home) == me_id:
                opp = away
            elif getattr(away, "team_id", away) == me_id:
                opp = home
        if opp is not None and not isinstance(opp, int):
            rosters.append(roster_view(opp))

    return {
        "matchup_period": period,
        "today_scoring_period": today,
        "days": [
            {"scoring_period": d, **dates.get(d, {}), "played": d < today}
            for d in days
        ],
        "nba_teams": nba,
        "rosters": rosters,
        "note": "remaining_usable_starts caps each day at 10 starters and skips "
        "players tagged OUT or IR.",
    }


@mcp.tool(annotations=READ_ONLY)
def cats_refresh() -> dict:
    """Drop the cached league data and fetch it again from ESPN. Only needed
    straight after a roster move or trade, since data is otherwise cached for
    a few minutes."""
    league = _league(refresh=True)
    return {
        "refreshed": True,
        "current_matchup_period": league.currentMatchupPeriod,
        "scoring_period": league.scoringPeriodId,
        "teams": len(league.teams),
    }


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
