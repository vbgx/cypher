from pathlib import Path

import cypher.main as cypher


def test_checksum_roundtrip():
    payload = b"cypher test payload"

    checksum = cypher.compute_checksum(payload)

    assert cypher.verify_checksum(
        checksum,
        cypher.compute_checksum(payload),
    )


def test_safe_relative_path_normalizes():
    path = cypher.safe_relative_path(
        Path("../folder/../secret.txt")
    )

    assert isinstance(path, str)
    assert "secret.txt" in path
