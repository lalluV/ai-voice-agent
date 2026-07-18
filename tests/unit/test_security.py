from app.core.config import Settings
from app.core.security import compute_plivo_signature_v3, verify_plivo_signature


def test_compute_plivo_signature_stable() -> None:
    sig = compute_plivo_signature_v3(
        "token",
        "nonce1",
        "POST",
        "https://example.com/plivo/answer",
        {"CallUUID": "abc", "From": "+91"},
    )
    sig2 = compute_plivo_signature_v3(
        "token",
        "nonce1",
        "POST",
        "https://example.com/plivo/answer",
        {"From": "+91", "CallUUID": "abc"},
    )
    assert sig == sig2
    assert isinstance(sig, str)
    assert len(sig) > 10


def test_verify_skips_when_disabled() -> None:
    settings = Settings(plivo_validate_signature=False, plivo_auth_token="x")
    verify_plivo_signature(
        settings=settings,
        signature_header=None,
        nonce=None,
        method="POST",
        uri="https://example.com/x",
        params={},
    )
