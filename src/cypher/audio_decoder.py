from pathlib import Path
import zlib

import numpy as np
import soundfile as sf
from tqdm import tqdm


RGBPixel = tuple[int, int, int]


def load_audio_samples(path: str | Path) -> tuple[int, np.ndarray]:
    """
    Load audio file as int16 samples.
    """
    print(f"Reading audio   : {path}")

    data, sample_rate = sf.read(
        path,
        dtype="int16",
    )

    if data.ndim > 1:
        raise ValueError("V3 payload audio must be mono")

    print(f"Sample rate     : {sample_rate} Hz")
    print(f"Audio samples   : {len(data):,}")

    return sample_rate, data


def int16_samples_to_bytes(
    samples: np.ndarray,
    compressed_size: int,
) -> bytes:
    """
    Convert int16 samples back to compressed bytes.
    """
    print("Converting audio samples back to compressed bytes...")

    payload = samples.astype(np.int16).tobytes()

    payload = payload[:compressed_size]

    print(f"Compressed bytes: {len(payload):,}")

    return payload


def decompress_payload(payload: bytes, expected_raw_size: int) -> bytes:
    """
    Decompress lossless RGB payload.
    """
    print("Decompressing payload with zlib...")

    raw_payload = zlib.decompress(payload)

    print(f"Raw bytes       : {len(raw_payload):,}")

    if len(raw_payload) != expected_raw_size:
        raise ValueError(
            f"Invalid raw payload size: expected {expected_raw_size}, "
            f"got {len(raw_payload)}"
        )

    return raw_payload


def bytes_to_pixels(payload: bytes) -> list[RGBPixel]:
    """
    Convert RGB byte payload back to pixels.
    """
    if len(payload) % 3 != 0:
        raise ValueError("RGB payload length must be divisible by 3")

    pixels: list[RGBPixel] = []

    for index in tqdm(
        range(0, len(payload), 3),
        desc="Unpacking RGB bytes",
        unit="px",
        total=len(payload) // 3,
    ):
        pixels.append(
            (
                payload[index],
                payload[index + 1],
                payload[index + 2],
            )
        )

    return pixels


def decode_audio(
    path: str | Path,
    compressed_size: int,
    raw_size: int,
) -> list[RGBPixel]:
    """
    Decode lossless audio payload back into RGB pixels.
    """
    print("Starting V3 lossless decode...")

    _sample_rate, samples = load_audio_samples(path)

    compressed_payload = int16_samples_to_bytes(
        samples=samples,
        compressed_size=compressed_size,
    )

    raw_payload = decompress_payload(
        compressed_payload,
        expected_raw_size=raw_size,
    )

    pixels = bytes_to_pixels(raw_payload)

    print("Audio decode completed.")
    print(f"Decoded pixels  : {len(pixels):,}")

    return pixels
