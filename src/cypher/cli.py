import argparse
from pathlib import Path

from cypher.audio_decoder import decode_audio_to_container
from cypher.audio_encoder import encode_container_to_audio
from cypher.checksum import compute_bytes_checksum, verify_checksum
from cypher.config import (
    AUDIO_DIR,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_COMPRESSION_LEVEL,
    DEFAULT_SAMPLE_RATE,
    INPUT_DIR,
    LOSSLESS_AUDIO_OUTPUT,
    OUTPUT_DIR,
    UNSAFE_AUDIO_OUTPUT,
)
from cypher.file_reader import read_file_bytes, resolve_input_file
from cypher.file_writer import write_file_bytes
from cypher.header import build_container, create_header, parse_container


def resolve_input_audio(name: str) -> Path:
    path = Path(name)

    if path.exists():
        return path

    candidate = AUDIO_DIR / name

    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Audio file not found: {name}")


def resolve_audio_output(
    input_path: Path,
    audio_format: str,
) -> Path:
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


def encode_command(args: argparse.Namespace) -> None:
    input_path = resolve_input_file(
        args.file,
        INPUT_DIR,
    )

    output_path = resolve_audio_output(
        input_path=input_path,
        audio_format=args.format,
    )

    payload = read_file_bytes(input_path)
    checksum = compute_bytes_checksum(payload)

    header = create_header(
        input_path=input_path,
        raw_size=len(payload),
        checksum=checksum,
    )

    container = build_container(
        header=header,
        payload=payload,
    )

    compressed_size = encode_container_to_audio(
        container=container,
        output_path=output_path,
        sample_rate=args.sample_rate,
        compression_level=args.compression_level,
    )

    print("Encode completed.")
    print(f"Input file       : {input_path}")
    print(f"Audio            : {output_path}")
    print(f"Embedded metadata: yes")
    print(f"MIME type        : {header.mime_type}")
    print(f"Raw size         : {header.raw_size:,} bytes")
    print(f"Compressed size  : {compressed_size:,} bytes")
    print(f"Checksum         : {checksum}")


def decode_command(args: argparse.Namespace) -> None:
    audio_path = resolve_input_audio(args.file)

    container = decode_audio_to_container(audio_path)

    header, payload = parse_container(container)

    actual_checksum = compute_bytes_checksum(payload)

    if not verify_checksum(header.checksum, actual_checksum):
        raise ValueError(
            "Checksum mismatch: "
            f"expected {header.checksum}, got {actual_checksum}"
        )

    output_path = resolve_decoded_output(
        output_name=args.output,
        original_name=header.original_name,
    )

    write_file_bytes(
        path=output_path,
        payload=payload,
    )

    print("Decode completed.")
    print(f"Audio            : {audio_path}")
    print(f"Output file      : {output_path}")
    print(f"Original name    : {header.original_name}")
    print(f"MIME type        : {header.mime_type}")
    print(f"Checksum         : {actual_checksum}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cypher",
        description=(
            "Encode any file into self-contained lossless audio "
            "and decode it back."
        ),
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
