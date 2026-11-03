# espn-cats: read-only ESPN fantasy basketball category MCP server (FastMCP
# from the MCP Python SDK, espn-api) on its native Streamable HTTP transport.
# Versions are pinned here and in requirements.txt; Renovate proposes updates
# as pull requests.

# renovate: datasource=docker depName=python versioning=docker
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8000
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
 && useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin app
COPY app/espn_cats.py /app/espn_cats.py

USER app
EXPOSE 8000
# No health endpoint: any HTTP answer from /mcp (a plain GET is refused) means
# the server is up.
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u, urllib.error as e; exec('try: u.urlopen(\"http://127.0.0.1:8000/mcp\", timeout=4)\nexcept e.HTTPError: pass')"

ENTRYPOINT ["python", "/app/espn_cats.py"]
