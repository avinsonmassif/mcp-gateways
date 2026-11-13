# Toggl's MCP server (@togglhq/mcp, Toggl 2.0) served over Streamable HTTP
# by supergateway. Versions are pinned here; Renovate proposes updates as
# pull requests.

# renovate: datasource=docker depName=node versioning=docker
ARG NODE_VERSION=24
FROM node:${NODE_VERSION}-alpine

# renovate: datasource=npm depName=@togglhq/mcp
ARG TOGGL_MCP_VERSION=1.13.206
# renovate: datasource=npm depName=supergateway
ARG SUPERGATEWAY_VERSION=4.2.1
RUN npm install -g @togglhq/mcp@${TOGGL_MCP_VERSION} supergateway@${SUPERGATEWAY_VERSION} \
 && npm cache clean --force

# Opt out of the package's usage analytics and error reports by default.
ENV TOGGL_PRODUCT_ANALYTICS=off \
    TOGGL_SENTRY=off

USER node
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1:8000/healthz || exit 1

# Stateful: one toggl-mcp process per client session, because mutating tools
# keep their pending confirm_token in process memory between the two calls.
ENTRYPOINT ["supergateway", "--stdio", "toggl-mcp", \
            "--outputTransport", "streamableHttp", "--stateful", "--sessionTimeout", "900000", \
            "--port", "8000", "--healthEndpoint", "/healthz"]
