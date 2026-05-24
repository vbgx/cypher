from argparse import Namespace

import pytest

import cypher.main as cypher


def corrupt_first_frame_copy(payload: bytes) -> bytes:
    data = bytearray(payload)
    cursor = len(cypher.TRANSPORT_MAGIC)

    header_size = int.from_bytes(data[cursor : cursor + 8], "big")
    cursor += 8 + header_size

    frame_header_size = int.from_bytes(data[cursor : cursor + 8], "big")
    cursor += 8 + frame_header_size

    frame_size = int.from_bytes(data[cursor : cursor + 8], "big")
    cursor += 8

    assert frame_size > 0

    data[cursor] ^= 0xFF
    return bytes(data)


def test_transport_payload_roundtrip() -> None:
    payload = b"hello resilient audio transport" * 100

    encoded = cypher.encode_transport_payload(payload)
    decoded = cypher.decode_transport_payload(encoded)

    assert decoded == payload


def test_transport_recovers_from_one_corrupted_copy() -> None:
    payload = b"frame-data" * 1000

    encoded = cypher.encode_transport_payload(
        payload,
        redundancy=3,
        frame_size=128,
    )

    corrupted = corrupt_first_frame_copy(encoded)

    assert cypher.decode_transport_payload(corrupted) == payload


def test_transport_rejects_unrecoverable_corruption() -> None:
    payload = b"x" * 256

    encoded = cypher.encode_transport_payload(
        payload,
        redundancy=1,
        frame_size=128,
    )

    corrupted = corrupt_first_frame_copy(encoded)

    with pytest.raises(ValueError, match="Unable to recover"):
        cypher.decode_transport_payload(corrupted)


def test_transport_partial_recovery_skips_missing_frame() -> None:
    payload = b"a" * 128 + b"b" * 128

    encoded = cypher.encode_transport_payload(
        payload,
        redundancy=1,
        frame_size=128,
    )

    corrupted = corrupt_first_frame_copy(encoded)
    partial = cypher.decode_transport_payload(corrupted, allow_partial=True)

    assert partial == b"b" * 128


def test_transport_header_rejects_invalid_magic() -> None:
    header = cypher.TransportHeader(
        magic="BAD",
        version=cypher.TRANSPORT_VERSION,
        mode=cypher.TRANSPORT_MODE_REDUNDANT,
        original_size=1,
        original_crc32=1,
        frame_size=1,
        frame_count=1,
        redundancy=1,
    )

    with pytest.raises(ValueError, match="Invalid transport magic"):
        cypher.validate_transport_header(header)


def test_parser_accepts_redundancy_option() -> None:
    parser = cypher.build_parser()

    args = parser.parse_args(
        [
            "encode",
            "payload.bin",
            "--redundancy",
        ]
    )

    assert args.redundancy is True


def test_encode_container_to_audio_uses_transport_redundancy(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    header = cypher.create_header(
        input_path="payload.bin",
        raw_size=3,
        checksum=cypher.compute_checksum(b"abc"),
    )

    captured = {}

    monkeypatch.setattr(
        cypher,
        "encode_chunked_payload",
        lambda payload, compression_level, public_key: (
            b"chunked",
            cypher.CRYPTO_MODE_NONE,
            None,
        ),
    )
    monkeypatch.setattr(
        cypher.container_mod,
        "bytes_to_int16_samples",
        lambda payload: (
            captured.setdefault("payload", payload),
            cypher.np.array([1], dtype=cypher.np.int16),
        )[1],
    )
    monkeypatch.setattr(cypher.container_mod, "write_audio", lambda **kwargs: None)
    monkeypatch.setattr(
        cypher.container_mod,
        "write_waveform_preview",
        lambda **kwargs: None,
    )

    cypher.encode_container_to_audio(
        container=b"abc",
        header=header,
        output_path=tmp_path / "payload.flac",
        sample_rate=cypher.DEFAULT_SAMPLE_RATE,
        compression_level=9,
        public_key=None,
        redundancy=True,
    )

    output = capsys.readouterr().out

    assert "Transport         : redundant-crc32" in output
    assert b"CYPHERTRANSPORT14" in captured["payload"]


def test_decode_command_unwraps_transport_envelope(monkeypatch, tmp_path) -> None:
    restored_payload = b"abc"

    header = cypher.create_header(
        input_path="payload.bin",
        raw_size=len(restored_payload),
        checksum=cypher.compute_checksum(restored_payload),
    )

    container = cypher.build_container(header, restored_payload)
    transport = cypher.encode_transport_payload(b"chunked")

    monkeypatch.setattr(
        cypher,
        "resolve_input_audio",
        lambda file: tmp_path / "payload.flac",
    )
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: (
            {
                "crypto_mode": cypher.CRYPTO_MODE_NONE,
                "transport_mode": "redundant-crc32",
            },
            transport,
        ),
    )
    monkeypatch.setattr(cypher, "require_touch_id", lambda reason: None)
    monkeypatch.setattr(cypher, "resolve_default_private_key", lambda key: None)
    monkeypatch.setattr(
        cypher,
        "decode_chunked_payload",
        lambda payload, private_key: container if payload == b"chunked" else b"",
    )

    cypher.decode_command(
        Namespace(
            file="payload.flac",
            output=str(tmp_path / "out.bin"),
            private_key=None,
            allow_partial=False,
        )
    )

    assert (tmp_path / "out.bin").read_bytes() == restored_payload
