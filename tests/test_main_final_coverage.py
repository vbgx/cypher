from argparse import Namespace
from pathlib import Path

import pytest

import cypher.main as cypher


def test_emit_progress_prints(capsys) -> None:
    cypher.emit_progress("phase", 1, 2)

    assert "PROGRESS phase=phase current=1 total=2" in capsys.readouterr().out


def test_generate_obfuscated_stem_length() -> None:
    assert len(cypher.generate_obfuscated_stem(12)) == 12


def test_detect_mime_type_fallback() -> None:
    assert cypher.detect_mime_type("unknown.nope") == "application/octet-stream"


def test_safe_relative_path_rejects_empty() -> None:
    with pytest.raises(ValueError, match="Invalid relative path"):
        cypher.safe_relative_path(Path("."))


def test_load_public_key_rejects_non_key(tmp_path) -> None:
    bad = tmp_path / "bad.pem"
    bad.write_text("not a key")

    with pytest.raises(ValueError):
        cypher.load_public_key(bad)


def test_load_private_key_rejects_public_key(tmp_path, monkeypatch) -> None:
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"

    cypher.generate_keypair(
        private_key_path=private_path,
        public_key_path=public_path,
        force=True,
    )

    monkeypatch.setattr(
        cypher,
        "load_private_key_password_from_keychain",
        lambda: "wrong-password",
    )

    with pytest.raises(ValueError):
        cypher.load_private_key(private_path)


def test_decrypt_payload_multi_skips_invalid_recipient(monkeypatch) -> None:
    class FakePrivateKey:
        pass

    monkeypatch.setattr(
        cypher,
        "load_private_key",
        lambda path: FakePrivateKey(),
    )

    with pytest.raises(ValueError, match="No matching private key"):
        cypher.decrypt_payload_multi(
            ciphertext=b"payload",
            crypto_meta={
                "nonce": "AAAA",
                "recipients": [
                    "bad-recipient",
                    {
                        "ephemeral_public_key": "bad",
                        "salt": "bad",
                        "wrap_nonce": "bad",
                        "wrapped_key": "bad",
                    },
                ],
            },
            private_key_path="private.pem",
        )


def test_build_audio_payload_encrypted_hides_public_metadata() -> None:
    header = cypher.create_header(
        input_path="secret.txt",
        raw_size=1,
        checksum="abc",
    )

    audio_payload = cypher.build_audio_payload(
        payload=b"x",
        header=header,
        crypto_meta={"crypto_mode": cypher.CRYPTO_MODE_X25519_AESGCM},
    )

    meta, payload = cypher.parse_audio_payload(audio_payload)

    assert payload == b"x"
    assert meta["public"]["payload_mode"] == "ENCRYPTED_CONTAINER"
    assert "original_name" not in meta["public"]


def test_decode_chunked_payload_legacy_single_recipient_branch(monkeypatch) -> None:
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

    crypto_meta = {"crypto_mode": cypher.CRYPTO_MODE_X25519_AESGCM}
    crypto_bytes = cypher.json.dumps(
        crypto_meta,
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
        "decrypt_payload",
        lambda ciphertext, crypto_meta, private_key_path: compressed,
    )

    assert cypher.decode_chunked_payload(serialized, "private.pem") == chunk


def test_benchmark_command_with_public_key(monkeypatch, tmp_path, capsys) -> None:
    payload = tmp_path / "payload.txt"
    payload.write_text("bench")

    monkeypatch.setattr(
        cypher,
        "resolve_default_public_keys",
        lambda keys: ["public.pem"],
    )
    monkeypatch.setattr(
        cypher,
        "encrypt_payload_multi",
        lambda payload, recipient_public_key_paths: (
            b"encrypted",
            {"crypto_mode": cypher.CRYPTO_MODE_X25519_AESGCM_MULTI},
        ),
    )

    cypher.benchmark_command(
        Namespace(
            file=str(payload),
            compression_level=9,
            public_key=["public.pem"],
        )
    )

    assert "Crypto            : x25519-aesgcm-multi" in capsys.readouterr().out


def test_bundle_command_rejects_empty_directory(tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(ValueError, match="Bundle is empty"):
        cypher.bundle_command(
            Namespace(
                files=[str(empty)],
                name=None,
                format="flac",
                keep_name=True,
                sample_rate=cypher.DEFAULT_SAMPLE_RATE,
                compression_level=9,
                public_key=None,
            )
        )


def test_bundle_command_rejects_unsupported_path(monkeypatch, tmp_path) -> None:
    broken = tmp_path / "broken"

    monkeypatch.setattr(
        cypher,
        "resolve_input_file",
        lambda path: broken,
    )

    with pytest.raises(ValueError, match="Unsupported path"):
        cypher.bundle_command(
            Namespace(
                files=[str(broken)],
                name=None,
                format="flac",
                keep_name=True,
                sample_rate=cypher.DEFAULT_SAMPLE_RATE,
                compression_level=9,
                public_key=None,
            )
        )


def test_inspect_command_encrypted_metadata(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cypher,
        "resolve_input_audio",
        lambda file: Path("payload.flac"),
    )
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: (
            {
                "crypto_mode": cypher.CRYPTO_MODE_X25519_AESGCM,
                "public": {
                    "cypher_version": cypher.VERSION,
                    "payload_mode": "ENCRYPTED_CONTAINER",
                },
            },
            b"payload",
        ),
    )

    cypher.inspect_command(Namespace(file="payload.flac"))

    assert "Metadata hidden" in capsys.readouterr().out


def test_add_audio_encode_options_rejects_bad_compression_level() -> None:
    parser = cypher.argparse.ArgumentParser()
    cypher.add_audio_encode_options(parser)

    with pytest.raises(SystemExit):
        parser.parse_args(["--compression-level", "99"])


def test_parser_version_exits(capsys) -> None:
    parser = cypher.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--version"])

    assert "cypher 1.0.0" in capsys.readouterr().out
