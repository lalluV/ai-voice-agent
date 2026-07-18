from app.audio.codec import mulaw_to_pcm16, pcm16_to_mulaw
from app.audio.resample import resample_pcm16


def test_mulaw_roundtrip_length() -> None:
    pcm = bytes([0, 0, 10, 0, 20, 0, 30, 0] * 20)
    mulaw = pcm16_to_mulaw(pcm)
    back = mulaw_to_pcm16(mulaw)
    assert len(mulaw) == len(pcm) // 2
    assert len(back) == len(pcm)


def test_resample_8k_to_16k_doubles_samples() -> None:
    # 160 samples @ 8k = 20ms
    pcm8k = bytes([0, 1] * 160)
    pcm16k = resample_pcm16(pcm8k, 8000, 16000)
    assert len(pcm16k) == len(pcm8k) * 2


def test_resample_24k_to_8k() -> None:
    pcm24k = bytes([0, 1] * 480)
    pcm8k = resample_pcm16(pcm24k, 24000, 8000)
    assert len(pcm8k) == len(pcm24k) // 3


def test_resample_identity() -> None:
    pcm = bytes([1, 2, 3, 4])
    assert resample_pcm16(pcm, 16000, 16000) == pcm
