# Agent Docker / authenticated HTTP (#13)

This packages one Agent domain service with an internal HTTP API and an external MCP facade. PostgreSQL and inference stay
external. No GPU devices, model weights, Docker socket, DB bootstrap, runtime
activation, Hub configuration or production deployment is performed.

## Security contract

- HTTP is a private service-to-service endpoint, not a public OAuth MCP service.
  Every internal API or MCP request requires one operator-configured bearer credential. Its scope
  is the fixed human/Agent/project configured in default mode. Never share that
  default instance/token among unrelated users or tenants. Explicit shared mode
  authenticates a trusted delegator and requires operator-controlled exact grants;
  see [PRINCIPAL_SESSIONS.md](PRINCIPAL_SESSIONS.md) before enabling it.
- At least 32 ASCII non-whitespace characters are required in AGENT_MCP_TOKEN.
  There is no default credential. Missing/invalid credentials fail startup.
  Rotating it requires restarting the process.
- Host allowlist is explicit; browser Origin headers are rejected. No CORS.
  Host checks and authentication happen before internal API or MCP dispatch. No forwarded
  identity headers are trusted. /healthz only returns process liveness.
- Publish only host loopback by default. A trusted TLS reverse proxy or private
  network gateway is required for any non-loopback connection. Docker publication
  is not authentication. Keep upstream plaintext traffic inside the trusted network.
- No token, provider/DB error body, prompt, transcript or private topology is
  included in service errors/access logs. Operator/provider logging policies
  remain independent.
- Use a single worker/container. Admission rejects concurrent asks, not queues.
  HTTP body ceiling is 128 KiB, request-header handling is Uvicorn's; reverse proxy
  must impose connection/header/rate limits too. No automatic ask retries.
- SIGTERM drains/cancels work with a 30-second graceful shutdown window. A forced
  kill/DB outage may leave incomplete lifecycle timestamps or committed partial
  turns. Consult request_id and existing DB evidence before retrying.

## Build and start

Copy .env.example to an untracked .env and replace all deployment values.
Supply AGENT_MCP_TOKEN separately via your runtime environment or protected .env.
Use a random secret (for example python -c 'import secrets; print(secrets.token_urlsafe(32))').
Do not paste credentials into Issues.

Set PGHOST and INTELLIGENCE_BASE_URL to addresses reachable *from the container*.
127.0.0.1 in a container is not the host. Verify actual deployed endpoint/model
via the runtime manager/runbook; do not invent host topology from this example.
Runtime host/model/application identities must already exist in PostgreSQL.
Register container provenance deliberately: do not repoint a historical host key.
There is no automatic schema, seed, or runtime registration on startup.

    docker compose build
    docker compose up -d

Compose reads .env at runtime, enforces a required token and publishes
127.0.0.1:8768 → container 8768 by default. The bundled public example Agent context is used
unless explicitly overridden. For private editable context, set
FLAMORIS_AGENT_HOME=/context and add a read-only mount of the intended directory
with agents/<agent-key>/agent.toml and its listed Markdown files. Missing explicit context
fails rather than silently changing identity. Do not mount unrelated host folders.
Never bake .env or private context into the image.

Studio connects to `/api/v1` using the authenticated internal contract in
[INTERNAL_EXECUTION.md](INTERNAL_EXECUTION.md). It sends ordinary domain request
JSON, without MCP or JSON-RPC. Shared mode additionally requires the configured
delegator, exact DB membership/grants and Studio's independent account boundary.

External MCP clients connect to `/mcp` with the same operator bearer credential;
fixed/shared modes advertise different catalogs. Review the exact external catalog
before Hub registration. Neither route turns the service token into a human identity
or creates a second conversation/request authority.

## Settings

| Variable | Default / constraint |
|---|---|
| AGENT_MCP_TOKEN | required for HTTP, 32–512 ASCII characters, no whitespace |
| AGENT_HTTP_HOST | 127.0.0.1; container overrides to 0.0.0.0 |
| AGENT_HTTP_PORT | 8768, 1–65535 |
| AGENT_HTTP_ALLOWED_HOSTS | localhost:8768,127.0.0.1:8768,[::1]:8768 |
| AGENT_HTTP_DELEGATOR_KEY | unset: fixed catalog; explicit safe caller key selects shared catalog after grants/migration; see PRINCIPAL_SESSIONS.md |
| FLAMORIS_HUMAN_KEY / AGENT_KEY / PROJECT_KEY | fixed configured principal scope |
| FLAMORIS_HOST_KEY / APPLICATION_KEY / MODEL_KEY | existing runtime references |
| PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD | external PostgreSQL |
| INTELLIGENCE_BASE_URL / INTELLIGENCE_MODEL | configured direct llama.cpp base URL/model |
| AGENT_INTELLIGENCE_TARGET / AGENT_INTELLIGENCE_TARGETS | approved local target / opt-in settings target registry; see INTERNAL_EXECUTION.md |

Allowed hosts are comma-separated exact Host header values, with optional ports;
no wildcard. Add only the actual internal/proxy hostname used to reach this service.
Use TLS termination outside this process; forwarded headers are not trusted.

The image is non-root (10001), read-only with temporary /tmp, and no Linux
capabilities. Locked Python dependencies are used in Docker; ordinary package
dependency ranges remain in pyproject.toml. No dev tools or history in the image.
The console and stdio commands remain available by overriding the image command.

## Verification

CI builds/runs the image, verifies installed entrypoints/manifest context resources and liveness,
and rejects unauthenticated internal API and MCP requests without real services. Offline tests
exercise both authenticated transports using the same domain service and fake providers. Phase 0's live
console acceptance was completed in #2; a new HTTP deployment still requires
its own operational validation.
