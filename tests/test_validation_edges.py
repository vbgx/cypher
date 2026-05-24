import pytest

import cypher.main as cypher


def test_validate_header_rejects_bad_magic() -> None:
    header = cypher.CypherHeader(
        original_name="x.txt",
        original_suffix=".txt",
        mime_type="text/plain",
        raw_size=1,
        checksum="abc",
        magic="BAD",
    )

    with pytest.raises(ValueError, match="Invalid magic"):
        cypher.validate_header(header)


def test_validate_header_rejects_negative_size() -> None:
    header = cypher.CypherHeader(
        original_name="x.txt",
        original_suffix=".txt",
        mime_type="text/plain",
        raw_size=-1,
        checksum="abc",
    )

    with pytest.raises(ValueError, match="Invalid raw size"):
        cypher.validate_header(header)


def test_validate_bundle_header_rejects_empty_bundle() -> None:
    header = cypher.BundleHeader(files_count=0)

    with pytest.raises(ValueError, match="at least one file"):
        cypher.validate_bundle_header(header)


def test_verify_checksum_is_case_insensitive() -> None:
    assert cypher.verify_checksum("ABCDEF", "abcdef")
