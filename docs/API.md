# API Documentation

Base URL: configured via `PUBLIC_BASE_URL` (local default `http://localhost:8080`).

Admin routes require header: `X-Admin-Api-Key: <ADMIN_API_KEY>`.

Plivo webhook routes validate `X-Plivo-Signature-V3` + `X-Plivo-Signature-V3-Nonce` when `PLIVO_VALIDATE_SIGNATURE=true`.

## Health

### `GET /health`

Returns process status and metric snapshot.

### `GET /live`

Liveness probe — always `{"status":"alive"}` if the process is up.

### `GET /ready`

Readiness probe. Returns `503` during shutdown or if Mongo (and Redis when enabled) are unavailable.

### `GET /metrics`

Prometheus text exposition format.

## Tenants (admin)

### `GET /admin/tenants`

List tenants (JWT redacted).

### `POST /admin/tenants`

Create tenant.

```json
{
  "tenant_id": "srichakra",
  "name": "Sri Chakra Diagnostics",
  "plivo_numbers": ["+91XXXXXXXXXX"],
  "hms_base_url": "https://hms-server.lalluvemula.cloud/api",
  "hms_subdomain": "srichakra",
  "hms_auth_token": "<static JWT>",
  "ai_provider": "gemini",
  "voice_name": "Kore",
  "prompt_version": "v1",
  "transfer_number": "+91YYYYYYYYYY",
  "hospital_blurb": "Optional short hospital description",
  "enabled": true
}
```

### `GET /admin/tenants/{tenant_id}`

### `PATCH /admin/tenants/{tenant_id}`

Partial update. Invalidates DID cache entries.

### `DELETE /admin/tenants/{tenant_id}`

## Plivo webhooks

### `POST /plivo/answer`

Form fields from Plivo (`CallUUID`, `From`, `To`, `Direction`, …).

Resolves tenant by inbound `To` (or outbound `From`), creates a session, returns:

```xml
<Response>
  <Stream bidirectional="true" keepCallAlive="true"
          contentType="audio/x-mulaw;rate=8000"
          extraHeaders="tenantId=...;sessionId=...">
    wss://host/ws/plivo/stream
  </Stream>
</Response>
```

### `POST /plivo/hangup`

Ends the associated session.

### `POST /plivo/stream-status`

Optional stream status callback logging.

### `GET /plivo/transfer-xml?to=+91...`

Returns Dial XML used during human transfer.

## WebSocket

### `WS /ws/plivo/stream`

Plivo bidirectional media events: `start`, `media`, `dtmf`, `stop`.

Outbound events from server: `playAudio`, `clearAudio`.

## Outbound calls (admin)

### `POST /calls/outbound`

```json
{
  "tenant_id": "srichakra",
  "to_number": "+91XXXXXXXXXX",
  "from_number": null
}
```

Uses Plivo REST to place a call answered by `/plivo/answer`.

## Function tools (AI → HMS)

| Tool | HMS / telephony mapping |
|------|-------------------------|
| `patientSearch` | `GET /patients`, `GET /patients/phone/:phone` |
| `createPatient` | `POST /patients` |
| `bookAppointment` | `POST /appointments` |
| `cancelAppointment` | `PUT/DELETE /appointments/:id` |
| `departmentList` | `GET /departments` (Redis cached) |
| `doctorAvailability` | Best-effort `GET /staff/type/Doctor` (TODO: real slots API) |
| `labReports` | Best-effort diagnostics receipts (TODO) |
| `generateBill` | `GET /patients/:id/interim-bill` |
| `sendWhatsapp` | Prescription WhatsApp only (TODO: general messaging) |
| `transferCall` | Plivo Call Transfer API |
