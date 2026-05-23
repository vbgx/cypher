from pathlib import Path

from PIL import Image


RGBPixel = tuple[int, int, int]


def validate_dimensions(
    width: int,
    height: int,
) -> None:
    """
    Validate image dimensions.
    """
    if width <= 0:
        raise ValueError("Image width must be greater than 0")

    if height <= 0:
        raise ValueError("Image height must be greater than 0")


def validate_pixel(pixel: RGBPixel) -> None:
    """
    Validate one RGB pixel.
    """
    if len(pixel) != 3:
        raise ValueError(f"RGB pixel must contain 3 values, got {len(pixel)}")

    for channel in pixel:
        if channel < 0 or channel > 255:
            raise ValueError(
                f"RGB channel must be between 0 and 255, got {channel}"
            )


def validate_pixels(
    pixels: list[RGBPixel],
    width: int,
    height: int,
) -> None:
    """
    Validate pixel stream length and channel values.
    """
    expected_pixels = width * height

    if len(pixels) != expected_pixels:
        raise ValueError(
            f"Invalid pixel count: expected {expected_pixels}, got {len(pixels)}"
        )

    for pixel in pixels:
        validate_pixel(pixel)


def build_image(
    width: int,
    height: int,
    pixels: list[RGBPixel],
) -> Image.Image:
    """
    Build RGB image from deterministic pixel stream.
    """
    validate_dimensions(width, height)
    validate_pixels(pixels, width, height)

    image = Image.new(
        "RGB",
        (width, height),
    )

    image.putdata(pixels)

    return image


def write_image(
    path: str | Path,
    width: int,
    height: int,
    pixels: list[RGBPixel],
) -> None:
    """
    Write RGB pixel stream to an image file.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image = build_image(
        width=width,
        height=height,
        pixels=pixels,
    )

    image.save(output_path)


def main() -> None:
    """
    Simple manual test.
    """
    width = 2
    height = 2

    pixels: list[RGBPixel] = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 255),
    ]

    write_image(
        "data/output/example.png",
        width,
        height,
        pixels,
    )

    print("Wrote data/output/example.png")


if __name__ == "__main__":
    main()
