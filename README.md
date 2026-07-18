# Healeka AI Voice Agent

Production-grade real-time AI voice agent backend (Python / FastAPI) for hospital receptionist phone calls.

**Stack:** FastAPI · AsyncIO · Plivo bidirectional streaming · Gemini 3.1 Flash Live · httpx · MongoDB · Redis · Docker

The voice agent never accesses the HMS database. All business operations go through the existing Express.js HMS REST APIs.

## Architecture

```
Caller → Plivo Voice → FastAPI Voice Gateway → Gemini Live
                              ↓
                        Function tools → Express HMS APIs
```

- Multi-hospital tenancy via Plivo DID → tenant registry (Mongo + optional Redis cache)
- Per-hospital static HMS JWT (`x-auth-token`) stored on the tenant record
- Isolated session per call with barge-in (`clearAudio` on Gemini `interrupted`)
- Provider abstraction (`VoiceProvider`) with Gemini implemented and OpenAI Realtime stubbed

## Quick start

```bash
cp .env.example .env
# Fill PLIVO_*, GEMINI_API_KEY, ADMIN_API_KEY, PUBLIC_* URLs

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Local Mongo/Redis (or use docker compose)
docker compose up -d mongo redis

uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Admin dashboard (multi-hospital onboarding)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with `ADMIN_API_KEY`.  
See [frontend/README.md](frontend/README.md).

Register a hospital tenant:

```bash
curl -X POST http://localhost:8080/admin/tenants \
  -H "X-Admin-Api-Key: change-me-admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "srichakra",
    "name": "Sri Chakra Diagnostics",
    "plivo_numbers": ["+91XXXXXXXXXX"],
    "hms_base_url": "https://hms-server.lalluvemula.cloud/api",
    "hms_subdomain": "srichakra",
    "hms_auth_token": "<static-jwt>",
    "transfer_number": "+91YYYYYYYYYY",
    "prompt_version": "v1"
  }'
```

Point your Plivo application **Answer URL** to `https://<host>/plivo/answer` and **Hangup URL** to `https://<host>/plivo/hangup`. The answer webhook returns bidirectional `<Stream>` XML to `wss://<host>/ws/plivo/stream`.

## Documentation

- [API reference](docs/API.md)
- [Deployment guide](docs/DEPLOYMENT.md)
- [Testing guide](docs/TESTING.md)

## Health

| Endpoint   | Purpose              |
|-----------|----------------------|
| `GET /health`  | Liveness + snapshot |
| `GET /live`    | Process alive       |
| `GET /ready`   | Dependencies ready  |
| `GET /metrics` | Prometheus metrics  |

## Project layout

See `app/` for clean-architecture modules: `api`, `audio`, `providers`, `tools`, `hms`, `tenants`, `sessions`, `prompts`.

## License

Proprietary — Healeka / Sri Chakra Diagnostics.
