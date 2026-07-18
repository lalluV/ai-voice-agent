from __future__ import annotations

import os

import pytest

# Disable external deps for unit tests by default
os.environ.setdefault("PLIVO_VALIDATE_SIGNATURE", "false")
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")


@pytest.fixture
def sample_tenant_dict() -> dict:
    return {
        "tenant_id": "demo",
        "name": "Demo Hospital",
        "plivo_numbers": ["+919876543210"],
        "hms_base_url": "https://hms.example.com/api",
        "hms_subdomain": "demo",
        "hms_auth_token": "jwt-token",
        "transfer_number": "+919999999999",
        "enabled": True,
    }
