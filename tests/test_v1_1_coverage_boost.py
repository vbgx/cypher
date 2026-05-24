from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pytest

import cypher.audio as audio
import cypher.bundle as bundle
import cypher.cli as cli
import cypher.container as container
import cypher.keys as keys
import cypher.main as cypher


def test_audio_parse_payload_rejects_truncated_payload() -> None:
    meta = b'{"crypto_mode":"none"}'
    payload = b"abc"

    raw = (
        audio.AUDIO_MAGIC
        + len(meta).to_bytes(8, "big")
        + (len(payload) + 10).to_bytes(8, "big")
        + meta
        + payload
    )

    with pytest.raises(ValueError, match="Invalid audio payload size"):
        audio.parse_audio_payload(raw)


def test_audio_waveform_rejects_empty_samples(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audio, "WAVEFORM_DIR", tmp_path)

    with pytest.raises(ValueError, match="empty audio"):
        audio.write_waveform_preview("x.flac", np.array([], dtype=np.int16))


def test_audio_read_audio_rejects_stereo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        audio.sf,
        "read",
        lambda *_args, **_kwargs: (np.zeros((2, 2), dtype=np.int16), 44100),
    )

    with pytest.raises(ValueError, match="must be mono"):
        audio.read_audio("x.flac")


def test_container_resolvers_raise_for_missing_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(container, "INPUT_DIR", tmp_path / "input")
    monkeypatch.setattr(container, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(container, "BUNDLE_AUDIO_DIR", tmp_path / "bundle")

    with pytest.raises(FileNotFoundError, match="Input file not found"):
        container.resolve_input_file("missing.txt")

    with pytest.raises(FileNotFoundError, match="Audio file not found"):
        container.resolve_input_audio("missing.flac")


def test_container_output_resolution_absolute_and_dedup(tmp_path: Path) -> None:
    absolute = tmp_path / "out.txt"
    assert container.resolve_decoded_output(str(absolute), "ignored.txt") == absolute

    existing = tmp_path / "file.txt"
    existing.write_text("x")

    assert container.unique_output_path(tmp_path, "file.txt") == tmp_path / "file_1.txt"


def test_container_resolve_bundle_output_dir_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cypher, "OUTPUT_DIR", tmp_path)

    assert cypher.resolve_bundle_output_dir(None, "case") == tmp_path / "case"
    assert cypher.resolve_bundle_output_dir("named", None) == tmp_path / "named"

    absolute = tmp_path / "absolute"
    assert cypher.resolve_bundle_output_dir(str(absolute), None) == absolute


def test_container_default_private_key_none_and_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cypher,
        "DEFAULT_PRIVATE_KEY_PATH",
        tmp_path / "missing.pem",
    )

    assert cypher.resolve_default_private_key(None) is None
    assert cypher.resolve_default_private_key("private.pem") == "private.pem"


def test_container_default_public_keys_explicit_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(container, "DEFAULT_PUBLIC_KEY_PATH", tmp_path / "public.pem")

    assert container.resolve_default_public_keys(None) == []
    assert container.resolve_default_public_keys(
    ["a.pem", "b.pem"]
) == ["a.pem", "b.pem"]


def test_bundle_parse_rejects_bad_magic() -> None:
    with pytest.raises(ValueError, match="Invalid cypher bundle magic"):
        bundle.parse_bundle_container(b"BAD")


def test_bundle_parse_rejects_trailing_bytes() -> None:
    header = bundle.BundleHeader(files_count=1)
    file_header = container.create_header(
        input_path="a.txt",
        raw_size=1,
        checksum=container.compute_checksum(b"x"),
    )

    payload = bundle.BUNDLE_MAGIC
    bundle_header_bytes = bundle.json.dumps(
        bundle.asdict(header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    file_header_bytes = container.encode_header(file_header)

    payload += len(bundle_header_bytes).to_bytes(8, "big")
    payload += bundle_header_bytes
    payload += len(file_header_bytes).to_bytes(8, "big")
    payload += file_header_bytes
    payload += (1).to_bytes(8, "big")
    payload += b"x"
    payload += b"extra"

    with pytest.raises(ValueError, match="Unexpected trailing bytes"):
        bundle.parse_bundle_container(payload)


def test_keys_generate_keypair_existing_rejects(tmp_path: Path) -> None:
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    private_key.write_text("x")
    public_key.write_text("y")

    with pytest.raises(FileExistsError, match="Key file already exists"):
        keys.generate_keypair(private_key, public_key, force=False)


def test_keys_keygen_command_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_generate_keypair(
        private_key_path: Path,
        public_key_path: Path,
        force: bool,
    ) -> None:
        calls.append((private_key_path, public_key_path, force))

    monkeypatch.setattr(keys, "generate_keypair", fake_generate_keypair)

    keys.keygen_command(
        argparse.Namespace(
            private_key="private.pem",
            public_key="public.pem",
            force=True,
        )
    )

    assert calls == [(Path("private.pem"), Path("public.pem"), True)]


def test_cli_main_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    called = []

    def fake_func(_args: argparse.Namespace) -> None:
        called.append(True)

    parser = cli.build_parser()
    args = parser.parse_args(["inspect", "payload.flac"])
    args.func = fake_func

    class FakeParser:
        def parse_args(self) -> argparse.Namespace:
            return args

    monkeypatch.setattr(cli, "build_parser", lambda: FakeParser())

    cli.main()

    assert called == [True]

