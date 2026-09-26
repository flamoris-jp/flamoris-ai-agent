FROM python:3.12-slim-bookworm AS build
WORKDIR /build
COPY pyproject.toml README.md LICENSE docker-requirements.txt ./
COPY src/ ./src/
COPY agents/ ./agents/
RUN python -m pip install --no-cache-dir hatchling==1.32.4 \
    && python -m pip wheel --no-cache-dir --wheel-dir /wheels -r docker-requirements.txt \
    && python -m pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir /wheels .

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENT_HTTP_HOST=0.0.0.0 \
    AGENT_HTTP_PORT=8768
COPY --from=build /wheels /wheels
COPY docker-requirements.txt /tmp/docker-requirements.txt
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels \
      -r /tmp/docker-requirements.txt /wheels/flamoris_ai_agent-*.whl \
    && rm -r /wheels /tmp/docker-requirements.txt \
    && mkdir /app && chown 10001:10001 /app
USER 10001:10001
WORKDIR /app
EXPOSE 8768
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-m", "flamoris_ai_agent.healthcheck"]
CMD ["flamoris-agent-mcp", "--transport", "streamable-http"]
