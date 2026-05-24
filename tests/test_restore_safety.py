from pathlib import Path

import cypher.main as cypher


def test_unique_output_path_returns_original_when_free(tmp_path) -> None:
    candidate = cypher.unique_output_path(tmp_path, "file.txt")

    assert candidate == tmp_path / "file.txt"


def test_unique_output_path_deduplicates_existing_file(tmp_path) -> None:
    existing = tmp_path / "file.txt"
    existing.write_text("first")

    candidate = cypher.unique_output_path(tmp_path, "file.txt")

    assert candidate == tmp_path / "file_1.txt"


def test_restore_bundle_deduplicates_existing_outputs(tmp_path) -> None:
    output_dir = tmp_path / "restored"
    output_dir.mkdir()
    (output_dir / "file.txt").write_text("existing")

    payload = b"new content"

    header = cypher.create_header(
        input_path="file.txt",
        raw_size=len(payload),
        checksum=cypher.compute_checksum(payload),
        relative_path="file.txt",
    )

    bundle = cypher.build_bundle_container([(header, payload)])

    cypher.restore_bundle_payload(
        audio_path=Path("payload.flac"),
        restored_payload=bundle,
        bundle_checksum=cypher.compute_checksum(bundle),
        output_dir=output_dir,
    )

    assert (output_dir / "file.txt").read_text() == "existing"
    assert (output_dir / "file_1.txt").read_bytes() == payload
