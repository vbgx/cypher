from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import soundfile as sf
from tqdm import tqdm

from cypher.crypto import CRYPTO_MODE_NONE

if TYPE_CHECKING:
    from cypher.container import CypherHeader

VERSION = "1.0.0"

AUDIO_MAGIC = b"CYPHERAUDIO49"

DEFAULT_SAMPLE_RATE = 44_100
DEFAULT_AUDIO_FORMAT = "flac"
DEFAULT_COMPRESSION_LEVEL = 9
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024
DEFAULT_OBFUSCATED_NAME_LENGTH = 24

LOSSLESS_AUDIO_OUTPUT = {".wav", ".flac"}
UNSAFE_AUDIO_OUTPUT = {".mp3"}

DATA_DIR = Path("data")
AUDIO_DIR = DATA_DIR / "audio"
BUNDLE_AUDIO_DIR = AUDIO_DIR / "bundle"
OUTPUT_DIR = DATA_DIR / "output"
WAVEFORM_DIR = OUTPUT_DIR / "waveforms"

COMPRESSION_ALGORITHM = "zlib"


def emit_progress(
    phase: str,
    current: int,
    total: int,
) -> None:
    print(
        f"PROGRESS phase={phase} current={current} total={total}",
        flush=True,
    )


def generate_obfuscated_stem(length: int = DEFAULT_OBFUSCATED_NAME_LENGTH) -> str:
    return secrets.token_urlsafe(length)[:length]


def build_audio_payload(
    payload: bytes,
    header: CypherHeader,
    crypto_meta: dict[str, object] | None = None,
) -> bytes:
    meta: dict[str, object] = crypto_meta or {"crypto_mode": CRYPTO_MODE_NONE}
    crypto_mode = str(meta["crypto_mode"])

    if crypto_mode == CRYPTO_MODE_NONE:
        public_meta = {
            "cypher_version": VERSION,
            "original_name": header.original_name,
            "original_suffix": header.original_suffix,
            "mime_type": header.mime_type,
            "raw_size": str(header.raw_size),
            "checksum": header.checksum,
            "payload_mode": header.payload_mode,
            "compression_algorithm": COMPRESSION_ALGORITHM,
        }
    else:
        public_meta = {
            "cypher_version": VERSION,
            "payload_mode": "ENCRYPTED_CONTAINER",
            "compression_algorithm": COMPRESSION_ALGORITHM,
        }

    meta = {**meta, "public": public_meta}

    meta_bytes = json.dumps(
        meta,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    meta_size = len(meta_bytes).to_bytes(8, byteorder="big")
    payload_size = len(payload).to_bytes(8, byteorder="big")

    return AUDIO_MAGIC + meta_size + payload_size + meta_bytes + payload


def parse_audio_payload(audio_payload: bytes) -> tuple[dict[str, object], bytes]:
    magic_size = len(AUDIO_MAGIC)

    if audio_payload[:magic_size] != AUDIO_MAGIC:
        raise ValueError("Invalid cypher audio magic")

    meta_size_start = magic_size
    meta_size_end = meta_size_start + 8

    payload_size_start = meta_size_end
    payload_size_end = payload_size_start + 8

    meta_size = int.from_bytes(
        audio_payload[meta_size_start:meta_size_end],
        byteorder="big",
    )

    payload_size = int.from_bytes(
        audio_payload[payload_size_start:payload_size_end],
        byteorder="big",
    )

    meta_start = payload_size_end
    meta_end = meta_start + meta_size

    payload_start = meta_end
    payload_end = payload_start + payload_size

    meta = json.loads(audio_payload[meta_start:meta_end].decode("utf-8"))
    payload = audio_payload[payload_start:payload_end]

    if len(payload) != payload_size:
        raise ValueError(
            f"Invalid audio payload size: expected {payload_size}, got {len(payload)}"
        )

    return meta, payload


def resolve_audio_output(
    input_path: Path,
    audio_format: str,
    obfuscate_name: bool = True,
) -> Path:
    suffix = audio_format if audio_format.startswith(".") else f".{audio_format}"

    if suffix in UNSAFE_AUDIO_OUTPUT:
        raise ValueError(
            "MP3 is lossy and cannot preserve arbitrary files bit-perfect. "
            "Use WAV or FLAC."
        )

    if suffix not in LOSSLESS_AUDIO_OUTPUT:
        raise ValueError(f"Unsupported audio format: {suffix}")

    stem = generate_obfuscated_stem() if obfuscate_name else input_path.stem

    return AUDIO_DIR / f"{stem}{suffix}"


def bytes_to_int16_samples(payload: bytes) -> np.ndarray:
    print("Packing bytes into PCM16 audio samples...")

    if len(payload) % 2 != 0:
        payload += b"\x00"

    total_samples = len(payload) // 2

    emit_progress(
        phase="audio",
        current=0,
        total=100,
    )

    for _ in tqdm(
        range(total_samples),
        desc="Packing samples",
        unit="sample",
    ):
        pass

    samples = np.frombuffer(payload, dtype=np.int16).copy()

    emit_progress(
        phase="audio",
        current=100,
        total=100,
    )

    print(f"Audio samples     : {len(samples):,}")

    return samples


def int16_samples_to_bytes(samples: np.ndarray) -> bytes:
    print("Unpacking PCM16 audio samples into bytes...")

    emit_progress(
        phase="audio",
        current=0,
        total=100,
    )

    for _ in tqdm(
        range(len(samples)),
        desc="Unpacking samples",
        unit="sample",
    ):
        pass

    emit_progress(
        phase="audio",
        current=100,
        total=100,
    )

    return samples.astype(np.int16).tobytes()


def write_audio(
    path: str | Path,
    samples: np.ndarray,
    sample_rate: int,
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


def write_waveform_preview(
    audio_path: str | Path,
    samples: np.ndarray,
    width: int = 1200,
    height: int = 320,
) -> Path:
    output_path = WAVEFORM_DIR / f"{Path(audio_path).stem}.pgm"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if samples.size == 0:
        raise ValueError("Cannot render waveform preview for empty audio.")

    mono = samples.astype(np.float32)
    peak = float(np.max(np.abs(mono))) or 1.0
    mono = mono / peak

    bucket_count = min(width, max(1, mono.size))
    buckets = np.array_split(mono, bucket_count)

    pixels = np.full((height, bucket_count), 255, dtype=np.uint8)
    center = height // 2

    for x, bucket in enumerate(buckets):
        if bucket.size == 0:
            continue

        low = int(center + float(np.min(bucket)) * (height // 2 - 8))
        high = int(center + float(np.max(bucket)) * (height // 2 - 8))

        y1 = max(0, min(height - 1, min(low, high)))
        y2 = max(0, min(height - 1, max(low, high)))

        pixels[y1 : y2 + 1, x] = 0
        pixels[center, x] = 80

    with output_path.open("wb") as file:
        file.write(f"P5\n{bucket_count} {height}\n255\n".encode("ascii"))
        file.write(pixels.tobytes())

    print(f"Waveform preview  : {output_path}")
    return output_path


def read_audio(path: str | Path) -> tuple[int, np.ndarray]:
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


def read_audio_payload(path: str | Path) -> tuple[dict[str, object], bytes]:
    _sample_rate, samples = read_audio(path)
    audio_payload = int16_samples_to_bytes(samples)
    return parse_audio_payload(audio_payload)
