# Agent Docker / authenticated HTTP (#13)

This packages the same Agent MCP runtime as stdio. PostgreSQL and inference stay
external. No GPU devices, model weights, Docker socket, DB bootstrap, runtime
activation, Hub configuration or production deployment is performed.

## Security contract

- HTTP is a private service-to-service endpoint, not a public OAuth MCP service.
  Every MCP request requires one operator-configured bearer credential. Its scope
  is the fixed human/Agent/project configured in this instance. Never share one
  instance/token among unrelated users or tenants.
- At least 32 ASCII non-whitespace characters are required in AGENT_MCP_TOKEN.
  There is no default credential. Missing/invalid credentials fail startup.
  Rotating it requires restarting the process.
- Host allowlist is explicit; browser Origin headers are rejected. No CORS.
  Host checks and authentication happen before MCP dispatch. No forwarded
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
127.0.0.1:8768 → container 8768 by default. The bundled public Umeko context is used
unless explicitly overridden. For private editable context, set
FLAMORIS_AGENT_HOME=/context and add a read-only mount of the intended directory
with agents/<agent-key>/{personality,flamoris,characters}.md. Missing explicit context
fails rather than silently changing identity. Do not mount unrelated host folders.
Never bake .env or private context into the image.

Connect a trusted client to /mcp with Authorization: Bearer <secret>. A future Hub
config uses local tools health/ask and namespace agent; Hub configuration is a
separate reviewed change. This token identifies the service's one principal, not
the identity of each user behind a Hub.

## Settings

| Variable | Default / constraint |
|---|---|
| AGENT_MCP_TOKEN | required for HTTP, 32–512 ASCII characters, no whitespace |
| AGENT_HTTP_HOST | 127.0.0.1; container overrides to 0.0.0.0 |
| AGENT_HTTP_PORT | 8768, 1–65535 |
| AGENT_HTTP_ALLOWED_HOSTS | localhost:8768,127.0.0.1:8768,[::1]:8768 |
| FLAMORIS_HUMAN_KEY / AGENT_KEY / PROJECT_KEY | fixed configured principal scope |
| FLAMORIS_HOST_KEY / APPLICATION_KEY / MODEL_KEY | existing runtime references |
| PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD | external PostgreSQL |
| INTELLIGENCE_BASE_URL / INTELLIGENCE_MODEL | configured inference endpoint/model |

Allowed hosts are comma-separated exact Host header values, with optional ports;
no wildcard. Add only the actual internal/proxy hostname used to reach this service.
Use TLS termination outside this process; forwarded headers are not trusted.

The image is non-root (10001), read-only with temporary /tmp, and no Linux
capabilities. Locked Python dependencies are used in Docker; ordinary package
dependency ranges remain in pyproject.toml. No dev tools or history in the image.
The console and stdio commands remain available by overriding the image command.

## Verification

CI builds/runs the image, verifies installed entrypoints/personality and liveness,
and rejects unauthenticated MCP requests without real services. Offline tests
exercise authenticated MCP initialization and asks using fakes. These do NOT close
#2: record actual GPT-OSS response, existing identity, DB messages/provenance,
clean shutdown and restart/explicit parent continuation on the deployed revision.
Do not mark this production-ready until the live checklist passes.
