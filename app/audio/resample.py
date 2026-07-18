from __future__ import annotations

import numpy as np
import soxr


def resample_pcm16(pcm_bytes: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resample mono PCM16 LE between sample rates."""
    if src_rate == dst_rate or not pcm_bytes:
        return pcm_bytes
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if samples.size == 0:
        return b""
    # soxr expects float for quality; convert back to int16
    float_samples = samples.astype(np.float32) / 32768.0
    resampled = soxr.resample(float_samples, src_rate, dst_rate, quality="LQ")
    out = np.clip(resampled * 32768.0, -32768, 32767).astype(np.int16)
    return out.tobytes()
