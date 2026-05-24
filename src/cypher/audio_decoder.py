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
        raise ValueError("V4 payload audio must be mono")

    print(f"Sample rate       : {sample_rate} Hz")
    print(f"Audio samples     : {len(data):,}")

    return sample_rate, data


def int16_samples_to_bytes(
    samples: np.ndarray,
    compressed_size: int,
) -> bytes:
    print("Unpacking PCM16 audio samples into bytes...")

    for _ in tqdm(
        range(len(samples)),
        desc="Unpacking samples",
        unit="sample",
    ):
        pass

    payload = samples.astype(np.int16).tobytes()
    payload = payload[:compressed_size]

    print(f"Compressed bytes  : {len(payload):,}")

    return payload


def decompress_payload(
    payload: bytes,
    expected_raw_size: int,
) -> bytes:
    print("Decompressing payload...")

    raw_payload = zlib.decompress(payload)

    print(f"Raw bytes         : {len(raw_payload):,}")

    if len(raw_payload) != expected_raw_size:
        raise ValueError(
            f"Invalid raw payload size: expected {expected_raw_size}, "
            f"got {len(raw_payload)}"
        )

    return raw_payload


def decode_audio_to_payload(
    path: str | Path,
    compressed_size: int,
    raw_size: int,
) -> bytes:
    print("Starting V4 audio-to-file decode...")

    _sample_rate, samples = load_audio_samples(path)

    compressed_payload = int16_samples_to_bytes(
        samples=samples,
        compressed_size=compressed_size,
    )

    payload = decompress_payload(
        payload=compressed_payload,
        expected_raw_size=raw_size,
    )

    print("Audio decode completed.")

    return payload
