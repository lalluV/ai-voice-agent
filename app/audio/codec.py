from __future__ import annotations

import audioop


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """Decode G.711 μ-law to 16-bit little-endian PCM."""
    return audioop.ulaw2lin(mulaw_bytes, 2)


def pcm16_to_mulaw(pcm_bytes: bytes) -> bytes:
    """Encode 16-bit little-endian PCM to G.711 μ-law."""
    return audioop.lin2ulaw(pcm_bytes, 2)


def pcm16_to_l16_bytes(pcm_bytes: bytes) -> bytes:
    """Identity helper — L16 is raw PCM16 LE."""
    return pcm_bytes
