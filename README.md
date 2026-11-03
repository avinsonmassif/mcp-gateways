# mcp-gateways

Container images that serve MCP servers over Streamable HTTP, with pinned versions. Stdio-only servers run behind [supergateway](https://github.com/supercorp-ai/supergateway); servers with their own HTTP transport run it directly. One folder per server.

| Folder | Image | MCP server |
| --- | --- | --- |
| [`toggl`](toggl/) | `ghcr.io/avinsonmassif/mcp-gateway-toggl` | [`@togglhq/mcp`](https://www.npmjs.com/package/@togglhq/mcp) (Toggl 2.0) |
| [`pushover`](pushover/) | `ghcr.io/avinsonmassif/mcp-gateway-pushover` | [`pushover-mcp`](https://www.npmjs.com/package/pushover-mcp) |

## Versions and updates

Each Dockerfile pins its base image and npm packages as `ARG ..._VERSION` lines with a `# renovate:` comment. [Renovate](https://docs.renovatebot.com/) opens a pull request for each new upstream release. Pull requests build but do not publish; merging to `main` builds and pushes:

- `:latest`
- a version tag, useful for pinning or rolling back: for `toggl` e.g. `1.12.6-sg4.2.1` (`@togglhq/mcp` version, then supergateway version), for `pushover` the `pushover-mcp` version, e.g. `2.0.0`

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
