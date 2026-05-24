from __future__ import annotations

import argparse
import json
import mimetypes
import zlib
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from collections.abc import Sequence

from cypher.audio import (
    AUDIO_DIR,
    BUNDLE_AUDIO_DIR,
    DEFAULT_CHUNK_SIZE,
    OUTPUT_DIR,
    build_audio_payload,
    bytes_to_int16_samples,
    read_audio_payload,
    resolve_audio_output,
    write_audio,
    write_waveform_preview,
)
from cypher.crypto import (
    CRYPTO_MODE_NONE,
    CRYPTO_MODE_X25519_AESGCM_MULTI,
    decrypt_payload,
    decrypt_payload_multi,
    encrypt_payload_multi,
)
from cypher.keys import (
    DEFAULT_PRIVATE_KEY_PATH,
    DEFAULT_PUBLIC_KEY_PATH,
    require_touch_id,
)

PROJECT_NAME = "cypher"
VERSION = "1.0.0"

MAGIC = "CYPHER"
CONTAINER_MAGIC = b"CYPHER45"

HEADER_VERSION = 100

PAYLOAD_MODE = "ANY_FILE_SELF_CONTAINED_AUDIO"
BUNDLE_PAYLOAD_MODE = "MULTI_FILE_SELF_CONTAINED_AUDIO"
STREAMING_PAYLOAD_MODE = "CHUNKED_STREAM"

CHECKSUM_ALGORITHM = "SHA256"
COMPRESSION_ALGORITHM = "zlib"

DATA_DIR = Path("data")
INPUT_DIR = DATA_DIR / "input"

DEFAULT_BUNDLE_NAME = "bundle"

TOUCH_ID_DECODE_REASON = "En attente ton empreinte digitale pour déchiffrer le fichier."


@dataclass(frozen=True)
class CypherHeader:
    original_name: str
    original_suffix: str
    mime_type: str
    raw_size: int
    checksum: str
    relative_path: str | None = None
    magic: str = MAGIC
    version: int = HEADER_VERSION
    payload_mode: str = PAYLOAD_MODE
    checksum_algorithm: str = CHECKSUM_ALGORITHM
    compression_algorithm: str = COMPRESSION_ALGORITHM


@dataclass(frozen=True)
class ChunkHeader:
    index: int
    total_chunks: int
    raw_size: int
    compressed_size: int
    encrypted: bool


def compute_checksum(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def verify_checksum(expected: str, actual: str) -> bool:
    return expected.lower() == actual.lower()


def emit_progress(
    phase: str,
    current: int,
    total: int,
) -> None:
    print(
        f"PROGRESS phase={phase} current={current} total={total}",
        flush=True,
    )


def resolve_input_file(path: str | Path) -> Path:
    candidate = Path(path)

    if candidate.exists():
        return candidate

    candidate = INPUT_DIR / Path(path)

    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Input file not found: {path}")


def resolve_input_audio(path: str | Path) -> Path:
    candidate = Path(path)

    if candidate.exists():
        return candidate

    candidate = AUDIO_DIR / Path(path)

    if candidate.exists():
        return candidate

    candidate = BUNDLE_AUDIO_DIR / Path(path)

    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Audio file not found: {path}")


def read_file(path: str | Path) -> bytes:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    return file_path.read_bytes()


def write_file(path: str | Path, payload: bytes) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)


def detect_mime_type(path: str | Path) -> str:
    mime_type, _encoding = mimetypes.guess_type(Path(path).name)
    return mime_type or "application/octet-stream"


def safe_relative_path(path: Path) -> str:
    parts = []

    for part in path.parts:
        if part in {"", ".", ".."}:
            continue

        parts.append(part)

    if not parts:
        raise ValueError(f"Invalid relative path: {path}")

    return str(Path(*parts))


def create_header(
    input_path: str | Path,
    raw_size: int,
    checksum: str,
    payload_mode: str = PAYLOAD_MODE,
    relative_path: str | None = None,
) -> CypherHeader:
    path = Path(input_path)

    header = CypherHeader(
        original_name=path.name,
        original_suffix=path.suffix,
        mime_type=detect_mime_type(path),
        raw_size=raw_size,
        checksum=checksum,
        payload_mode=payload_mode,
        relative_path=relative_path,
    )

    validate_header(header)
    return header


def validate_header(header: CypherHeader) -> None:
    if header.magic != MAGIC:
        raise ValueError(f"Invalid magic: {header.magic}")

    if header.version != HEADER_VERSION:
        raise ValueError(f"Unsupported version: {header.version}")

    if header.payload_mode not in {PAYLOAD_MODE, BUNDLE_PAYLOAD_MODE}:
        raise ValueError(f"Unsupported payload mode: {header.payload_mode}")

    if header.raw_size < 0:
        raise ValueError("Invalid raw size")

    if not header.original_name:
        raise ValueError("Original filename cannot be empty")

    if not header.checksum:
        raise ValueError("Checksum cannot be empty")


def encode_header(header: CypherHeader) -> bytes:
    validate_header(header)
    return json.dumps(
        asdict(header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_header(payload: bytes) -> CypherHeader:
    data = json.loads(payload.decode("utf-8"))

    if "relative_path" not in data:
        data["relative_path"] = None

    header = CypherHeader(**data)
    validate_header(header)
    return header


def build_container(header: CypherHeader, payload: bytes) -> bytes:
    header_bytes = encode_header(header)
    header_size = len(header_bytes).to_bytes(8, byteorder="big")

    return CONTAINER_MAGIC + header_size + header_bytes + payload


def parse_container(container: bytes) -> tuple[CypherHeader, bytes]:
    magic_size = len(CONTAINER_MAGIC)

    if container[:magic_size] != CONTAINER_MAGIC:
        raise ValueError("Invalid cypher container magic")

    header_size_start = magic_size
    header_size_end = header_size_start + 8

    header_size = int.from_bytes(
        container[header_size_start:header_size_end],
        byteorder="big",
    )

    header_start = header_size_end
    header_end = header_start + header_size

    header = decode_header(container[header_start:header_end])
    payload = container[header_end:]

    if len(payload) != header.raw_size:
        raise ValueError(
            f"Invalid payload size: expected {header.raw_size}, got {len(payload)}"
        )

    return header, payload


def unique_output_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename

    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix

    for index in range(1, 10_000):
        deduplicated = directory / f"{stem}_{index}{suffix}"

        if not deduplicated.exists():
            return deduplicated

    raise FileExistsError(f"Unable to create unique output path for {filename}")


def resolve_decoded_output(
    output_name: str | None,
    original_name: str,
) -> Path:
    if output_name is not None:
        output_path = Path(output_name)

        if output_path.parent != Path("."):
            return output_path

        return OUTPUT_DIR / output_name

    return OUTPUT_DIR / original_name


def resolve_bundle_output_dir(
    output_name: str | None,
    bundle_name: str | None = None,
) -> Path:
    if output_name is not None:
        output_path = Path(output_name)

        if output_path.parent != Path("."):
            return output_path

        return OUTPUT_DIR / output_name

    if bundle_name:
        return OUTPUT_DIR / bundle_name

    return OUTPUT_DIR / DEFAULT_BUNDLE_NAME


def resolve_default_public_keys(
    args_public_keys: Sequence[str] | None,
) -> list[str]:
    if args_public_keys:
        return list(args_public_keys)

    if DEFAULT_PUBLIC_KEY_PATH.exists():
        return [str(DEFAULT_PUBLIC_KEY_PATH)]

    return []


def resolve_default_private_key(args_private_key: str | None) -> str | None:
    if args_private_key is not None:
        return args_private_key

    if DEFAULT_PRIVATE_KEY_PATH.exists():
        return str(DEFAULT_PRIVATE_KEY_PATH)

    return None


def compress_container(container: bytes, compression_level: int) -> bytes:
    print("Compressing chunk/container...")
    print(f"Input size        : {len(container):,} bytes")
    print(f"Compression level : {compression_level}")

    compressed = zlib.compress(container, level=compression_level)
    ratio = len(compressed) / max(len(container), 1)

    print(f"Compressed size   : {len(compressed):,} bytes")
    print(f"Compression ratio : {ratio:.2%}")

    return compressed


def decompress_container(payload: bytes) -> bytes:
    print("Decompressing chunk/container...")
    container = zlib.decompress(payload)
    print(f"Output bytes      : {len(container):,}")
    return container


def split_chunks(payload: bytes, chunk_size: int) -> list[bytes]:
    return [
        payload[index : index + chunk_size]
        for index in range(0, len(payload), chunk_size)
    ] or [b""]


def encode_chunked_payload(
    payload: bytes,
    compression_level: int,
    public_key: Sequence[str] | None,
) -> tuple[bytes, str, str | None]:
    chunks = split_chunks(
        payload=payload,
        chunk_size=DEFAULT_CHUNK_SIZE,
    )

    total_chunks = len(chunks)
    serialized = b""

    public_key_paths = resolve_default_public_keys(public_key)
    crypto_mode = (
        "chunked-x25519-aesgcm-multi"
        if public_key_paths
        else CRYPTO_MODE_NONE
    )

    print(f"Chunk count       : {total_chunks}")

    processed_chunk_bytes = 0
    total_chunk_bytes = len(payload)

    for index, chunk in enumerate(chunks, start=1):
        processed_chunk_bytes += len(chunk)

        emit_progress(
            phase="chunks",
            current=processed_chunk_bytes,
            total=total_chunk_bytes,
        )

        print(f"Chunk {index}/{total_chunks}")

        compressed = compress_container(
            container=chunk,
            compression_level=compression_level,
        )

        if public_key_paths:
            stored_chunk, crypto_meta = encrypt_payload_multi(
                payload=compressed,
                recipient_public_key_paths=public_key_paths,
            )
            encrypted = True
        else:
            stored_chunk = compressed
            crypto_meta = {"crypto_mode": CRYPTO_MODE_NONE}
            encrypted = False

        chunk_header = ChunkHeader(
            index=index,
            total_chunks=total_chunks,
            raw_size=len(chunk),
            compressed_size=len(stored_chunk),
            encrypted=encrypted,
        )

        header_bytes = json.dumps(
            asdict(chunk_header),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        crypto_bytes = json.dumps(
            crypto_meta,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        serialized += len(header_bytes).to_bytes(8, "big")
        serialized += header_bytes
        serialized += len(crypto_bytes).to_bytes(8, "big")
        serialized += crypto_bytes
        serialized += len(stored_chunk).to_bytes(8, "big")
        serialized += stored_chunk

    public_key_summary = ", ".join(public_key_paths) if public_key_paths else None
    return serialized, crypto_mode, public_key_summary


def decode_chunked_payload(payload: bytes, private_key: str | None) -> bytes:
    cursor = 0
    rebuilt = b""

    while cursor < len(payload):
        header_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        header = ChunkHeader(
            **json.loads(payload[cursor : cursor + header_size].decode("utf-8"))
        )
        cursor += header_size

        crypto_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        crypto_meta = json.loads(payload[cursor : cursor + crypto_size].decode("utf-8"))
        cursor += crypto_size

        chunk_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        stored_chunk = payload[cursor : cursor + chunk_size]
        cursor += chunk_size

        if header.encrypted:
            if private_key is None:
                raise ValueError("Private key path is required for encrypted chunks")

            crypto_mode = crypto_meta.get("crypto_mode")

            if crypto_mode == CRYPTO_MODE_X25519_AESGCM_MULTI:
                compressed = decrypt_payload_multi(
                    ciphertext=stored_chunk,
                    crypto_meta=crypto_meta,
                    private_key_path=private_key,
                )
            else:
                compressed = decrypt_payload(
                    ciphertext=stored_chunk,
                    crypto_meta=crypto_meta,
                    private_key_path=private_key,
                )
        else:
            compressed = stored_chunk

        chunk = decompress_container(compressed)

        if len(chunk) != header.raw_size:
            raise ValueError(
                "Invalid decoded chunk size: "
                f"expected {header.raw_size}, "
                f"got {len(chunk)}"
            )

        rebuilt += chunk

    return rebuilt


def encode_container_to_audio(
    container: bytes,
    header: CypherHeader,
    output_path: Path,
    sample_rate: int,
    compression_level: int,
    public_key: Sequence[str] | None,
) -> None:
    chunked_payload, crypto_mode, public_key_path = encode_chunked_payload(
        payload=container,
        compression_level=compression_level,
        public_key=public_key,
    )

    audio_payload = build_audio_payload(
        payload=chunked_payload,
        header=header,
        crypto_meta={
            "crypto_mode": crypto_mode,
        },
    )

    samples = bytes_to_int16_samples(audio_payload)

    write_audio(
        path=output_path,
        samples=samples,
        sample_rate=sample_rate,
    )

    write_waveform_preview(
        audio_path=output_path,
        samples=samples,
    )

    print("Encode completed.")
    print(f"Audio             : {output_path}")
    print("Embedded metadata : yes")
    print(f"Encryption        : {crypto_mode}")
    print(f"Public key        : {public_key_path or 'none'}")
    print(f"Payload mode      : {header.payload_mode}")

    if header.relative_path:
        print(f"Relative path     : {header.relative_path}")

    print(f"Checksum          : {header.checksum}")


def encode_command(args: argparse.Namespace) -> None:
    input_path = resolve_input_file(args.file)

    output_path = resolve_audio_output(
        input_path=input_path,
        audio_format=args.format,
        obfuscate_name=not args.keep_name,
    )

    payload = read_file(input_path)
    checksum = compute_checksum(payload)

    header = create_header(
        input_path=input_path,
        raw_size=len(payload),
        checksum=checksum,
        payload_mode=PAYLOAD_MODE,
    )

    container = build_container(
        header=header,
        payload=payload,
    )

    print("Starting V4.9 self-contained encode...")
    print(f"Input file        : {input_path}")
    print(f"MIME type         : {header.mime_type}")
    print(f"Raw size          : {len(payload):,} bytes")
    print(f"Sample rate       : {args.sample_rate} Hz")

    encode_container_to_audio(
        container=container,
        header=header,
        output_path=output_path,
        sample_rate=args.sample_rate,
        compression_level=args.compression_level,
        public_key=args.public_key,
    )


def decode_command(args: argparse.Namespace) -> None:
    from cypher.bundle import is_bundle_container, restore_bundle_payload

    audio_path = resolve_input_audio(args.file)

    print("Starting chunked decode...")

    _crypto_meta, payload = read_audio_payload(audio_path)

    private_key_path = resolve_default_private_key(args.private_key)

    require_touch_id(TOUCH_ID_DECODE_REASON)

    container = decode_chunked_payload(
        payload=payload,
        private_key=private_key_path,
    )

    header, restored_payload = parse_container(container)

    actual_checksum = compute_checksum(restored_payload)

    if not verify_checksum(header.checksum, actual_checksum):
        raise ValueError(
            "Checksum mismatch: "
            f"expected {header.checksum}, got {actual_checksum}"
        )

    if header.payload_mode == BUNDLE_PAYLOAD_MODE or is_bundle_container(
        restored_payload
    ):
        restore_bundle_payload(
            audio_path=audio_path,
            restored_payload=restored_payload,
            bundle_checksum=actual_checksum,
            output_dir=(
                resolve_bundle_output_dir(args.output)
                if args.output
                else None
            ),
            bundle_name=header.relative_path,
        )
        return

    output_path = resolve_decoded_output(
        output_name=args.output,
        original_name=header.original_name,
    )

    write_file(
        path=output_path,
        payload=restored_payload,
    )

    print("Decode completed.")
    print(f"Audio             : {audio_path}")
    print(f"Output file       : {output_path}")
    print(f"Original name     : {header.original_name}")
    print(f"MIME type         : {header.mime_type}")

    if header.relative_path:
        print(f"Relative path     : {header.relative_path}")

    print(f"Checksum          : {actual_checksum}")
