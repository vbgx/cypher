from pathlib import Path

import pytest

import cypher.main as cypher


def test_resolve_input_file_prefers_existing_path(tmp_path) -> None:
    file_path = tmp_path / "direct.txt"
    file_path.write_text("direct")

    assert cypher.resolve_input_file(file_path) == file_path


def test_resolve_input_file_uses_input_dir(tmp_path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    file_path = input_dir / "inside.txt"
    file_path.write_text("inside")

    monkeypatch.setattr(cypher, "INPUT_DIR", input_dir)

    assert cypher.resolve_input_file("inside.txt") == file_path


def test_resolve_input_file_missing_raises(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(cypher, "INPUT_DIR", tmp_path)

    with pytest.raises(
        FileNotFoundError,
        match="Input file not found",
    ):
        cypher.resolve_input_file("missing.txt")


def test_resolve_input_audio_checks_audio_and_bundle_dirs(
    tmp_path,
    monkeypatch,
) -> None:
    audio_dir = tmp_path / "audio"
    bundle_dir = audio_dir / "bundle"

    audio_dir.mkdir()
    bundle_dir.mkdir()

    bundle_audio = bundle_dir / "payload.flac"
    bundle_audio.write_text("audio")

    monkeypatch.setattr(cypher, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(cypher, "BUNDLE_AUDIO_DIR", bundle_dir)

    assert (
        cypher.resolve_input_audio("payload.flac")
        == bundle_audio
    )


def test_resolve_input_audio_missing_raises(
    tmp_path,
    monkeypatch,
) -> None:
    audio_dir = tmp_path / "audio"
    bundle_dir = audio_dir / "bundle"

    audio_dir.mkdir()
    bundle_dir.mkdir()

    monkeypatch.setattr(cypher, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(cypher, "BUNDLE_AUDIO_DIR", bundle_dir)

    with pytest.raises(
        FileNotFoundError,
        match="Audio file not found",
    ):
        cypher.resolve_input_audio("missing.flac")


def test_read_file_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(
        FileNotFoundError,
        match="File not found",
    ):
        cypher.read_file(tmp_path / "missing.txt")


def test_read_file_rejects_directory(tmp_path) -> None:
    with pytest.raises(
        ValueError,
        match="Path is not a file",
    ):
        cypher.read_file(tmp_path)


def test_write_file_creates_parent_directories(
    tmp_path,
) -> None:
    output = tmp_path / "nested" / "file.bin"

    cypher.write_file(output, b"payload")

    assert output.read_bytes() == b"payload"


def test_resolve_decoded_output_with_nested_path() -> None:
    output = cypher.resolve_decoded_output(
        output_name="custom/out.txt",
        original_name="ignored.txt",
    )

    assert output == Path("custom/out.txt")


def test_resolve_bundle_output_dir_defaults() -> None:
    assert (
        cypher.resolve_bundle_output_dir(None)
        == cypher.OUTPUT_DIR / "bundle"
    )


def test_resolve_bundle_output_dir_uses_bundle_name() -> None:
    assert (
        cypher.resolve_bundle_output_dir(
            None,
            "project",
        )
        == cypher.OUTPUT_DIR / "project"
    )
