from dataclasses import dataclass

from cypher.config import (
    CHECKSUM_ALGORITHM,
    COLOR_MODE,
    HEADER_VERSION,
    MAGIC,
    PIXEL_MODE,
)


HEADER_SEPARATOR = "|"


@dataclass(frozen=True)
class CypherHeader:
    """
    Metadata required to decode a cypher audio stream.
    """

    width: int
    height: int
    pixel_duration: float
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
    checksum: str,
) -> CypherHeader:
    """
    Create and validate a cypher header.
    """
    header = CypherHeader(
        width=width,
        height=height,
        pixel_duration=pixel_duration,
        checksum=checksum,
    )

    validate_header(header)

    return header


def validate_header(header: CypherHeader) -> None:
    """
    Validate header consistency.
    """
    if header.magic != MAGIC:
        raise ValueError(f"Invalid magic value: {header.magic}")

    if header.version != HEADER_VERSION:
        raise ValueError(f"Unsupported header version: {header.version}")

    if header.width <= 0:
        raise ValueError("Header width must be greater than 0")

    if header.height <= 0:
        raise ValueError("Header height must be greater than 0")

    if header.pixel_duration <= 0:
        raise ValueError("Pixel duration must be greater than 0")

    if header.color_mode != COLOR_MODE:
        raise ValueError(f"Unsupported color mode: {header.color_mode}")

    if header.pixel_mode != PIXEL_MODE:
        raise ValueError(f"Unsupported pixel mode: {header.pixel_mode}")

    if header.checksum_algorithm != CHECKSUM_ALGORITHM:
        raise ValueError(
            f"Unsupported checksum algorithm: {header.checksum_algorithm}"
        )

    if not header.checksum:
        raise ValueError("Checksum cannot be empty")


def serialize_header(header: CypherHeader) -> str:
    """
    Serialize header to a deterministic string.
    """
    validate_header(header)

    return HEADER_SEPARATOR.join(
        [
            header.magic,
            str(header.version),
            str(header.width),
            str(header.height),
            header.color_mode,
            header.pixel_mode,
            format(header.pixel_duration, ".10g"),
            header.checksum_algorithm,
            header.checksum,
        ]
    )


def deserialize_header(raw: str) -> CypherHeader:
    """
    Deserialize a header string into a CypherHeader.
    """
    parts = raw.strip().split(HEADER_SEPARATOR)

    if len(parts) != 9:
        raise ValueError(
            f"Invalid header field count: expected 9, got {len(parts)}"
        )

    (
        magic,
        version_raw,
        width_raw,
        height_raw,
        color_mode,
        pixel_mode,
        pixel_duration_raw,
        checksum_algorithm,
        checksum,
    ) = parts

    header = CypherHeader(
        magic=magic,
        version=int(version_raw),
        width=int(width_raw),
        height=int(height_raw),
        color_mode=color_mode,
        pixel_mode=pixel_mode,
        pixel_duration=float(pixel_duration_raw),
        checksum_algorithm=checksum_algorithm,
        checksum=checksum,
    )

    validate_header(header)

    return header


def get_pixel_count(header: CypherHeader) -> int:
    """
    Return expected number of pixels from header dimensions.
    """
    validate_header(header)

    return header.width * header.height


def main() -> None:
    """
    Simple manual test.
    """
    header = create_header(
        width=100,
        height=100,
        pixel_duration=0.01,
        checksum="abc123",
    )

    serialized = serialize_header(header)

    print(serialized)

    restored = deserialize_header(serialized)

    print(restored)
    print(f"Pixel count: {get_pixel_count(restored)}")


if __name__ == "__main__":
    main()
