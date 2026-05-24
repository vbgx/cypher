from pathlib import Path
import zlib

import numpy as np
import soundfile as sf
from tqdm import tqdm

from cypher.config import DEFAULT_COMPRESSION_LEVEL, DEFAULT_SAMPLE_RATE


def compress_container(
    container: bytes,
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
) -> bytes:
    print("Compressing embedded container...")
    print(f"Container size    : {len(container):,} bytes")
    print(f"Compression level : {compression_level}")

    compressed = zlib.compress(container, level=compression_level)

    ratio = len(compressed) / max(len(container), 1)

    print(f"Compressed size   : {len(compressed):,} bytes")
    print(f"Compression ratio : {ratio:.2%}")

    return compressed


def bytes_to_int16_samples(payload: bytes) -> np.ndarray:
    print("Packing compressed bytes into PCM16 audio samples...")

    if len(payload) % 2 != 0:
        payload += b"\x00"

    total_samples = len(payload) // 2

    for _ in tqdm(
        range(total_samples),
        desc="Packing samples",
        unit="sample",
    ):
        pass

    samples = np.frombuffer(payload, dtype=np.int16).copy()

    print(f"Audio samples     : {len(samples):,}")

    return samples


def save_audio(
    path: str | Path,
    samples: np.ndarray,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing audio     : {output_path}")

    sf.write(
        file=output_path,
        data=samples,
        samplerate=sample_rate,
        subtype="PCM_16",
    )


def encode_container_to_audio(
    container: bytes,
    output_path: str | Path,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
) -> int:
    print("Starting V4.2 self-contained encode...")
    print(f"Sample rate       : {sample_rate} Hz")

    compressed = compress_container(
        container=container,
        compression_level=compression_level,
    )

    samples = bytes_to_int16_samples(compressed)

    save_audio(
        path=output_path,
        samples=samples,
        sample_rate=sample_rate,
    )

    print("Audio encode completed.")

    return len(compressed)
