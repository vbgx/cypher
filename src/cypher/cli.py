import argparse
from pathlib import Path

from cypher.audio_decoder import decode_audio
from cypher.audio_encoder import encode_audio
from cypher.checksum import compute_pixel_checksum, verify_checksum
from cypher.config import (
    AUDIO_DIR,
    DEFAULT_PIXEL_DURATION,
    DEFAULT_SAMPLE_RATE,
    INPUT_DIR,
    OUTPUT_DIR,
    SUPPORTED_AUDIO_OUTPUT,
)
from cypher.header import create_header, get_pixel_count, load_header, save_header
from cypher.image_reader import read_image
from cypher.image_writer import write_image


def resolve_input_image(name: str) -> Path:
    path = Path(name)
    if path.exists():
        return path
    return INPUT_DIR / name


def resolve_input_audio(name: str) -> Path:
    path = Path(name)
    if path.exists():
        return path
    return AUDIO_DIR / name


def resolve_audio_output(image_path: Path, audio_format: str) -> Path:
    suffix = audio_format if audio_format.startswith(".") else f".{audio_format}"
    if suffix not in SUPPORTED_AUDIO_OUTPUT:
        raise ValueError(f"Unsupported audio format: {suffix}")
    return AUDIO_DIR / f"{image_path.stem}{suffix}"


def resolve_image_output(audio_path: Path) -> Path:
    return OUTPUT_DIR / f"{audio_path.stem}.png"


def encode_command(args: argparse.Namespace) -> None:
    image_path = resolve_input_image(args.file)
    output_path = resolve_audio_output(image_path, args.format)

    width, height, pixels = read_image(image_path)
    checksum = compute_pixel_checksum(pixels)

    encode_audio(
        pixels=pixels,
        output_path=output_path,
        pixel_duration=args.pixel_duration,
        sample_rate=args.sample_rate,
    )

    header = create_header(
        width=width,
        height=height,
        pixel_duration=args.pixel_duration,
        sample_rate=args.sample_rate,
        checksum=checksum,
    )

    metadata_path = save_header(header, output_path)

    print("Encode completed.")
    print(f"Image   : {image_path}")
    print(f"Audio   : {output_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Size    : {width}x{height}")
    print(f"Checksum: {checksum}")


def decode_command(args: argparse.Namespace) -> None:
    audio_path = resolve_input_audio(args.file)
    output_path = resolve_image_output(audio_path)

    header = load_header(audio_path)

    pixels = decode_audio(
        path=audio_path,
        pixel_duration=header.pixel_duration,
    )

    expected_pixels = get_pixel_count(header)

    if len(pixels) < expected_pixels:
        raise ValueError(
            f"Decoded pixel count too small: expected {expected_pixels}, got {len(pixels)}"
        )

    pixels = pixels[:expected_pixels]

    actual_checksum = compute_pixel_checksum(pixels)

    if not verify_checksum(header.checksum, actual_checksum):
        print("Warning: checksum mismatch.")
        print(f"Expected: {header.checksum}")
        print(f"Actual  : {actual_checksum}")

    write_image(
        path=output_path,
        width=header.width,
        height=header.height,
        pixels=pixels,
    )

    print("Decode completed.")
    print(f"Audio   : {audio_path}")
    print(f"Image   : {output_path}")
    print(f"Size    : {header.width}x{header.height}")
    print(f"Checksum: {actual_checksum}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cypher",
        description="Encode images into audio and decode audio back into images.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    encode_parser = subparsers.add_parser("encode")
    encode_parser.add_argument("file")
    encode_parser.add_argument(
        "--format",
        default="flac",
        choices=["wav", "flac"],
    )
    encode_parser.add_argument(
        "--pixel-duration",
        type=float,
        default=DEFAULT_PIXEL_DURATION,
    )
    encode_parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
    )
    encode_parser.set_defaults(func=encode_command)

    decode_parser = subparsers.add_parser("decode")
    decode_parser.add_argument("file")
    decode_parser.set_defaults(func=decode_command)

    decore_parser = subparsers.add_parser("decore")
    decore_parser.add_argument("file")
    decore_parser.set_defaults(func=decode_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
