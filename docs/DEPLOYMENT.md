# Deployment Guide

## Prerequisites

- Python 3.12+
- Docker / Docker Compose
- MongoDB 7+
- Redis 7+ (recommended for DID + department cache)
- Plivo Voice account with bidirectional streaming enabled
- Google AI API key with access to `gemini-3.1-flash-live-preview`
- Public HTTPS / WSS endpoint reachable by Plivo (TLS required in production)

## Environment

Copy `.env.example` → `.env` and set at minimum:

| Variable | Notes |
|----------|--------|
| `PUBLIC_BASE_URL` | `https://voice.yourdomain.com` |
| `PUBLIC_WS_BASE_URL` | `wss://voice.yourdomain.com` |
| `ADMIN_API_KEY` | Strong random secret |
| `PLIVO_AUTH_ID` / `PLIVO_AUTH_TOKEN` | From Plivo console |
| `PLIVO_VALIDATE_SIGNATURE` | `true` in production |
| `GEMINI_API_KEY` | Default key (overridable per tenant) |
| `MONGODB_URI` | Voice agent DB only (not HMS) |
| `REDIS_URL` / `REDIS_ENABLED` | DID cache |

## Docker Compose

```bash
cp .env.example .env
# edit .env
docker compose up -d --build
docker compose ps
curl -s https://voice.yourdomain.com/ready
```

Services:

- `api` — FastAPI / uvicorn on port 8080
- `mongo` — tenant registry + call logs
- `redis` — optional hot cache (enabled by default in compose)

Graceful shutdown: Compose `stop_grace_period` is 35s; the app drains active sessions within `SHUTDOWN_GRACE_SECONDS`.

## Plivo configuration

1. Create a Plivo Application.
2. Answer URL: `POST https://voice.yourdomain.com/plivo/answer`
3. Hangup URL: `POST https://voice.yourdomain.com/plivo/hangup`
4. Assign DIDs to the application.
5. Register each DID on the matching tenant via `POST /admin/tenants`.

Streaming notes:

- Content type: `audio/x-mulaw;rate=8000` (default)
- Bidirectional stream WebSocket must be publicly reachable WSS
- Signature validation uses Plivo V3 headers

## HMS integration

Per tenant:

- `hms_base_url` — e.g. `https://hms-server.lalluvemula.cloud/api`
- `hms_subdomain` — used to build `Origin: https://{subdomain}.healeka.com`
- `hms_auth_token` — long-lived static JWT for a service/receptionist user

The voice agent never connects to HMS MongoDB.

## Horizontal scaling

- Run multiple API replicas behind a load balancer.
- Sticky sessions are **not** required for HTTP webhooks, but a **single Plivo stream WebSocket** must stick to one replica for the call lifetime (enable LB sticky by connection or route all `/ws/*` carefully).
- Mongo and Redis are shared state; in-memory `SessionManager` is per-process — hangup on another replica will not see the live WS, but call logs are in Mongo. For multi-replica production, prefer sticky WS or move live session routing to Redis (future enhancement).

## Observability

- Structured JSON logs to stdout
- Prometheus: `GET /metrics`
- Track: concurrent calls, interruptions, tool calls, errors, latency histogram

## Security checklist

- [ ] `PLIVO_VALIDATE_SIGNATURE=true`
- [ ] Strong `ADMIN_API_KEY`
- [ ] TLS termination for HTTPS/WSS
- [ ] Tenant JWTs never logged (sanitizer redacts token fields)
- [ ] Restrict admin routes at the network edge if possible
