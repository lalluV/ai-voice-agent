from __future__ import annotations

from app.domain.enums import CallDirection
from app.domain.models import CallSession
from app.prompts.loader import PromptLoader
from app.tools.helpers import (
    customer_phone,
    format_phone_for_speech,
    phone_missing_payload,
)


def test_customer_phone_inbound() -> None:
    session = CallSession(
        tenant_id="t1",
        direction=CallDirection.INBOUND,
        from_number="+919876543210",
        to_number="+911234567890",
    )
    assert customer_phone(session) == "+919876543210"


def test_customer_phone_outbound() -> None:
    session = CallSession(
        tenant_id="t1",
        direction=CallDirection.OUTBOUND,
        from_number="+911234567890",
        to_number="+919876543210",
    )
    assert customer_phone(session) == "+919876543210"


def test_format_phone_for_speech() -> None:
    assert format_phone_for_speech("+919876543210") == "98765 43210"


def test_phone_missing_payload_includes_caller() -> None:
    session = CallSession(
        tenant_id="t1",
        direction=CallDirection.INBOUND,
        from_number="+919876543210",
    )
    payload = phone_missing_payload(session)
    assert payload["callerNumber"] == "+919876543210"
    assert "98765 43210" in payload["instruction"]
    assert "verify" in payload["instruction"].lower() or "read" in payload["instruction"].lower()


def test_build_system_instruction_includes_caller_number() -> None:
    loader = PromptLoader()
    text = loader.build_system_instruction(
        "v1",
        hospital_name="Sri Chakra",
        caller_number="+919876543210",
        caller_number_spoken="98765 43210",
    )
    assert "+919876543210" in text
    assert "98765 43210" in text
    assert "use this" in text.lower() or "calling number" in text.lower()
