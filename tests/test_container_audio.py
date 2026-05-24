from pathlib import Path

import numpy as np
import pytest

import cypher.main as cypher


def test_header_roundtrip() -> None:
    header = cypher.create_header(
        input_path="report.pdf",
        raw_size=123,
        checksum="abc123",
        relative_path="case/report.pdf",
    )

    decoded = cypher.decode_header(cypher.encode_header(header))

    assert decoded == header


def test_parse_container_rejects_bad_magic() -> None:
    with pytest.raises(ValueError, match="Invalid cypher container magic"):
        cypher.parse_container(b"BADMAGIC")


def test_parse_audio_payload_rejects_bad_magic() -> None:
    with pytest.raises(ValueError, match="Invalid cypher audio magic"):
        cypher.parse_audio_payload(b"NOTCYPHER")


def test_bytes_to_int16_samples_pads_odd_payload() -> None:
    samples = cypher.bytes_to_int16_samples(b"abc")

    assert isinstance(samples, np.ndarray)
    assert samples.dtype == np.int16
    assert samples.tobytes() == b"abc\x00"


def test_split_chunks_empty_payload_returns_one_empty_chunk() -> None:
    assert cypher.split_chunks(b"", 10) == [b""]


def test_split_chunks_exact_boundaries() -> None:
    assert cypher.split_chunks(b"abcdef", 2) == [b"ab", b"cd", b"ef"]


def test_resolve_audio_output_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="Unsupported audio format"):
        cypher.resolve_audio_output(
            input_path=Path("payload.bin"),
            audio_format="ogg",
        )


def test_waveform_preview_rejects_empty_samples(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cypher, "WAVEFORM_DIR", tmp_path)

    with pytest.raises(ValueError, match="empty audio"):
        cypher.write_waveform_preview(
            audio_path="empty.flac",
            samples=np.array([], dtype=np.int16),
        )
