from pathlib import Path
import zlib

import numpy as np
import soundfile as sf
from tqdm import tqdm


def load_audio_samples(path: str | Path) -> tuple[int, np.ndarray]:
    print(f"Reading audio     : {path}")

    data, sample_rate = sf.read(
        path,
        dtype="int16",
    )

    if data.ndim > 1:
        raise ValueError("Cypher payload audio must be mono")

    print(f"Sample rate       : {sample_rate} Hz")
    print(f"Audio samples     : {len(data):,}")

    return sample_rate, data


def int16_samples_to_bytes(samples: np.ndarray) -> bytes:
    print("Unpacking PCM16 audio samples into compressed bytes...")

    for _ in tqdm(
        range(len(samples)),
        desc="Unpacking samples",
        unit="sample",
    ):
        pass

    return samples.astype(np.int16).tobytes()


def decompress_container(payload: bytes) -> bytes:
    print("Decompressing embedded container...")

    container = zlib.decompress(payload)

    print(f"Container bytes   : {len(container):,}")

    return container


def decode_audio_to_container(path: str | Path) -> bytes:
    print("Starting V4.2 self-contained decode...")

    _sample_rate, samples = load_audio_samples(path)

    compressed_payload = int16_samples_to_bytes(samples)

    container = decompress_container(compressed_payload)

    print("Audio decode completed.")

    return container
