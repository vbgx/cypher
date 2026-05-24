import numpy as np
import pytest

import cypher.main as cypher


def test_write_and_read_audio_roundtrip(tmp_path) -> None:
    audio_path = tmp_path / "payload.flac"
    samples = np.array([0, 1, -1, 256, -256], dtype=np.int16)

    cypher.write_audio(
        path=audio_path,
        samples=samples,
        sample_rate=cypher.DEFAULT_SAMPLE_RATE,
    )

    sample_rate, restored = cypher.read_audio(audio_path)

    assert sample_rate == cypher.DEFAULT_SAMPLE_RATE
    assert restored.dtype == np.int16
    assert restored.tolist() == samples.tolist()


def test_read_audio_rejects_stereo(tmp_path, monkeypatch) -> None:
    def fake_read(path, dtype):
        return np.array([[1, 2], [3, 4]], dtype=np.int16), 44100

    monkeypatch.setattr(cypher.sf, "read", fake_read)

    with pytest.raises(ValueError, match="must be mono"):
        cypher.read_audio(tmp_path / "stereo.flac")


def test_write_waveform_preview_creates_pgm(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cypher, "WAVEFORM_DIR", tmp_path)

    output = cypher.write_waveform_preview(
        audio_path="payload.flac",
        samples=np.array([0, 10, -10, 20, -20], dtype=np.int16),
        width=10,
        height=20,
    )

    assert output.exists()
    assert output.read_bytes().startswith(b"P5\n")
