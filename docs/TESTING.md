# Testing Guide

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Unit/integration tests mock Plivo, Gemini, and HMS. Mongo/Redis are not required for the default suite.

## Run tests

```bash
pytest -q
pytest --cov=app --cov-report=term-missing
```

## What is covered

| Area | Location |
|------|----------|
| μ-law codec + resample | `tests/unit/test_codec_resample.py` |
| Plivo signature helper | `tests/unit/test_security.py` |
| Tenant DID resolver | `tests/unit/test_tenant_resolver.py` |
| Prompt loader | `tests/unit/test_prompt_loader.py` |
| Tool handlers / router | `tests/unit/test_tools.py` |
| Audio bridge + barge-in | `tests/integration/test_audio_bridge.py` |
| Plivo answer XML | `tests/integration/test_plivo_answer.py` |
| HMS httpx client headers | `tests/integration/test_hms_client.py` |

## Load test example

Stress-tests the audio bridge with a silent mock provider (no network):

```bash
python scripts/load_test_example.py --concurrency 50 --chunks 100
```

## Manual call test checklist

1. Start stack (`docker compose up` or local uvicorn + mongo/redis).
2. Create tenant with a real Plivo DID and HMS JWT.
3. Place inbound call to the DID.
4. Confirm `/metrics` shows `voice_concurrent_calls` increasing.
5. Speak in Telugu/English; verify language matching.
6. Interrupt the agent mid-sentence — playback should stop (`clearAudio`).
7. Book/cancel appointment via tools against staging HMS.
8. Trigger `transferCall` to the configured receptionist number.
9. Hang up — call log written to Mongo `call_logs`.

## Mocking tips

- Set `PLIVO_VALIDATE_SIGNATURE=false` for local webhook curls.
- Point `hms_base_url` at a mock server or use staging HMS.
- Gemini can be skipped in unit tests; live calls need a valid `GEMINI_API_KEY`.
