import json
import mimetypes
from dataclasses import asdict, dataclass
from pathlib import Path

from cypher.config import (
    CHECKSUM_ALGORITHM,
    COMPRESSION_ALGORITHM,
    CONTAINER_MAGIC,
    HEADER_VERSION,
    MAGIC,
    PAYLOAD_MODE,
)


@dataclass(frozen=True)
class CypherHeader:
    original_name: str
    original_suffix: str
    mime_type: str
    raw_size: int
    checksum: str
    magic: str = MAGIC
    version: int = HEADER_VERSION
    payload_mode: str = PAYLOAD_MODE
    checksum_algorithm: str = CHECKSUM_ALGORITHM
    compression_algorithm: str = COMPRESSION_ALGORITHM


def detect_mime_type(path: str | Path) -> str:
    mime_type, _encoding = mimetypes.guess_type(Path(path).name)
    return mime_type or "application/octet-stream"


def create_header(
    input_path: str | Path,
    raw_size: int,
    checksum: str,
) -> CypherHeader:
    path = Path(input_path)

    header = CypherHeader(
        original_name=path.name,
        original_suffix=path.suffix,
        mime_type=detect_mime_type(path),
        raw_size=raw_size,
        checksum=checksum,
    )

    validate_header(header)

    return header


def validate_header(header: CypherHeader) -> None:
    if header.magic != MAGIC:
        raise ValueError(f"Invalid magic: {header.magic}")

    if header.version != HEADER_VERSION:
        raise ValueError(f"Unsupported version: {header.version}")

    if header.payload_mode != PAYLOAD_MODE:
        raise ValueError(f"Unsupported payload mode: {header.payload_mode}")

    if header.raw_size < 0:
        raise ValueError("Invalid raw size")

    if not header.original_name:
        raise ValueError("Original filename cannot be empty")

    if not header.checksum:
        raise ValueError("Checksum cannot be empty")

    if header.checksum_algorithm != CHECKSUM_ALGORITHM:
        raise ValueError(
            f"Unsupported checksum algorithm: {header.checksum_algorithm}"
        )

    if header.compression_algorithm != COMPRESSION_ALGORITHM:
        raise ValueError(
            f"Unsupported compression algorithm: {header.compression_algorithm}"
        )


def encode_header(header: CypherHeader) -> bytes:
    validate_header(header)

    return json.dumps(
        asdict(header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_header(payload: bytes) -> CypherHeader:
    data = json.loads(payload.decode("utf-8"))

    header = CypherHeader(**data)

    validate_header(header)

    return header


def build_container(
    header: CypherHeader,
    payload: bytes,
) -> bytes:
    header_bytes = encode_header(header)
    header_size = len(header_bytes).to_bytes(8, byteorder="big")

    return CONTAINER_MAGIC + header_size + header_bytes + payload


def parse_container(container: bytes) -> tuple[CypherHeader, bytes]:
    magic_size = len(CONTAINER_MAGIC)

    if container[:magic_size] != CONTAINER_MAGIC:
        raise ValueError("Invalid cypher container magic")

    header_size_start = magic_size
    header_size_end = header_size_start + 8

    header_size = int.from_bytes(
        container[header_size_start:header_size_end],
        byteorder="big",
    )

    header_start = header_size_end
    header_end = header_start + header_size

    header = decode_header(container[header_start:header_end])
    payload = container[header_end:]

    if len(payload) != header.raw_size:
        raise ValueError(
            f"Invalid payload size: expected {header.raw_size}, got {len(payload)}"
        )

    return header, payload
