from pathlib import Path

import numpy as np
from scipy.io import wavfile

RGBPixel = tuple[int, int, int]

DEFAULT_SAMPLE_RATE = 44_100
DEFAULT_PIXEL_DURATION = 0.01
DEFAULT_AMPLITUDE = 0.25

R_FREQ = 500.0
G_FREQ = 1500.0
B_FREQ = 2500.0


def generate_sine(frequency: float, duration: float, sample_rate: int) -> np.ndarray:
    n = int(sample_rate * duration)
    t = np.arange(n) / sample_rate
    return np.sin(2 * np.pi * frequency * t)


def generate_pixel_frame(
    pixel: RGBPixel,
    duration: float,
    sample_rate: int,
    amplitude: float,
) -> np.ndarray:
    r, g, b = pixel

    r_amp = amplitude * (r / 255)
    g_amp = amplitude * (g / 255)
    b_amp = amplitude * (b / 255)

    frame = (
        r_amp * generate_sine(R_FREQ, duration, sample_rate)
        + g_amp * generate_sine(G_FREQ, duration, sample_rate)
        + b_amp * generate_sine(B_FREQ, duration, sample_rate)
    )

    return frame.astype(np.float32)


def encode_pixels(
    pixels: list[RGBPixel],
    pixel_duration: float = DEFAULT_PIXEL_DURATION,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    amplitude: float = DEFAULT_AMPLITUDE,
) -> np.ndarray:
    frames = [
        generate_pixel_frame(pixel, pixel_duration, sample_rate, amplitude)
        for pixel in pixels
    ]

    if not frames:
        return np.array([], dtype=np.float32)

    return np.concatenate(frames).astype(np.float32)


def save_wav(path: str | Path, samples: np.ndarray, sample_rate: int) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)

    wavfile.write(output_path, sample_rate, pcm)


def encode_audio(
    pixels: list[RGBPixel],
    output_path: str | Path,
    pixel_duration: float = DEFAULT_PIXEL_DURATION,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    amplitude: float = DEFAULT_AMPLITUDE,
) -> None:
    samples = encode_pixels(
        pixels=pixels,
        pixel_duration=pixel_duration,
        sample_rate=sample_rate,
        amplitude=amplitude,
    )

    save_wav(output_path, samples, sample_rate)
