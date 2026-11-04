# mcp-gateways

Container images that serve MCP servers over Streamable HTTP, with pinned versions. Stdio-only servers run behind [supergateway](https://github.com/supercorp-ai/supergateway); servers with their own HTTP transport run it directly. One folder per server; `espncats` also holds the server's own code.

| Folder | Image | MCP server |
| --- | --- | --- |
| [`toggl`](toggl/) | `ghcr.io/avinsonmassif/mcp-gateway-toggl` | [`@togglhq/mcp`](https://www.npmjs.com/package/@togglhq/mcp) (Toggl 2.0) |
| [`pushover`](pushover/) | `ghcr.io/avinsonmassif/mcp-gateway-pushover` | [`pushover-mcp`](https://www.npmjs.com/package/pushover-mcp) |
| [`espncats`](espncats/) | `ghcr.io/avinsonmassif/mcp-gateway-espncats` | `espn-cats` (in this repo), read-only ESPN fantasy basketball category analysis on [`espn-api`](https://github.com/cwendt94/espn-api) |
| [`espn`](espn/) | `ghcr.io/avinsonmassif/mcp-gateway-espn` | [`espn-fantasy-mcp`](https://github.com/tlo1216/espn-fantasy-mcp), built from the [avinsonmassif fork](https://github.com/avinsonmassif/espn-fantasy-mcp) at a pinned commit |

## Versions and updates

Each Dockerfile pins its base image and npm packages as `ARG ..._VERSION` lines with a `# renovate:` comment; Python packages are pinned in `requirements.txt`. `espn` is not on npm, so its git commit is pinned as `ARG ESPN_MCP_REF` and bumped by hand. [Renovate](https://docs.renovatebot.com/) opens a pull request for each new upstream release. Pull requests build but do not publish; merging to `main` builds and pushes:

- `:latest`
- a version tag, useful for pinning or rolling back: for `toggl` e.g. `1.12.6-sg4.2.1` (`@togglhq/mcp` version, then supergateway version), for `pushover` the `pushover-mcp` version, e.g. `2.0.0`, for `espncats` the `espn-api` and `mcp` versions and the commit, e.g. `1.0.1-mcp1.30.0-abc1234`, for `espn` the server commit, then supergateway version, e.g. `75ec998-sg4.2.1`

## toggl

Serves `toggl-mcp` in API-token mode on port 8000:

- MCP endpoint: `http://<host>:8000/mcp`
- Health: `http://<host>:8000/healthz`

Required environment variables:

| Variable | Notes |
| --- | --- |
| `TOGGL_API_TOKEN` | Personal API token from Toggl |
| `TOGGL_ORGANIZATION_ID` | From the app URL: `focus.toggl.com/<organization_id>/workspaces/<workspace_id>/...` |
| `TOGGL_WORKSPACE_ID` | As above |

`TOGGL_PRODUCT_ANALYTICS` and `TOGGL_SENTRY` default to `off` in the image.

The gateway runs in stateful mode (one `toggl-mcp` process per client session), because Toggl's mutating tools keep a pending `confirm_token` in memory between the confirm request and the confirmed call.

The endpoint has no authentication of its own. Put it behind an authenticating proxy or keep it on a private network.

Example:

```yaml
services:
  mcp-gateway-toggl:
    image: ghcr.io/avinsonmassif/mcp-gateway-toggl:latest
    restart: unless-stopped
    environment:
      - TOGGL_API_TOKEN=${TOGGL_API_TOKEN}
      - TOGGL_ORGANIZATION_ID=${TOGGL_ORGANIZATION_ID}
      - TOGGL_WORKSPACE_ID=${TOGGL_WORKSPACE_ID}
```

## pushover

Runs `pushover-mcp` on its own Streamable HTTP transport on port 8000:

- MCP endpoint: `http://<host>:8000/mcp`

Required environment variables:

| Variable | Notes |
| --- | --- |
| `PUSHOVER_TOKEN` | Application API token from Pushover |
| `PUSHOVER_USER` | User or group key |
| `PUSHOVER_MCP_AUTH_TOKEN` | Bearer token clients must send as `Authorization: Bearer <token>`. The server will not listen beyond loopback without one |

Optional: `PUSHOVER_DEFAULT_DEVICE`, `PUSHOVER_DEFAULT_SOUND`, `PUSHOVER_DEFAULT_PRIORITY` (see the [package docs](https://github.com/AshikNesin/pushover-mcp#readme)).

Requests without the bearer token get 401. The server also rejects browser requests with a non-localhost `Origin` header. There is no separate health endpoint; the image's healthcheck expects 401 from an unauthenticated local request to `/mcp`.

Example:

```yaml
services:
  mcp-gateway-pushover:
    image: ghcr.io/avinsonmassif/mcp-gateway-pushover:latest
    restart: unless-stopped
    environment:
      - PUSHOVER_TOKEN=${PUSHOVER_TOKEN}
      - PUSHOVER_USER=${PUSHOVER_USER}
      - PUSHOVER_MCP_AUTH_TOKEN=${PUSHOVER_MCP_AUTH_TOKEN}
```

## espncats

A small, read-only MCP server for ESPN fantasy basketball leagues scored by category (9-cat, H2H Most Categories). It covers what general ESPN fantasy servers lack: per-category matchup scores, per-category player averages, league category ranks and games per week. It never writes to ESPN. Built with FastMCP from the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), on its own Streamable HTTP transport on port 8000:

- MCP endpoint: `http://<host>:8000/mcp`
- Health: `http://<host>:8000/healthz` (answers `ok` without opening an MCP session, and is left out of the access log)

Tools: `cats_matchup`, `cats_player_stats`, `cats_league_profile`, `cats_games_this_week`, `cats_refresh`.

Required environment variables:

| Variable | Notes |
| --- | --- |
| `ESPN_S2`, `ESPN_SWID` | ESPN session cookies from a signed-in browser (`SWID` includes the curly braces) |
| `ESPN_LEAGUE_ID` | From the league URL (`leagueId=...`) |
| `ESPN_SEASON` | Season end year, e.g. `2027` for 2026-27 |
| `ESPN_TEAM_ID` | Your team, used as the default "my team" |

Optional: `ESPN_CACHE_SECONDS` (league cache lifetime, default `300`) and `TZ` (IANA timezone such as `Europe/London` for the `first_tip` times in `cats_games_this_week`, default `UTC`; an unknown zone also falls back to UTC).

The image sets `MCP_TRANSPORT=streamable-http`, `MCP_HOST=0.0.0.0` and `MCP_PORT=8000`. Run outside the image, `app/espn_cats.py` defaults to stdio. CI runs the offline test (`test/test_espn_cats.py`, synthetic ESPN data, no network) before building.

The endpoint has no authentication of its own. Put it behind an authenticating proxy or keep it on a private network.

Example:

```yaml
services:
  mcp-gateway-espncats:
    image: ghcr.io/avinsonmassif/mcp-gateway-espncats:latest
    restart: unless-stopped
    environment:
      - ESPN_S2=${ESPN_S2}
      - ESPN_SWID=${ESPN_SWID}
      - ESPN_LEAGUE_ID=${ESPN_LEAGUE_ID}
      - ESPN_SEASON=2027
      - ESPN_TEAM_ID=${ESPN_TEAM_ID}
      - TZ=Europe/London
```

## espn

Serves [`espn-fantasy-mcp`](https://github.com/tlo1216/espn-fantasy-mcp) (ESPN fantasy football, basketball and baseball: leagues, rosters, free agents, matchups, transactions, and optional roster writes) behind supergateway on port 8000:

- MCP endpoint: `http://<host>:8000/mcp`
- Health: `http://<host>:8000/healthz`

It is built from the [avinsonmassif fork](https://github.com/avinsonmassif/espn-fantasy-mcp), which adds a fix for leagues with no trade deadline on top of upstream.

Required environment variables:

| Variable | Notes |
| --- | --- |
| `ESPN_S2`, `ESPN_SWID` | ESPN session cookies from a signed-in browser (`SWID` includes the curly braces) |
| `ESPN_SPORT` | `ffl`, `fba` or `flb` |
| `ESPN_SEASON` | Season year |
| `ESPN_LEAGUE_ID` | Default league |

Optional: `ESPN_TEAM_ID` (default team) and `WRITES_ENABLED` (`true` allows lineup, waiver and IR writes; default `false`). Write tools default to a dry run either way. Writes that are sent are logged to `logs/writes.jsonl` under the working directory, `/data`, so mount a volume there to keep the log.

The gateway runs in stateful mode (one server process per client session), as for `toggl`.

The endpoint has no authentication of its own. Put it behind an authenticating proxy or keep it on a private network.

Example:

```yaml
services:
  mcp-gateway-espn:
    image: ghcr.io/avinsonmassif/mcp-gateway-espn:latest
    restart: unless-stopped
    environment:
      - ESPN_S2=${ESPN_S2}
      - ESPN_SWID=${ESPN_SWID}
      - ESPN_SPORT=fba
      - ESPN_SEASON=2027
      - ESPN_LEAGUE_ID=${ESPN_LEAGUE_ID}
      - ESPN_TEAM_ID=${ESPN_TEAM_ID}
    volumes:
      - ./data:/data
```
