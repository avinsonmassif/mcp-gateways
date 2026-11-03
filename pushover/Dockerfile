# Pushover's MCP server (pushover-mcp) on its native Streamable HTTP
# transport. Versions are pinned here; Renovate proposes updates as pull
# requests.

# renovate: datasource=docker depName=node versioning=docker
ARG NODE_VERSION=24
FROM node:${NODE_VERSION}-alpine

# renovate: datasource=npm depName=pushover-mcp
ARG PUSHOVER_MCP_VERSION=2.0.0
RUN npm install -g pushover-mcp@${PUSHOVER_MCP_VERSION} \
 && npm cache clean --force

USER node
EXPOSE 8000
# No health endpoint: /mcp answers an unauthenticated local request with 401.
HEALTHCHECK --interval=30s --timeout=5s CMD node -e "fetch('http://127.0.0.1:8000/mcp').then(r=>process.exit(r.status===401?0:1),()=>process.exit(1))"

# Listening beyond loopback requires PUSHOVER_MCP_AUTH_TOKEN; the server
# refuses to start without it.
ENTRYPOINT ["pushover-mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
