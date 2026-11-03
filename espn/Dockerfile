# ESPN fantasy MCP server (tlo1216/espn-fantasy-mcp, built from the
# avinsonmassif fork) served over Streamable HTTP by supergateway. Node and
# supergateway are pinned here and updated by Renovate. The server is not on
# npm, so its git commit is pinned below and bumped by hand after syncing the
# fork; never track a branch.

# renovate: datasource=docker depName=node versioning=docker
ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-alpine AS build
ARG ESPN_MCP_REPO=https://github.com/avinsonmassif/espn-fantasy-mcp.git
# Upstream e774fc6 plus the fix for leagues with no trade deadline.
ARG ESPN_MCP_REF=75ec998736973e82039b9859fa3883f57f7ce785
RUN apk add --no-cache git
WORKDIR /app
RUN git clone ${ESPN_MCP_REPO} . \
 && git checkout ${ESPN_MCP_REF} \
 && npm ci && npm run build && npm prune --omit=dev

FROM node:${NODE_VERSION}-alpine
# renovate: datasource=npm depName=supergateway
ARG SUPERGATEWAY_VERSION=4.2.1
RUN npm install -g supergateway@${SUPERGATEWAY_VERSION} \
 && npm cache clean --force
COPY --from=build /app/dist /app/dist
COPY --from=build /app/node_modules /app/node_modules
COPY --from=build /app/package.json /app/package.json

# The write log (logs/writes.jsonl) is relative to the working directory, so
# mount a volume at /data to keep it.
RUN mkdir /data && chown node:node /data
WORKDIR /data
USER node
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["supergateway", "--stdio", "node /app/dist/index.js", \
            "--outputTransport", "streamableHttp", "--stateful", "--sessionTimeout", "900000", \
            "--port", "8000", "--healthEndpoint", "/healthz"]
