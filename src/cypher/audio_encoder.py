from pathlib import Path
import zlib

import numpy as np
import soundfile as sf
from tqdm import tqdm

from cypher.config import DEFAULT_COMPRESSION_LEVEL, DEFAULT_SAMPLE_RATE


RGBPixel = tuple[int, int, int]


def pixels_to_bytes(pixels: list[RGBPixel]) -> bytes:
    """
    Convert RGB pixels to exact raw bytes.
    """
    payload = bytearray()

    for r, g, b in tqdm(
        pixels,
        desc="Packing RGB bytes",
        unit="px",
    ):
        payload.extend((r, g, b))

    return bytes(payload)


def compress_payload(
    payload: bytes,
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
) -> bytes:
    """
    Compress raw RGB bytes losslessly.
    """
    print("Compressing payload with zlib...")
    print(f"Raw size        : {len(payload):,} bytes")
    print(f"Compression lvl : {compression_level}")

    compressed = zlib.compress(payload, level=compression_level)

    ratio = len(compressed) / len(payload)

    print(f"Compressed size : {len(compressed):,} bytes")
    print(f"Ratio           : {ratio:.2%}")

    return compressed


def bytes_to_int16_samples(payload: bytes) -> np.ndarray:
    """
    Store bytes as int16 audio samples.

    Each pair of bytes becomes one signed int16 sample.
    If payload length is odd, one zero byte is appended.
    """
    print("Converting compressed bytes to audio samples...")

    if len(payload) % 2 != 0:
        payload += b"\x00"

    samples = np.frombuffer(payload, dtype=np.int16).copy()

    print(f"Audio samples   : {len(samples):,}")

    return samples


def save_audio(
    path: str | Path,
    samples: np.ndarray,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    """
    Save int16 samples as WAV/FLAC.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing audio   : {output_path}")

    sf.write(
        file=output_path,
        data=samples,
        samplerate=sample_rate,
        subtype="PCM_16",
    )


def encode_audio(
    pixels: list[RGBPixel],
    output_path: str | Path,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
) -> tuple[int, int]:
    """
    Encode RGB pixels into a lossless audio payload.

    Returns:
        raw_size,
        compressed_size
    """
    print("Starting V3 lossless encode...")
    print(f"Pixels          : {len(pixels):,}")
    print(f"Sample rate     : {sample_rate} Hz")

    raw_payload = pixels_to_bytes(pixels)

    compressed_payload = compress_payload(
        raw_payload,
        compression_level=compression_level,
    )

    samples = bytes_to_int16_samples(compressed_payload)

    save_audio(
        path=output_path,
        samples=samples,
        sample_rate=sample_rate,
    )

    print("Audio encode completed.")

    return len(raw_payload), len(compressed_payload)
