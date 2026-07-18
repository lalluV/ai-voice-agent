from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.domain.enums import AIProvider, CallDirection, CallEndReason, SessionStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(BaseModel):
    tenant_id: str
    name: str
    plivo_numbers: list[str] = Field(default_factory=list)
    hms_base_url: str
    hms_subdomain: str
    hms_auth_token: str
    ai_provider: AIProvider = AIProvider.GEMINI
    gemini_api_key: str | None = None
    voice_name: str = "Aoede"
    prompt_version: str = "v1"
    transfer_number: str | None = None
    hospital_blurb: str | None = None
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def normalized_numbers(self) -> set[str]:
        return {_normalize_phone(n) for n in self.plivo_numbers}


class TenantCreate(BaseModel):
    tenant_id: str
    name: str
    plivo_numbers: list[str] = Field(default_factory=list)
    hms_base_url: str
    hms_subdomain: str
    hms_auth_token: str
    ai_provider: AIProvider = AIProvider.GEMINI
    gemini_api_key: str | None = None
    voice_name: str = "Aoede"
    prompt_version: str = "v1"
    transfer_number: str | None = None
    hospital_blurb: str | None = None
    enabled: bool = True


class TenantUpdate(BaseModel):
    name: str | None = None
    plivo_numbers: list[str] | None = None
    hms_base_url: str | None = None
    hms_subdomain: str | None = None
    hms_auth_token: str | None = None
    ai_provider: AIProvider | None = None
    gemini_api_key: str | None = None
    voice_name: str | None = None
    prompt_version: str | None = None
    transfer_number: str | None = None
    hospital_blurb: str | None = None
    enabled: bool | None = None


class TenantPublic(BaseModel):
    """Safe tenant view — never exposes HMS JWT or Gemini keys."""

    tenant_id: str
    name: str
    plivo_numbers: list[str]
    hms_base_url: str
    hms_subdomain: str
    ai_provider: AIProvider
    voice_name: str
    prompt_version: str
    transfer_number: str | None = None
    hospital_blurb: str | None = None
    enabled: bool
    has_hms_token: bool = False
    has_gemini_key: bool = False
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_tenant(cls, tenant: Tenant) -> TenantPublic:
        return cls(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            plivo_numbers=tenant.plivo_numbers,
            hms_base_url=tenant.hms_base_url,
            hms_subdomain=tenant.hms_subdomain,
            ai_provider=tenant.ai_provider,
            voice_name=tenant.voice_name,
            prompt_version=tenant.prompt_version,
            transfer_number=tenant.transfer_number,
            hospital_blurb=tenant.hospital_blurb,
            enabled=tenant.enabled,
            has_hms_token=bool(tenant.hms_auth_token),
            has_gemini_key=bool(tenant.gemini_api_key),
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )


class CallSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    call_id: str | None = None
    stream_id: str | None = None
    direction: CallDirection = CallDirection.INBOUND
    from_number: str | None = None
    to_number: str | None = None
    language: str | None = None
    current_intent: str | None = None
    tool_context: dict[str, Any] = Field(default_factory=dict)
    status: SessionStatus = SessionStatus.CREATED
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime | None = None
    end_reason: CallEndReason | None = None
    interruption_count: int = 0
    tool_call_count: int = 0
    error_message: str | None = None


class CallLog(BaseModel):
    session_id: str
    tenant_id: str
    call_id: str | None = None
    direction: CallDirection
    from_number: str | None = None
    to_number: str | None = None
    language: str | None = None
    status: SessionStatus
    end_reason: CallEndReason | None = None
    interruption_count: int = 0
    tool_call_count: int = 0
    duration_seconds: float | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class OutboundCallRequest(BaseModel):
    tenant_id: str
    to_number: str
    from_number: str | None = None
    answer_url: str | None = None


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    id: str
    name: str
    success: bool
    data: Any = None
    error: str | None = None


def _normalize_phone(number: str) -> str:
    digits = "".join(c for c in number if c.isdigit() or c == "+")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    return digits
