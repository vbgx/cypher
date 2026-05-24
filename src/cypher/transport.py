from __future__ import annotations

import json
import zlib
from dataclasses import asdict, dataclass

TRANSPORT_MAGIC = b"CYPHERTRANSPORT14"
TRANSPORT_VERSION = 1
TRANSPORT_MODE_REDUNDANT = "redundant-crc32"
DEFAULT_FRAME_SIZE = 64 * 1024
DEFAULT_REDUNDANCY = 3


@dataclass(frozen=True)
class TransportHeader:
    magic: str
    version: int
    mode: str
    original_size: int
    original_crc32: int
    frame_size: int
    frame_count: int
    redundancy: int


@dataclass(frozen=True)
class FrameHeader:
    index: int
    copy: int
    size: int
    crc32: int


def compute_crc32(payload: bytes) -> int:
    return zlib.crc32(payload) & 0xFFFFFFFF


def has_transport_envelope(payload: bytes) -> bool:
    return payload.startswith(TRANSPORT_MAGIC)


def split_frames(payload: bytes, frame_size: int) -> list[bytes]:
    if frame_size <= 0:
        raise ValueError("Frame size must be positive")

    return [
        payload[index : index + frame_size]
        for index in range(0, len(payload), frame_size)
    ] or [b""]


def encode_transport_payload(
    payload: bytes,
    redundancy: int = DEFAULT_REDUNDANCY,
    frame_size: int = DEFAULT_FRAME_SIZE,
) -> bytes:
    if redundancy < 1:
        raise ValueError("Redundancy must be at least 1")

    frames = split_frames(payload, frame_size)

    header = TransportHeader(
        magic="CYPHER_TRANSPORT",
        version=TRANSPORT_VERSION,
        mode=TRANSPORT_MODE_REDUNDANT,
        original_size=len(payload),
        original_crc32=compute_crc32(payload),
        frame_size=frame_size,
        frame_count=len(frames),
        redundancy=redundancy,
    )

    header_bytes = json.dumps(
        asdict(header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    output = TRANSPORT_MAGIC
    output += len(header_bytes).to_bytes(8, "big")
    output += header_bytes

    for index, frame in enumerate(frames):
        frame_crc = compute_crc32(frame)

        for copy in range(redundancy):
            frame_header = FrameHeader(
                index=index,
                copy=copy,
                size=len(frame),
                crc32=frame_crc,
            )

            frame_header_bytes = json.dumps(
                asdict(frame_header),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")

            output += len(frame_header_bytes).to_bytes(8, "big")
            output += frame_header_bytes
            output += len(frame).to_bytes(8, "big")
            output += frame

    return output


def decode_transport_payload(
    payload: bytes,
    allow_partial: bool = False,
) -> bytes:
    if not has_transport_envelope(payload):
        return payload

    cursor = len(TRANSPORT_MAGIC)

    if cursor + 8 > len(payload):
        raise ValueError("Truncated transport header size")

    header_size = int.from_bytes(payload[cursor : cursor + 8], "big")
    cursor += 8

    if cursor + header_size > len(payload):
        raise ValueError("Truncated transport header")

    header = TransportHeader(
        **json.loads(payload[cursor : cursor + header_size].decode("utf-8"))
    )
    cursor += header_size

    validate_transport_header(header)

    recovered: dict[int, bytes] = {}
    invalid_frames = 0

    while cursor < len(payload):
        if cursor + 8 > len(payload):
            invalid_frames += 1
            break

        frame_header_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        if cursor + frame_header_size > len(payload):
            invalid_frames += 1
            break

        try:
            frame_header = FrameHeader(
                **json.loads(
                    payload[cursor : cursor + frame_header_size].decode("utf-8")
                )
            )
        except Exception:
            invalid_frames += 1
            break

        cursor += frame_header_size

        if cursor + 8 > len(payload):
            invalid_frames += 1
            break

        frame_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        if cursor + frame_size > len(payload):
            invalid_frames += 1
            break

        frame = payload[cursor : cursor + frame_size]
        cursor += frame_size

        if frame_header.index < 0 or frame_header.index >= header.frame_count:
            invalid_frames += 1
            continue

        if frame_header.size != len(frame):
            invalid_frames += 1
            continue

        if compute_crc32(frame) != frame_header.crc32:
            invalid_frames += 1
            continue

        recovered.setdefault(frame_header.index, frame)

    missing = [
        index
        for index in range(header.frame_count)
        if index not in recovered
    ]

    if missing and not allow_partial:
        raise ValueError(
            "Unable to recover transport payload. "
            f"Missing frame indexes: {missing}"
        )

    rebuilt = b"".join(
        recovered[index]
        for index in range(header.frame_count)
        if index in recovered
    )

    if not allow_partial:
        if len(rebuilt) != header.original_size:
            raise ValueError(
                "Recovered transport payload size mismatch: "
                f"expected {header.original_size}, got {len(rebuilt)}"
            )

        if compute_crc32(rebuilt) != header.original_crc32:
            raise ValueError("Recovered transport payload CRC mismatch")

    if invalid_frames:
        print(
            "Transport recovery: "
            f"ignored {invalid_frames} corrupted frame(s)."
        )

    return rebuilt


def validate_transport_header(header: TransportHeader) -> None:
    if header.magic != "CYPHER_TRANSPORT":
        raise ValueError(f"Invalid transport magic: {header.magic}")

    if header.version != TRANSPORT_VERSION:
        raise ValueError(f"Unsupported transport version: {header.version}")

    if header.mode != TRANSPORT_MODE_REDUNDANT:
        raise ValueError(f"Unsupported transport mode: {header.mode}")

    if header.original_size < 0:
        raise ValueError("Invalid transport original size")

    if header.frame_size <= 0:
        raise ValueError("Invalid transport frame size")

    if header.frame_count < 1:
        raise ValueError("Transport payload must contain at least one frame")

    if header.redundancy < 1:
        raise ValueError("Transport redundancy must be at least 1")
