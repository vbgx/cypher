from pathlib import Path

import numpy as np
from scipy.io import wavfile


RGBPixel = tuple[int, int, int]

R_MIN = 300.0
R_MAX = 1000.0

G_MIN = 1200.0
G_MAX = 1900.0

B_MIN = 2100.0
B_MAX = 2800.0

DEFAULT_SAMPLE_RATE = 44_100
DEFAULT_PIXEL_DURATION = 0.01
DEFAULT_AMPLITUDE = 0.3


def channel_to_freq(
    value: int,
    f_min: float,
    f_max: float,
) -> float:
    """
    Convert RGB channel value to frequency.
    """
    if value < 0 or value > 255:
        raise ValueError(f"RGB channel must be between 0 and 255, got {value}")

    return f_min + (value / 255) * (f_max - f_min)


def pixel_to_frequencies(pixel: RGBPixel) -> tuple[float, float, float]:
    """
    Convert RGB pixel to three frequencies.
    """
    r, g, b = pixel

    return (
        channel_to_freq(r, R_MIN, R_MAX),
        channel_to_freq(g, G_MIN, G_MAX),
        channel_to_freq(b, B_MIN, B_MAX),
    )


def generate_sine(
    frequency: float,
    duration: float,
    sample_rate: int,
    amplitude: float,
) -> np.ndarray:
    """
    Generate one sine wave.
    """
    sample_count = int(sample_rate * duration)

    t = np.linspace(
        0,
        duration,
        sample_count,
        endpoint=False,
    )

    return amplitude * np.sin(2 * np.pi * frequency * t)


def generate_pixel_frame(
    pixel: RGBPixel,
    duration: float,
    sample_rate: int,
    amplitude: float,
) -> np.ndarray:
    """
    Generate one audio frame for one RGB pixel.

    A pixel is encoded as three simultaneous frequencies:
    R band + G band + B band.
    """
    r_freq, g_freq, b_freq = pixel_to_frequencies(pixel)

    r_wave = generate_sine(
        r_freq,
        duration,
        sample_rate,
        amplitude,
    )

    g_wave = generate_sine(
        g_freq,
        duration,
        sample_rate,
        amplitude,
    )

    b_wave = generate_sine(
        b_freq,
        duration,
        sample_rate,
        amplitude,
    )

    frame = r_wave + g_wave + b_wave

    peak = np.max(np.abs(frame))

    if peak > 0:
        frame = frame / peak * amplitude

    return frame.astype(np.float32)


def encode_pixels(
    pixels: list[RGBPixel],
    pixel_duration: float = DEFAULT_PIXEL_DURATION,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    amplitude: float = DEFAULT_AMPLITUDE,
) -> np.ndarray:
    """
    Encode RGB pixels into a mono audio signal.
    """
    frames = [
        generate_pixel_frame(
            pixel,
            pixel_duration,
            sample_rate,
            amplitude,
        )
        for pixel in pixels
    ]

    if not frames:
        return np.array([], dtype=np.float32)

    return np.concatenate(frames).astype(np.float32)


def save_wav(
    path: str | Path,
    samples: np.ndarray,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    """
    Save audio samples as WAV PCM 16-bit.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    clipped = np.clip(samples, -1.0, 1.0)

    pcm = (clipped * 32767).astype(np.int16)

    wavfile.write(
        output_path,
        sample_rate,
        pcm,
    )


def encode_audio(
    pixels: list[RGBPixel],
    output_path: str | Path,
    pixel_duration: float = DEFAULT_PIXEL_DURATION,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    amplitude: float = DEFAULT_AMPLITUDE,
) -> None:
    """
    Encode RGB pixels and write WAV file.
    """
    samples = encode_pixels(
        pixels,
        pixel_duration=pixel_duration,
        sample_rate=sample_rate,
        amplitude=amplitude,
    )

    save_wav(
        output_path,
        samples,
        sample_rate=sample_rate,
    )


def main() -> None:
    """
    Simple manual test.
    """
    pixels: list[RGBPixel] = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 255),
        (0, 0, 0),
    ]

    encode_audio(
        pixels,
        "data/audio/example.wav",
        pixel_duration=0.25,
    )

    print("Wrote data/audio/example.wav")


if __name__ == "__main__":
    main()
