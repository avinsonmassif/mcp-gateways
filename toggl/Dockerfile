# Toggl's MCP server (@togglhq/mcp, Toggl 2.0) served over Streamable HTTP
# by supergateway. Versions are pinned here; Renovate proposes updates as
# pull requests.

# renovate: datasource=docker depName=node versioning=docker
ARG NODE_VERSION=24
FROM node:${NODE_VERSION}-alpine

# renovate: datasource=npm depName=@togglhq/mcp
ARG TOGGL_MCP_VERSION=1.12.6
# renovate: datasource=npm depName=supergateway
ARG SUPERGATEWAY_VERSION=4.2.1
RUN npm install -g @togglhq/mcp@${TOGGL_MCP_VERSION} supergateway@${SUPERGATEWAY_VERSION} \
 && npm cache clean --force

# The API-token startup check probes the custom-fields endpoint, which returns
# 402 (feature_not_available) on plans without custom fields, so the server
# starts unauthenticated. Probe the projects endpoint instead. Fails the build
# if the upstream code changes and the patch no longer applies.
RUN f=$(grep -rlF '/custom-fields`, token' /usr/local/lib/node_modules/@togglhq/mcp/build/) \
 && sed -i 's#/custom-fields`, token#/projects`, token#' $f \
 && grep -qF '/projects`, token' $f

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
