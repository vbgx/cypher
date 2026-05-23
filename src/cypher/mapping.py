import numpy as np

from cypher.config import (
    B_MAX_FREQ,
    B_MIN_FREQ,
    G_MAX_FREQ,
    G_MIN_FREQ,
    R_MAX_FREQ,
    R_MIN_FREQ,
)


RGBPixel = tuple[int, int, int]
RGBFrequencies = tuple[float, float, float]


def validate_channel(value: int) -> None:
    """
    Validate one RGB channel.
    """
    if value < 0 or value > 255:
        raise ValueError(f"RGB channel must be between 0 and 255, got {value}")


def validate_frequency_band(
    frequency: float,
    f_min: float,
    f_max: float,
) -> None:
    """
    Validate that a frequency belongs to a given band.
    """
    if frequency < f_min or frequency > f_max:
        raise ValueError(
            f"Frequency must be between {f_min} Hz and {f_max} Hz, "
            f"got {frequency} Hz"
        )


def channel_to_frequency(
    value: int,
    f_min: float,
    f_max: float,
) -> float:
    """
    Convert one RGB channel value to frequency.
    """
    validate_channel(value)

    return f_min + (value / 255) * (f_max - f_min)


def frequency_to_channel(
    frequency: float,
    f_min: float,
    f_max: float,
) -> int:
    """
    Convert frequency back to RGB channel value.
    """
    validate_frequency_band(
        frequency,
        f_min,
        f_max,
    )

    normalized = (frequency - f_min) / (f_max - f_min)

    value = round(normalized * 255)

    return int(np.clip(value, 0, 255))


def pixel_to_frequencies(pixel: RGBPixel) -> RGBFrequencies:
    """
    Convert RGB pixel to three frequencies.
    """
    r, g, b = pixel

    return (
        channel_to_frequency(r, R_MIN_FREQ, R_MAX_FREQ),
        channel_to_frequency(g, G_MIN_FREQ, G_MAX_FREQ),
        channel_to_frequency(b, B_MIN_FREQ, B_MAX_FREQ),
    )


def frequencies_to_pixel(frequencies: RGBFrequencies) -> RGBPixel:
    """
    Convert three frequencies back to an RGB pixel.
    """
    r_freq, g_freq, b_freq = frequencies

    return (
        frequency_to_channel(r_freq, R_MIN_FREQ, R_MAX_FREQ),
        frequency_to_channel(g_freq, G_MIN_FREQ, G_MAX_FREQ),
        frequency_to_channel(b_freq, B_MIN_FREQ, B_MAX_FREQ),
    )


def pixels_to_frequencies(
    pixels: list[RGBPixel],
) -> list[RGBFrequencies]:
    """
    Convert RGB pixel stream to RGB frequency stream.
    """
    return [
        pixel_to_frequencies(pixel)
        for pixel in pixels
    ]


def frequencies_to_pixels(
    frequencies: list[RGBFrequencies],
) -> list[RGBPixel]:
    """
    Convert RGB frequency stream to RGB pixel stream.
    """
    return [
        frequencies_to_pixel(item)
        for item in frequencies
    ]


def main() -> None:
    """
    Simple manual test.
    """
    pixel: RGBPixel = (255, 128, 0)

    frequencies = pixel_to_frequencies(pixel)
    restored = frequencies_to_pixel(frequencies)

    print(f"Pixel      : {pixel}")
    print(f"Frequencies: {frequencies}")
    print(f"Restored   : {restored}")


if __name__ == "__main__":
    main()
