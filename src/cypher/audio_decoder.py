from pathlib import Path

import numpy as np
import soundfile as sf

from cypher.config import (
    B_FREQ,
    DEFAULT_AMPLITUDE,
    G_FREQ,
    R_FREQ,
)

RGBPixel = tuple[int, int, int]


def load_audio(path: str | Path) -> tuple[int, np.ndarray]:
    data, sample_rate = sf.read(path)

    if data.ndim > 1:
        data = data.mean(axis=1)

    return sample_rate, data.astype(np.float32)


def split_frames(
    samples: np.ndarray,
    sample_rate: int,
    pixel_duration: float,
) -> list[np.ndarray]:
    frame_size = int(sample_rate * pixel_duration)

    return [
        samples[start : start + frame_size]
        for start in range(0, len(samples), frame_size)
        if len(samples[start : start + frame_size]) == frame_size
    ]


def magnitude_at_frequency(
    frame: np.ndarray,
    sample_rate: int,
    frequency: float,
) -> float:
    fft = np.fft.rfft(frame)
    freqs = np.fft.rfftfreq(len(frame), d=1 / sample_rate)
    index = int(np.argmin(np.abs(freqs - frequency)))
    return float(np.abs(fft[index]))


def magnitude_to_channel(
    magnitude: float,
    frame_size: int,
    amplitude: float = DEFAULT_AMPLITUDE,
) -> int:
    expected_max = frame_size * amplitude / 2
    value = round((magnitude / expected_max) * 255)
    return int(np.clip(value, 0, 255))


def decode_pixel(frame: np.ndarray, sample_rate: int) -> RGBPixel:
    frame_size = len(frame)

    return (
        magnitude_to_channel(magnitude_at_frequency(frame, sample_rate, R_FREQ), frame_size),
        magnitude_to_channel(magnitude_at_frequency(frame, sample_rate, G_FREQ), frame_size),
        magnitude_to_channel(magnitude_at_frequency(frame, sample_rate, B_FREQ), frame_size),
    )


def decode_audio(path: str | Path, pixel_duration: float) -> list[RGBPixel]:
    sample_rate, samples = load_audio(path)

    frames = split_frames(
        samples=samples,
        sample_rate=sample_rate,
        pixel_duration=pixel_duration,
    )

    return [decode_pixel(frame, sample_rate) for frame in frames]
