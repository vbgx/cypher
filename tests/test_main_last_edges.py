from argparse import Namespace
from pathlib import Path

import pytest

import cypher.main as cypher


def test_resolve_input_audio_prefers_direct_path(tmp_path) -> None:
    audio = tmp_path / "payload.flac"
    audio.write_text("audio")

    assert cypher.resolve_input_audio(audio) == audio


def test_parse_container_rejects_bad_magic_extra() -> None:
    with pytest.raises(ValueError, match="Invalid cypher container magic"):
        cypher.parse_container(b"WRONG")


def test_build_bundle_container_rejects_payload_size_mismatch() -> None:
    header = cypher.create_header(
        input_path="x.txt",
        raw_size=99,
        checksum=cypher.compute_checksum(b"abc"),
    )

    with pytest.raises(ValueError, match="Invalid bundled payload size"):
        cypher.build_bundle_container([(header, b"abc")])


def test_build_bundle_container_rejects_checksum_mismatch_after_size_match() -> None:
    payload = b"abc"

    header = cypher.create_header(
        input_path="x.txt",
        raw_size=len(payload),
        checksum="wrong",
    )

    with pytest.raises(ValueError, match="Checksum mismatch before bundling"):
        cypher.build_bundle_container([(header, payload)])


def test_load_public_key_wrong_type_branch(monkeypatch, tmp_path) -> None:
    pem = tmp_path / "key.pem"
    pem.write_text("fake")

    monkeypatch.setattr(
        cypher.serialization,
        "load_pem_public_key",
        lambda payload: object(),
    )

    with pytest.raises(TypeError, match="Public key must be"):
        cypher.load_public_key(pem)


def test_load_private_key_wrong_type_branch(monkeypatch, tmp_path) -> None:
    pem = tmp_path / "key.pem"
    pem.write_text("fake")

    monkeypatch.setattr(
        cypher,
        "load_private_key_password_from_keychain",
        lambda: "password",
    )
    monkeypatch.setattr(
        cypher.serialization,
        "load_pem_private_key",
        lambda payload, password: object(),
    )

    with pytest.raises(TypeError, match="Private key must be"):
        cypher.load_private_key(pem)


def test_decrypt_payload_multi_rejects_invalid_nonce(monkeypatch) -> None:
    monkeypatch.setattr(
        cypher,
        "load_private_key",
        lambda path: object(),
    )

    with pytest.raises(ValueError, match="Invalid payload nonce"):
        cypher.decrypt_payload_multi(
            ciphertext=b"x",
            crypto_meta={
                "recipients": [],
                "nonce": None,
            },
            private_key_path="private.pem",
        )


def test_decode_chunked_payload_rejects_wrong_raw_size(monkeypatch) -> None:
    chunk = b"raw"
    compressed = cypher.compress_container(chunk, 9)

    chunk_header = cypher.ChunkHeader(
        index=1,
        total_chunks=1,
        raw_size=999,
        compressed_size=len(compressed),
        encrypted=False,
    )

    header_bytes = cypher.json.dumps(
        cypher.asdict(chunk_header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    crypto_bytes = cypher.json.dumps(
        {"crypto_mode": cypher.CRYPTO_MODE_NONE},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    serialized = (
        len(header_bytes).to_bytes(8, "big")
        + header_bytes
        + len(crypto_bytes).to_bytes(8, "big")
        + crypto_bytes
        + len(compressed).to_bytes(8, "big")
        + compressed
    )

    with pytest.raises(ValueError, match="Invalid decoded chunk size"):
        cypher.decode_chunked_payload(serialized, private_key=None)


def test_decode_chunked_payload_multi_branch(monkeypatch) -> None:
    chunk = b"raw"
    compressed = cypher.compress_container(chunk, 9)

    chunk_header = cypher.ChunkHeader(
        index=1,
        total_chunks=1,
        raw_size=len(chunk),
        compressed_size=len(compressed),
        encrypted=True,
    )

    header_bytes = cypher.json.dumps(
        cypher.asdict(chunk_header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    crypto_bytes = cypher.json.dumps(
        {"crypto_mode": cypher.CRYPTO_MODE_X25519_AESGCM_MULTI},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    serialized = (
        len(header_bytes).to_bytes(8, "big")
        + header_bytes
        + len(crypto_bytes).to_bytes(8, "big")
        + crypto_bytes
        + len(b"cipher").to_bytes(8, "big")
        + b"cipher"
    )

    monkeypatch.setattr(
        cypher,
        "decrypt_payload_multi",
        lambda ciphertext, crypto_meta, private_key_path: compressed,
    )

    assert cypher.decode_chunked_payload(serialized, "private.pem") == chunk


def test_read_audio_payload_delegates(monkeypatch) -> None:
    monkeypatch.setattr(
        cypher,
        "read_audio",
        lambda path: (44100, cypher.np.array([1, 2], dtype=cypher.np.int16)),
    )
    monkeypatch.setattr(
        cypher,
        "int16_samples_to_bytes",
        lambda samples: b"audio-payload",
    )
    monkeypatch.setattr(
        cypher,
        "parse_audio_payload",
        lambda payload: ({"crypto_mode": cypher.CRYPTO_MODE_NONE}, b"payload"),
    )

    meta, payload = cypher.read_audio_payload("x.flac")

    assert meta["crypto_mode"] == cypher.CRYPTO_MODE_NONE
    assert payload == b"payload"


def test_encode_container_to_audio_logs_relative_path(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    header = cypher.create_header(
        input_path="x.txt",
        raw_size=1,
        checksum="abc",
        relative_path="folder/x.txt",
    )

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
        cypher,
        "bytes_to_int16_samples",
        lambda payload: cypher.np.array([1], dtype=cypher.np.int16),
    )
    monkeypatch.setattr(cypher, "write_audio", lambda **kwargs: None)
    monkeypatch.setattr(cypher, "write_waveform_preview", lambda **kwargs: None)

    cypher.encode_container_to_audio(
        container=b"x",
        header=header,
        output_path=tmp_path / "x.flac",
        sample_rate=cypher.DEFAULT_SAMPLE_RATE,
        compression_level=9,
        public_key=None,
    )

    assert "Relative path" in capsys.readouterr().out


def test_decode_command_without_private_key_for_encrypted_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        cypher,
        "resolve_input_audio",
        lambda file: Path("payload.flac"),
    )
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: ({"crypto_mode": "x"}, b"payload"),
    )
    monkeypatch.setattr(
        cypher,
        "resolve_default_private_key",
        lambda private_key: None,
    )
    monkeypatch.setattr(cypher, "require_touch_id", lambda reason: None)
    monkeypatch.setattr(
        cypher,
        "decode_chunked_payload",
        lambda payload, private_key: (_ for _ in ()).throw(
            ValueError("Private key path is required")
        ),
    )

    with pytest.raises(ValueError, match="Private key path is required"):
        cypher.decode_command(
            Namespace(
                file="payload.flac",
                output=None,
                private_key=None,
            )
        )


def test_restore_bundle_payload_infers_root(tmp_path) -> None:
    payload = b"abc"

    header = cypher.create_header(
        input_path="x.txt",
        raw_size=len(payload),
        checksum=cypher.compute_checksum(payload),
        relative_path="project/x.txt",
    )

    bundle = cypher.build_bundle_container([(header, payload)])
    output_dir = tmp_path / "restore"

    cypher.restore_bundle_payload(
        audio_path=Path("payload.flac"),
        restored_payload=bundle,
        bundle_checksum=cypher.compute_checksum(bundle),
        output_dir=output_dir,
        bundle_name=None,
    )

    assert (output_dir / "x.txt").read_bytes() == payload


def test_restore_bundle_payload_rejects_absolute_path(tmp_path) -> None:
    payload = b"abc"

    header = cypher.create_header(
        input_path="x.txt",
        raw_size=len(payload),
        checksum=cypher.compute_checksum(payload),
        relative_path="/tmp/x.txt",
    )

    bundle = cypher.build_bundle_container([(header, payload)])

    with pytest.raises(ValueError, match="Unsafe restore path"):
        cypher.restore_bundle_payload(
            audio_path=Path("payload.flac"),
            restored_payload=bundle,
            bundle_checksum=cypher.compute_checksum(bundle),
            output_dir=tmp_path,
            bundle_name=None,
        )


def test_inspect_command_none_public_meta(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cypher,
        "resolve_input_audio",
        lambda file: Path("payload.flac"),
    )
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: (
            {"crypto_mode": cypher.CRYPTO_MODE_NONE, "public": "bad"},
            b"payload",
        ),
    )

    cypher.inspect_command(Namespace(file="payload.flac"))

    assert "unknown" in capsys.readouterr().out
