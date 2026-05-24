from argparse import Namespace
from pathlib import Path

import pytest

import cypher.main as cypher


def test_resolve_default_public_key_uses_default_when_present(
    tmp_path,
    monkeypatch,
) -> None:
    public_key = tmp_path / "cypher_public.pem"
    public_key.write_text("public")

    monkeypatch.setattr(cypher, "DEFAULT_PUBLIC_KEY_PATH", public_key)

    assert cypher.resolve_default_public_key(None) == str(public_key)


def test_resolve_default_public_key_prefers_explicit() -> None:
    assert cypher.resolve_default_public_key("explicit.pem") == "explicit.pem"


def test_resolve_default_private_key_uses_default_when_present(
    tmp_path,
    monkeypatch,
) -> None:
    private_key = tmp_path / "cypher_private.pem"
    private_key.write_text("private")

    monkeypatch.setattr(cypher, "DEFAULT_PRIVATE_KEY_PATH", private_key)

    assert cypher.resolve_default_private_key(None) == str(private_key)


def test_resolve_default_private_key_returns_none_without_default(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        cypher,
        "DEFAULT_PRIVATE_KEY_PATH",
        tmp_path / "missing_private.pem",
    )

    assert cypher.resolve_default_private_key(None) is None


def test_validate_header_rejects_unsupported_version() -> None:
    header = cypher.CypherHeader(
        original_name="x.txt",
        original_suffix=".txt",
        mime_type="text/plain",
        raw_size=1,
        checksum="abc",
        version=999,
    )

    with pytest.raises(ValueError, match="Unsupported version"):
        cypher.validate_header(header)


def test_validate_header_rejects_unsupported_payload_mode() -> None:
    header = cypher.CypherHeader(
        original_name="x.txt",
        original_suffix=".txt",
        mime_type="text/plain",
        raw_size=1,
        checksum="abc",
        payload_mode="BAD",
    )

    with pytest.raises(ValueError, match="Unsupported payload mode"):
        cypher.validate_header(header)


def test_validate_header_rejects_empty_original_name() -> None:
    header = cypher.CypherHeader(
        original_name="",
        original_suffix="",
        mime_type="application/octet-stream",
        raw_size=1,
        checksum="abc",
    )

    with pytest.raises(ValueError, match="Original filename cannot be empty"):
        cypher.validate_header(header)


def test_validate_header_rejects_empty_checksum() -> None:
    header = cypher.CypherHeader(
        original_name="x.bin",
        original_suffix=".bin",
        mime_type="application/octet-stream",
        raw_size=1,
        checksum="",
    )

    with pytest.raises(ValueError, match="Checksum cannot be empty"):
        cypher.validate_header(header)


def test_validate_bundle_header_rejects_bad_magic() -> None:
    header = cypher.BundleHeader(
        files_count=1,
        magic="BAD",
    )

    with pytest.raises(ValueError, match="Invalid bundle magic"):
        cypher.validate_bundle_header(header)


def test_validate_bundle_header_rejects_bad_version() -> None:
    header = cypher.BundleHeader(
        files_count=1,
        version=999,
    )

    with pytest.raises(ValueError, match="Unsupported bundle version"):
        cypher.validate_bundle_header(header)


def test_parse_bundle_container_rejects_trailing_bytes() -> None:
    payload = b"data"

    header = cypher.create_header(
        input_path="x.bin",
        raw_size=len(payload),
        checksum=cypher.compute_checksum(payload),
    )

    bundle = cypher.build_bundle_container([(header, payload)]) + b"junk"

    with pytest.raises(ValueError, match="Unexpected trailing bytes"):
        cypher.parse_bundle_container(bundle)


def test_parse_bundle_container_rejects_file_size_mismatch() -> None:
    payload = b"data"

    header = cypher.create_header(
        input_path="x.bin",
        raw_size=len(payload),
        checksum=cypher.compute_checksum(payload),
    )

    header_bytes = cypher.encode_header(header)
    bundle_header = cypher.BundleHeader(files_count=1)
    bundle_header_bytes = cypher.json.dumps(
        cypher.asdict(bundle_header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    malformed = (
        cypher.BUNDLE_MAGIC
        + len(bundle_header_bytes).to_bytes(8, "big")
        + bundle_header_bytes
        + len(header_bytes).to_bytes(8, "big")
        + header_bytes
        + (len(payload) + 10).to_bytes(8, "big")
        + payload
    )

    with pytest.raises(ValueError, match="Unexpected trailing bytes"):
        cypher.parse_bundle_container(malformed)


def test_parse_bundle_container_rejects_checksum_mismatch() -> None:
    payload = b"data"

    header = cypher.create_header(
        input_path="x.bin",
        raw_size=len(payload),
        checksum="wrong",
    )

    header_bytes = cypher.encode_header(header)
    bundle_header = cypher.BundleHeader(files_count=1)
    bundle_header_bytes = cypher.json.dumps(
        cypher.asdict(bundle_header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    malformed = (
        cypher.BUNDLE_MAGIC
        + len(bundle_header_bytes).to_bytes(8, "big")
        + bundle_header_bytes
        + len(header_bytes).to_bytes(8, "big")
        + header_bytes
        + len(payload).to_bytes(8, "big")
        + payload
    )

    with pytest.raises(ValueError, match="Checksum mismatch"):
        cypher.parse_bundle_container(malformed)


def test_decode_header_backfills_missing_relative_path() -> None:
    encoded = cypher.json.dumps(
        {
            "magic": cypher.MAGIC,
            "version": cypher.HEADER_VERSION,
            "payload_mode": cypher.PAYLOAD_MODE,
            "checksum_algorithm": cypher.CHECKSUM_ALGORITHM,
            "compression_algorithm": cypher.COMPRESSION_ALGORITHM,
            "original_name": "legacy.txt",
            "original_suffix": ".txt",
            "mime_type": "text/plain",
            "raw_size": 1,
            "checksum": "abc",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    header = cypher.decode_header(encoded)

    assert header.relative_path is None


def test_parse_container_rejects_bad_payload_size() -> None:
    header = cypher.create_header(
        input_path="x.bin",
        raw_size=10,
        checksum="abc",
    )

    container = cypher.CONTAINER_MAGIC
    header_bytes = cypher.encode_header(header)

    malformed = (
        container
        + len(header_bytes).to_bytes(8, "big")
        + header_bytes
        + b"tiny"
    )

    with pytest.raises(ValueError, match="Invalid payload size"):
        cypher.parse_container(malformed)


def test_decode_command_rejects_checksum_mismatch(monkeypatch) -> None:
    header = cypher.create_header(
        input_path="x.txt",
        raw_size=3,
        checksum="wrong",
    )

    container = cypher.build_container(header, b"abc")

    monkeypatch.setattr(
        cypher,
        "resolve_input_audio",
        lambda file: Path("payload.flac"),
    )
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: ({"crypto_mode": cypher.CRYPTO_MODE_NONE}, b"chunked"),
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
        lambda payload, private_key: container,
    )

    with pytest.raises(ValueError, match="Checksum mismatch"):
        cypher.decode_command(
            Namespace(
                file="payload.flac",
                output=None,
                private_key=None,
            )
        )


def test_decode_command_writes_custom_output(monkeypatch, tmp_path) -> None:
    output_file = tmp_path / "custom.txt"
    restored = b"abc"

    header = cypher.create_header(
        input_path="x.txt",
        raw_size=len(restored),
        checksum=cypher.compute_checksum(restored),
    )

    container = cypher.build_container(header, restored)

    monkeypatch.setattr(
        cypher,
        "resolve_input_audio",
        lambda file: Path("payload.flac"),
    )
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: ({"crypto_mode": cypher.CRYPTO_MODE_NONE}, b"chunked"),
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
        lambda payload, private_key: container,
    )

    cypher.decode_command(
        Namespace(
            file="payload.flac",
            output=str(output_file),
            private_key=None,
        )
    )

    assert output_file.read_bytes() == restored


def test_decode_command_restores_bundle_payload(monkeypatch, tmp_path) -> None:
    payload = b"abc"

    file_header = cypher.create_header(
        input_path="x.txt",
        raw_size=len(payload),
        checksum=cypher.compute_checksum(payload),
        relative_path="x.txt",
    )

    bundle_payload = cypher.build_bundle_container([(file_header, payload)])

    header = cypher.create_header(
        input_path="bundle.cypherbundle",
        raw_size=len(bundle_payload),
        checksum=cypher.compute_checksum(bundle_payload),
        payload_mode=cypher.BUNDLE_PAYLOAD_MODE,
        relative_path="bundle",
    )

    container = cypher.build_container(header, bundle_payload)

    monkeypatch.setattr(
        cypher,
        "resolve_input_audio",
        lambda file: Path("payload.flac"),
    )
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: ({"crypto_mode": cypher.CRYPTO_MODE_NONE}, b"chunked"),
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
        lambda payload, private_key: container,
    )

    cypher.decode_command(
        Namespace(
            file="payload.flac",
            output=str(tmp_path / "bundle-out"),
            private_key=None,
        )
    )

    assert (tmp_path / "bundle-out" / "x.txt").read_bytes() == payload
