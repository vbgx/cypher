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


def load_wav(path: str | Path) -> tuple[int, np.ndarray]:
    """
    Load WAV file.

    Returns:
        sample_rate,
        mono audio samples
    """
    sample_rate, data = wavfile.read(path)

    if data.ndim > 1:
        data = data.mean(axis=1)

    data = data.astype(np.float32)

    return sample_rate, data


def split_frames(
    samples: np.ndarray,
    sample_rate: int,
    pixel_duration: float,
) -> list[np.ndarray]:
    """
    Split audio into pixel frames.
    """
    frame_size = int(sample_rate * pixel_duration)

    frames = []

    for start in range(0, len(samples), frame_size):
        end = start + frame_size

        frame = samples[start:end]

        if len(frame) == frame_size:
            frames.append(frame)

    return frames


def dominant_frequency(
    frame: np.ndarray,
    sample_rate: int,
    f_min: float,
    f_max: float,
) -> float:
    """
    Detect dominant frequency in a band.
    """
    fft = np.fft.rfft(frame)

    magnitudes = np.abs(fft)

    freqs = np.fft.rfftfreq(
        len(frame),
        d=1 / sample_rate,
    )

    mask = (freqs >= f_min) & (freqs <= f_max)

    filtered_freqs = freqs[mask]
    filtered_mag = magnitudes[mask]

    peak_index = np.argmax(filtered_mag)

    return float(filtered_freqs[peak_index])


def freq_to_channel(
    freq: float,
    f_min: float,
    f_max: float,
) -> int:
    """
    Convert frequency back to RGB channel value.
    """
    normalized = (freq - f_min) / (f_max - f_min)

    value = round(normalized * 255)

    return int(np.clip(value, 0, 255))


def decode_pixel(
    frame: np.ndarray,
    sample_rate: int,
) -> RGBPixel:
    """
    Decode one audio frame into RGB pixel.
    """
    r_freq = dominant_frequency(
        frame,
        sample_rate,
        R_MIN,
        R_MAX,
    )

    g_freq = dominant_frequency(
        frame,
        sample_rate,
        G_MIN,
        G_MAX,
    )

    b_freq = dominant_frequency(
        frame,
        sample_rate,
        B_MIN,
        B_MAX,
    )

    r = freq_to_channel(r_freq, R_MIN, R_MAX)
    g = freq_to_channel(g_freq, G_MIN, G_MAX)
    b = freq_to_channel(b_freq, B_MIN, B_MAX)

    return (r, g, b)


def decode_audio(
    path: str | Path,
    pixel_duration: float,
) -> list[RGBPixel]:
    """
    Decode WAV audio into RGB pixel stream.
    """
    sample_rate, samples = load_wav(path)

    frames = split_frames(
        samples,
        sample_rate,
        pixel_duration,
    )

    pixels = []

    for frame in frames:
        pixel = decode_pixel(
            frame,
            sample_rate,
        )

        pixels.append(pixel)

    return pixels


def main() -> None:
    """
    Simple manual test.
    """
    pixels = decode_audio(
        "data/audio/example.wav",
        pixel_duration=0.01,
    )

    print(f"Decoded pixels: {len(pixels)}")

    print("First 10 pixels:")

    for pixel in pixels[:10]:
        print(pixel)


if __name__ == "__main__":
    main()
