import argparse
import json
import mimetypes
import zlib
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np
import soundfile as sf
from tqdm import tqdm


PROJECT_NAME = "cypher"
VERSION = "0.4.3"

MAGIC = "CYPHER"
CONTAINER_MAGIC = b"CYPHER43"
HEADER_VERSION = 43

PAYLOAD_MODE = "ANY_FILE_SELF_CONTAINED_AUDIO"
CHECKSUM_ALGORITHM = "SHA256"
COMPRESSION_ALGORITHM = "zlib"

DEFAULT_SAMPLE_RATE = 44_100
DEFAULT_AUDIO_FORMAT = "flac"
DEFAULT_COMPRESSION_LEVEL = 9

LOSSLESS_AUDIO_OUTPUT = {".wav", ".flac"}
UNSAFE_AUDIO_OUTPUT = {".mp3"}

DATA_DIR = Path("data")
INPUT_DIR = DATA_DIR / "input"
AUDIO_DIR = DATA_DIR / "audio"
OUTPUT_DIR = DATA_DIR / "output"


@dataclass(frozen=True)
class CypherHeader:
    original_name: str
    original_suffix: str
    mime_type: str
    raw_size: int
    checksum: str
    magic: str = MAGIC
    version: int = HEADER_VERSION
    payload_mode: str = PAYLOAD_MODE
    checksum_algorithm: str = CHECKSUM_ALGORITHM
    compression_algorithm: str = COMPRESSION_ALGORITHM


def compute_checksum(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def verify_checksum(expected: str, actual: str) -> bool:
    return expected.lower() == actual.lower()


def resolve_input_file(path: str | Path) -> Path:
    candidate = Path(path)

    if candidate.exists():
        return candidate

    candidate = INPUT_DIR / path

    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Input file not found: {path}")


def resolve_input_audio(path: str | Path) -> Path:
    candidate = Path(path)

    if candidate.exists():
        return candidate

    candidate = AUDIO_DIR / path

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


def create_header(
    input_path: str | Path,
    raw_size: int,
    checksum: str,
) -> CypherHeader:
    path = Path(input_path)

    header = CypherHeader(
        original_name=path.name,
        original_suffix=path.suffix,
        mime_type=detect_mime_type(path),
        raw_size=raw_size,
        checksum=checksum,
    )

    validate_header(header)

    return header


def validate_header(header: CypherHeader) -> None:
    if header.magic != MAGIC:
        raise ValueError(f"Invalid magic: {header.magic}")

    if header.version != HEADER_VERSION:
        raise ValueError(f"Unsupported version: {header.version}")

    if header.payload_mode != PAYLOAD_MODE:
        raise ValueError(f"Unsupported payload mode: {header.payload_mode}")

    if header.raw_size < 0:
        raise ValueError("Invalid raw size")

    if not header.original_name:
        raise ValueError("Original filename cannot be empty")

    if not header.checksum:
        raise ValueError("Checksum cannot be empty")

    if header.checksum_algorithm != CHECKSUM_ALGORITHM:
        raise ValueError(f"Unsupported checksum algorithm: {header.checksum_algorithm}")

    if header.compression_algorithm != COMPRESSION_ALGORITHM:
        raise ValueError(
            f"Unsupported compression algorithm: {header.compression_algorithm}"
        )


def encode_header(header: CypherHeader) -> bytes:
    validate_header(header)

    return json.dumps(
        asdict(header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_header(payload: bytes) -> CypherHeader:
    data = json.loads(payload.decode("utf-8"))

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


def resolve_audio_output(input_path: Path, audio_format: str) -> Path:
    suffix = audio_format if audio_format.startswith(".") else f".{audio_format}"

    if suffix in UNSAFE_AUDIO_OUTPUT:
        raise ValueError(
            "MP3 is lossy and cannot preserve arbitrary files bit-perfect. "
            "Use WAV or FLAC."
        )

    if suffix not in LOSSLESS_AUDIO_OUTPUT:
        raise ValueError(f"Unsupported audio format: {suffix}")

    return AUDIO_DIR / f"{input_path.stem}{suffix}"


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


def compress_container(
    container: bytes,
    compression_level: int,
) -> bytes:
    print("Compressing embedded container...")
    print(f"Container size    : {len(container):,} bytes")
    print(f"Compression level : {compression_level}")

    compressed = zlib.compress(container, level=compression_level)
    ratio = len(compressed) / max(len(container), 1)

    print(f"Compressed size   : {len(compressed):,} bytes")
    print(f"Compression ratio : {ratio:.2%}")

    return compressed


def decompress_container(payload: bytes) -> bytes:
    print("Decompressing embedded container...")

    container = zlib.decompress(payload)

    print(f"Container bytes   : {len(container):,}")

    return container


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


def int16_samples_to_bytes(samples: np.ndarray) -> bytes:
    print("Unpacking PCM16 audio samples into compressed bytes...")

    for _ in tqdm(
        range(len(samples)),
        desc="Unpacking samples",
        unit="sample",
    ):
        pass

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


def encode_command(args: argparse.Namespace) -> None:
    input_path = resolve_input_file(args.file)
    output_path = resolve_audio_output(input_path, args.format)

    payload = read_file(input_path)
    checksum = compute_checksum(payload)

    header = create_header(
        input_path=input_path,
        raw_size=len(payload),
        checksum=checksum,
    )

    container = build_container(
        header=header,
        payload=payload,
    )

    print("Starting V4.3 self-contained encode...")
    print(f"Input file        : {input_path}")
    print(f"MIME type         : {header.mime_type}")
    print(f"Raw size          : {len(payload):,} bytes")
    print(f"Sample rate       : {args.sample_rate} Hz")

    compressed = compress_container(
        container=container,
        compression_level=args.compression_level,
    )

    samples = bytes_to_int16_samples(compressed)

    write_audio(
        path=output_path,
        samples=samples,
        sample_rate=args.sample_rate,
    )

    print("Encode completed.")
    print(f"Audio             : {output_path}")
    print(f"Embedded metadata : yes")
    print(f"Checksum          : {checksum}")


def decode_command(args: argparse.Namespace) -> None:
    audio_path = resolve_input_audio(args.file)

    print("Starting V4.3 self-contained decode...")

    _sample_rate, samples = read_audio(audio_path)

    compressed = int16_samples_to_bytes(samples)
    container = decompress_container(compressed)

    header, payload = parse_container(container)

    actual_checksum = compute_checksum(payload)

    if not verify_checksum(header.checksum, actual_checksum):
        raise ValueError(
            "Checksum mismatch: "
            f"expected {header.checksum}, got {actual_checksum}"
        )

    output_path = resolve_decoded_output(
        output_name=args.output,
        original_name=header.original_name,
    )

    write_file(
        path=output_path,
        payload=payload,
    )

    print("Decode completed.")
    print(f"Audio             : {audio_path}")
    print(f"Output file       : {output_path}")
    print(f"Original name     : {header.original_name}")
    print(f"MIME type         : {header.mime_type}")
    print(f"Checksum          : {actual_checksum}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cypher",
        description=(
            "Encode any file into self-contained lossless audio "
            "and decode it back."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROJECT_NAME} {VERSION}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    encode_parser = subparsers.add_parser(
        "encode",
        help="Encode any file to self-contained audio",
    )

    encode_parser.add_argument(
        "file",
        help="Input filename or path",
    )

    encode_parser.add_argument(
        "--format",
        default=DEFAULT_AUDIO_FORMAT,
        choices=["wav", "flac", "mp3"],
    )

    encode_parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
    )

    encode_parser.add_argument(
        "--compression-level",
        type=int,
        default=DEFAULT_COMPRESSION_LEVEL,
        choices=range(0, 10),
        metavar="[0-9]",
    )

    encode_parser.set_defaults(func=encode_command)

    decode_parser = subparsers.add_parser(
        "decode",
        help="Decode self-contained audio back to original file",
    )

    decode_parser.add_argument(
        "file",
        help="Input audio filename or path",
    )

    decode_parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Optional output filename or path",
    )

    decode_parser.set_defaults(func=decode_command)

    decore_parser = subparsers.add_parser(
        "decore",
        help="Alias for decode",
    )

    decore_parser.add_argument(
        "file",
        help="Input audio filename or path",
    )

    decore_parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Optional output filename or path",
    )

    decore_parser.set_defaults(func=decode_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
