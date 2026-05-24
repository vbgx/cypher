from __future__ import annotations

from pathlib import Path

import pytest

import cypher.audio as audio
import cypher.bundle as bundle
import cypher.container as container
import cypher.crypto as crypto
import cypher.keys as keys
import cypher.main as cypher


def test_audio_resolve_output_rejects_mp3() -> None:
    with pytest.raises(ValueError, match="MP3 is lossy"):
        audio.resolve_audio_output(Path("x.txt"), "mp3")


def test_audio_resolve_output_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported audio format"):
        audio.resolve_audio_output(Path("x.txt"), "ogg")


def test_audio_samples_pad_odd_payload() -> None:
    samples = audio.bytes_to_int16_samples(b"abc")
    assert samples.size == 2


def test_container_safe_relative_path_rejects_empty() -> None:
    with pytest.raises(ValueError, match="Invalid relative path"):
        container.safe_relative_path(Path("."))


def test_container_read_file_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Path is not a file"):
        container.read_file(tmp_path)


def test_container_parse_container_rejects_bad_magic() -> None:
    with pytest.raises(ValueError, match="Invalid cypher container magic"):
        container.parse_container(b"BAD")


def test_container_parse_container_rejects_payload_size() -> None:
    header = container.create_header(
        input_path="x.txt",
        raw_size=10,
        checksum=container.compute_checksum(b"abc"),
    )
    payload = container.build_container(header, b"abc")

    with pytest.raises(ValueError, match="Invalid payload size"):
        container.parse_container(payload)


def test_container_unique_output_path_exhausted(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("0")

    for index in range(1, 10_000):
        (tmp_path / f"x_{index}.txt").write_text("x")

    with pytest.raises(FileExistsError, match="Unable to create unique output path"):
        container.unique_output_path(tmp_path, "x.txt")


def test_bundle_validate_header_errors() -> None:
    with pytest.raises(ValueError, match="Invalid bundle magic"):
        bundle.validate_bundle_header(
            bundle.BundleHeader(files_count=1, magic="BAD")
        )

    with pytest.raises(ValueError, match="Unsupported bundle version"):
        bundle.validate_bundle_header(
            bundle.BundleHeader(files_count=1, version=-1)
        )

    with pytest.raises(ValueError, match="at least one file"):
        bundle.validate_bundle_header(bundle.BundleHeader(files_count=0))


def test_bundle_build_rejects_empty() -> None:
    with pytest.raises(ValueError, match="Bundle requires at least one file"):
        bundle.build_bundle_container([])


def test_crypto_decrypt_multi_rejects_invalid_nonce() -> None:
    with pytest.raises(ValueError, match="Invalid payload nonce"):
        crypto.decrypt_payload_multi(
            b"payload",
            {"recipients": [], "nonce": None},
            "private.pem",
        )


def test_crypto_decrypt_single_rejects_missing_metadata() -> None:
    with pytest.raises(ValueError, match="Invalid payload metadata"):
        crypto.decrypt_payload(b"payload", {}, "private.pem")


def test_keys_load_public_key_rejects_private_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePrivateKey:
        pass

    key_path = tmp_path / "key.pem"
    key_path.write_bytes(b"key")

    monkeypatch.setattr(
        keys.serialization,
        "load_pem_public_key",
        lambda _payload: FakePrivateKey(),
    )

    with pytest.raises(TypeError, match="Public key must be an X25519"):
        keys.load_public_key(key_path)


def test_main_decode_chunked_restores_patched_functions() -> None:
    before_single = cypher.container_mod.decrypt_payload
    before_multi = cypher.container_mod.decrypt_payload_multi

    with pytest.raises(ValueError):
        cypher.decode_chunked_payload(b"bad", None)

    assert cypher.container_mod.decrypt_payload is before_single
    assert cypher.container_mod.decrypt_payload_multi is before_multi
