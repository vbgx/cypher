from pathlib import Path
from typing import Iterator

from PIL import Image

from cypher.config import SUPPORTED_INPUT_IMAGES


RGBPixel = tuple[int, int, int]


def validate_image_path(path: str | Path) -> Path:
    """
    Validate input image path and extension.
    """
    image_path = Path(path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    if not image_path.is_file():
        raise ValueError(f"Image path is not a file: {image_path}")

    if image_path.suffix.lower() not in SUPPORTED_INPUT_IMAGES:
        raise ValueError(
            f"Unsupported image format: {image_path.suffix}. "
            f"Supported formats: {sorted(SUPPORTED_INPUT_IMAGES)}"
        )

    return image_path


def load_image(path: str | Path) -> Image.Image:
    """
    Load an image and convert it to RGB mode.
    """
    image_path = validate_image_path(path)

    with Image.open(image_path) as image:
        return image.convert("RGB")


def get_dimensions(image: Image.Image) -> tuple[int, int]:
    """
    Return image dimensions as (width, height).
    """
    return image.size


def iter_pixels(image: Image.Image) -> Iterator[RGBPixel]:
    """
    Iterate pixels row by row.

    Order:
        (0,0), (1,0), ..., (width-1,0)
        (0,1), (1,1), ..., (width-1,1)
        ...
    """
    width, height = image.size
    pixel_access = image.load()

    for y in range(height):
        for x in range(width):
            r, g, b = pixel_access[x, y]
            yield (int(r), int(g), int(b))


def read_image(path: str | Path) -> tuple[int, int, list[RGBPixel]]:
    """
    Read image dimensions and deterministic RGB pixel stream.

    Returns:
        width,
        height,
        pixels
    """
    image = load_image(path)

    width, height = get_dimensions(image)
    pixels = list(iter_pixels(image))

    expected_pixels = width * height

    if len(pixels) != expected_pixels:
        raise ValueError(
            f"Invalid pixel count: expected {expected_pixels}, got {len(pixels)}"
        )

    return width, height, pixels


def main() -> None:
    """
    Simple manual test.
    """
    width, height, pixels = read_image("data/input/example.png")

    print(f"Width : {width}")
    print(f"Height: {height}")
    print(f"Pixels: {len(pixels)}")
    print("First 10 pixels:")

    for pixel in pixels[:10]:
        print(pixel)


if __name__ == "__main__":
    main()
