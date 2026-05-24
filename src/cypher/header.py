import json
import mimetypes
from dataclasses import asdict, dataclass
from pathlib import Path

from cypher.config import (
    CHECKSUM_ALGORITHM,
    COMPRESSION_ALGORITHM,
    HEADER_VERSION,
    MAGIC,
    PAYLOAD_MODE,
)


@dataclass(frozen=True)
class CypherHeader:
    original_name: str
    original_suffix: str
    mime_type: str
    sample_rate: int
    raw_size: int
    compressed_size: int
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
    sample_rate: int,
    raw_size: int,
    compressed_size: int,
    checksum: str,
) -> CypherHeader:
    path = Path(input_path)

    header = CypherHeader(
        original_name=path.name,
        original_suffix=path.suffix,
        mime_type=detect_mime_type(path),
        sample_rate=sample_rate,
        raw_size=raw_size,
        compressed_size=compressed_size,
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

    if header.sample_rate <= 0:
        raise ValueError("Invalid sample rate")

    if header.raw_size < 0:
        raise ValueError("Invalid raw size")

    if header.compressed_size <= 0:
        raise ValueError("Invalid compressed size")

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


def metadata_path_for_audio(audio_path: str | Path) -> Path:
    return Path(audio_path).with_suffix(".json")


def save_header(
    header: CypherHeader,
    audio_path: str | Path,
) -> Path:
    validate_header(header)

    metadata_path = metadata_path_for_audio(audio_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_path.write_text(
        json.dumps(asdict(header), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return metadata_path


def load_header(audio_path: str | Path) -> CypherHeader:
    metadata_path = metadata_path_for_audio(audio_path)

    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    data = json.loads(metadata_path.read_text(encoding="utf-8"))

    header = CypherHeader(**data)
    validate_header(header)

    return header
