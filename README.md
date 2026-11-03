# mcp-gateways

Container images that run stdio-only MCP servers behind [supergateway](https://github.com/supercorp-ai/supergateway), so they can be reached over Streamable HTTP. One folder per server.

| Folder | Image | MCP server |
| --- | --- | --- |
| [`toggl`](toggl/) | `ghcr.io/avinsonmassif/mcp-gateway-toggl` | [`@togglhq/mcp`](https://www.npmjs.com/package/@togglhq/mcp) (Toggl 2.0) |

## Versions and updates

Each Dockerfile pins its base image and npm packages as `ARG ..._VERSION` lines with a `# renovate:` comment. [Renovate](https://docs.renovatebot.com/) opens a pull request for each new upstream release. Pull requests build but do not publish; merging to `main` builds and pushes:

- `:latest`
- a version tag, e.g. `1.12.6-sg4.2.1` (`@togglhq/mcp` version, then supergateway version), useful for pinning or rolling back

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

The image patches the server's API-token startup check to probe `/projects` instead of `/custom-fields`, which returns 402 on plans without custom fields. The build fails if the patch no longer applies.

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
