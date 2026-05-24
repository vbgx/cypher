import pytest

import cypher.main as cypher


def test_build_bundle_requires_at_least_one_file() -> None:
    with pytest.raises(ValueError, match="Bundle requires at least one file"):
        cypher.build_bundle_container([])


def test_bundle_container_roundtrip_two_files() -> None:
    first_payload = b"alpha"
    second_payload = b"beta"

    first_header = cypher.create_header(
        input_path="alpha.txt",
        raw_size=len(first_payload),
        checksum=cypher.compute_checksum(first_payload),
        relative_path="docs/alpha.txt",
    )

    second_header = cypher.create_header(
        input_path="beta.txt",
        raw_size=len(second_payload),
        checksum=cypher.compute_checksum(second_payload),
        relative_path="docs/beta.txt",
    )

    bundle = cypher.build_bundle_container(
        [
            (first_header, first_payload),
            (second_header, second_payload),
        ]
    )

    restored = cypher.parse_bundle_container(bundle)

    assert restored == [
        (first_header, first_payload),
        (second_header, second_payload),
    ]


def test_parse_bundle_rejects_bad_magic() -> None:
    with pytest.raises(ValueError, match="Invalid cypher bundle magic"):
        cypher.parse_bundle_container(b"bad")


def test_build_bundle_rejects_checksum_mismatch() -> None:
    payload = b"real"

    header = cypher.create_header(
        input_path="payload.txt",
        raw_size=len(payload),
        checksum="wrong-checksum",
    )

    with pytest.raises(ValueError, match="Checksum mismatch before bundling"):
        cypher.build_bundle_container([(header, payload)])
