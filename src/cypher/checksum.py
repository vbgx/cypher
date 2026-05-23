from hashlib import sha256
from pathlib import Path


def compute_bytes_checksum(data: bytes) -> str:
    """
    Compute SHA256 checksum from raw bytes.
    """
    return sha256(data).hexdigest()


def compute_text_checksum(text: str) -> str:
    """
    Compute SHA256 checksum from UTF-8 text.
    """
    return compute_bytes_checksum(
        text.encode("utf-8")
    )


def compute_file_checksum(path: str | Path) -> str:
    """
    Compute SHA256 checksum for a file.
    """
    file_path = Path(path)

    hasher = sha256()

    with file_path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(8192),
            b"",
        ):
            hasher.update(chunk)

    return hasher.hexdigest()


def compute_pixel_checksum(
    pixels: list[tuple[int, int, int]],
) -> str:
    """
    Compute deterministic checksum for RGB pixel stream.
    """
    serialized = bytearray()

    for r, g, b in pixels:
        serialized.extend([r, g, b])

    return compute_bytes_checksum(
        bytes(serialized)
    )


def verify_checksum(
    expected: str,
    actual: str,
) -> bool:
    """
    Verify checksum equality.
    """
    return expected.lower() == actual.lower()


def main() -> None:
    """
    Simple manual test.
    """
    text_hash = compute_text_checksum(
        "cypher"
    )

    print("Text checksum:")
    print(text_hash)

    pixels = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
    ]

    pixel_hash = compute_pixel_checksum(
        pixels
    )

    print("\nPixel checksum:")
    print(pixel_hash)


if __name__ == "__main__":
    main()
