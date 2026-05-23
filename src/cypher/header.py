import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cypher.config import (
    CHECKSUM_ALGORITHM,
    COLOR_MODE,
    HEADER_VERSION,
    MAGIC,
    PIXEL_MODE,
)


@dataclass(frozen=True)
class CypherHeader:
    width: int
    height: int
    pixel_duration: float
    sample_rate: int
    checksum: str
    magic: str = MAGIC
    version: int = HEADER_VERSION
    color_mode: str = COLOR_MODE
    pixel_mode: str = PIXEL_MODE
    checksum_algorithm: str = CHECKSUM_ALGORITHM


def create_header(
    width: int,
    height: int,
    pixel_duration: float,
    sample_rate: int,
    checksum: str,
) -> CypherHeader:
    header = CypherHeader(
        width=width,
        height=height,
        pixel_duration=pixel_duration,
        sample_rate=sample_rate,
        checksum=checksum,
    )

    validate_header(header)
    return header


def validate_header(header: CypherHeader) -> None:
    if header.magic != MAGIC:
        raise ValueError(f"Invalid magic: {header.magic}")

    if header.version != HEADER_VERSION:
        raise ValueError(f"Unsupported version: {header.version}")

    if header.width <= 0 or header.height <= 0:
        raise ValueError("Invalid image dimensions")

    if header.pixel_duration <= 0:
        raise ValueError("Invalid pixel duration")

    if header.sample_rate <= 0:
        raise ValueError("Invalid sample rate")

    if not header.checksum:
        raise ValueError("Checksum cannot be empty")


def metadata_path_for_audio(audio_path: str | Path) -> Path:
    path = Path(audio_path)
    return path.with_suffix(".json")


def save_header(header: CypherHeader, audio_path: str | Path) -> Path:
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


def get_pixel_count(header: CypherHeader) -> int:
    validate_header(header)
    return header.width * header.height
