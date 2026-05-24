import pytest

import cypher.main as cypher


def test_decode_chunked_payload_requires_private_key_for_encrypted_chunk() -> None:
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
        {"crypto_mode": cypher.CRYPTO_MODE_X25519_AESGCM},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    payload = (
        len(header_bytes).to_bytes(8, "big")
        + header_bytes
        + len(crypto_bytes).to_bytes(8, "big")
        + crypto_bytes
        + (1).to_bytes(8, "big")
        + b"x"
    )

    with pytest.raises(ValueError, match="Private key path is required"):
        cypher.decode_chunked_payload(payload, private_key=None)


def test_decompress_container_rejects_invalid_zlib_payload() -> None:
    with pytest.raises(cypher.zlib.error):
        cypher.decompress_container(b"not zlib")


def test_parse_audio_payload_rejects_truncated_payload() -> None:
    meta = b'{"crypto_mode":"none"}'
    payload = b"abc"

    audio_payload = (
        cypher.AUDIO_MAGIC
        + len(meta).to_bytes(8, "big")
        + (len(payload) + 10).to_bytes(8, "big")
        + meta
        + payload
    )

    with pytest.raises(ValueError, match="Invalid audio payload size"):
        cypher.parse_audio_payload(audio_payload)
