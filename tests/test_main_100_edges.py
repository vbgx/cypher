from argparse import Namespace
from pathlib import Path

import pytest

import cypher.main as cypher


def test_resolve_input_audio_uses_audio_dir(tmp_path, monkeypatch) -> None:
    audio_dir = tmp_path / "audio"
    bundle_dir = audio_dir / "bundle"

    audio_dir.mkdir()
    bundle_dir.mkdir()

    audio = audio_dir / "payload.flac"
    audio.write_text("audio")

    monkeypatch.setattr(cypher, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(cypher, "BUNDLE_AUDIO_DIR", bundle_dir)

    assert cypher.resolve_input_audio("payload.flac") == audio


def test_build_bundle_container_checksum_mismatch_after_size_match() -> None:
    payload = b"abc"

    header = cypher.create_header(
        input_path="x.txt",
        raw_size=len(payload),
        checksum="wrong",
    )

    with pytest.raises(ValueError, match="Checksum mismatch before bundling"):
        cypher.build_bundle_container([(header, payload)])


def test_parse_bundle_container_checksum_mismatch_after_size_match() -> None:
    payload = b"abc"

    header = cypher.create_header(
        input_path="x.txt",
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


def test_encrypt_payload_multi_invalid_public_key_raises(tmp_path) -> None:
    bad_key = tmp_path / "bad.pem"
    bad_key.write_text("bad")

    with pytest.raises(ValueError):
        cypher.encrypt_payload_multi(b"payload", [bad_key])


def test_decrypt_payload_multi_all_recipients_fail(monkeypatch) -> None:
    class FakePrivateKey:
        def exchange(self, public_key):
            raise RuntimeError("exchange failed")

    monkeypatch.setattr(
        cypher,
        "load_private_key",
        lambda path: FakePrivateKey(),
    )
    monkeypatch.setattr(
        cypher.x25519.X25519PublicKey,
        "from_public_bytes",
        lambda payload: object(),
    )

    with pytest.raises(ValueError, match="No matching private key"):
        cypher.decrypt_payload_multi(
            ciphertext=b"payload",
            crypto_meta={
                "nonce": "AAAA",
                "recipients": [
                    {
                        "ephemeral_public_key": "AAAA",
                        "salt": "AAAA",
                        "wrap_nonce": "AAAA",
                        "wrapped_key": "AAAA",
                    }
                ],
            },
            private_key_path="private.pem",
        )


def test_build_audio_payload_plain_public_metadata() -> None:
    header = cypher.create_header(
        input_path="plain.txt",
        raw_size=3,
        checksum="abc",
    )

    audio_payload = cypher.build_audio_payload(
        payload=b"abc",
        header=header,
        crypto_meta=None,
    )

    meta, payload = cypher.parse_audio_payload(audio_payload)

    assert payload == b"abc"
    assert meta["public"]["original_name"] == "plain.txt"


def test_resolve_audio_output_keep_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cypher, "AUDIO_DIR", tmp_path)

    output = cypher.resolve_audio_output(
        input_path=Path("hello.txt"),
        audio_format="wav",
        obfuscate_name=False,
    )

    assert output == tmp_path / "hello.wav"


def test_resolve_decoded_output_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cypher, "OUTPUT_DIR", tmp_path)

    assert (
        cypher.resolve_decoded_output(None, "original.txt")
        == tmp_path / "original.txt"
    )


def test_resolve_bundle_output_dir_nested_output() -> None:
    assert (
        cypher.resolve_bundle_output_dir("nested/out")
        == Path("nested/out")
    )


def test_split_chunks_non_empty_single_chunk() -> None:
    assert cypher.split_chunks(b"abc", 10) == [b"abc"]


def test_encode_chunked_payload_no_crypto(monkeypatch) -> None:
    monkeypatch.setattr(
        cypher,
        "DEFAULT_PUBLIC_KEY_PATH",
        Path("definitely-missing-public.pem"),
    )

    payload, crypto_mode, public_key = cypher.encode_chunked_payload(
        payload=b"abc",
        compression_level=9,
        public_key=None,
    )

    assert payload
    assert crypto_mode == cypher.CRYPTO_MODE_NONE
    assert public_key is None


def test_decode_chunked_payload_rejects_missing_private_key_multi() -> None:
    chunk_header = cypher.ChunkHeader(
        index=1,
        total_chunks=1,
        raw_size=1,
        compressed_size=1,
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
        + (1).to_bytes(8, "big")
        + b"x"
    )

    with pytest.raises(ValueError, match="Private key path is required"):
        cypher.decode_chunked_payload(serialized, private_key=None)


def test_decode_command_single_file_logs_relative_path(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    payload = b"abc"

    header = cypher.create_header(
        input_path="x.txt",
        raw_size=len(payload),
        checksum=cypher.compute_checksum(payload),
        relative_path="folder/x.txt",
    )

    container = cypher.build_container(header, payload)

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
            output=str(tmp_path / "out.txt"),
            private_key=None,
        )
    )

    assert "Relative path" in capsys.readouterr().out


def test_bundle_command_multiple_inputs_common_root(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "root"
    root.mkdir()

    file_a = root / "a.txt"
    file_b = root / "b.txt"

    file_a.write_text("a")
    file_b.write_text("b")

    audio_dir = tmp_path / "audio"
    bundle_audio_dir = audio_dir / "bundle"
    waveform_dir = tmp_path / "waveforms"

    for directory in [audio_dir, bundle_audio_dir, waveform_dir]:
        directory.mkdir(parents=True)

    monkeypatch.setattr(cypher, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(cypher, "BUNDLE_AUDIO_DIR", bundle_audio_dir)
    monkeypatch.setattr(cypher, "WAVEFORM_DIR", waveform_dir)
    monkeypatch.setattr(
        cypher,
        "DEFAULT_PUBLIC_KEY_PATH",
        tmp_path / "missing_public.pem",
    )

    cypher.bundle_command(
        Namespace(
            files=[str(file_a), str(file_b)],
            name="multi",
            format="flac",
            keep_name=True,
            sample_rate=cypher.DEFAULT_SAMPLE_RATE,
            compression_level=9,
            public_key=None,
        )
    )

    assert (bundle_audio_dir / "multi.flac").exists()


def test_inspect_command_no_crypto_prints_public_fields(
    monkeypatch,
    capsys,
) -> None:
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
                "crypto_mode": cypher.CRYPTO_MODE_NONE,
                "public": {
                    "cypher_version": cypher.VERSION,
                    "payload_mode": cypher.PAYLOAD_MODE,
                    "original_name": "x.txt",
                    "mime_type": "text/plain",
                    "raw_size": "3",
                    "checksum": "abc",
                },
            },
            b"payload",
        ),
    )

    cypher.inspect_command(Namespace(file="payload.flac"))

    output = capsys.readouterr().out

    assert "Original name  : x.txt" in output
    assert "Checksum       : abc" in output
