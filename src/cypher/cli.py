import argparse
from pathlib import Path

from cypher.audio_decoder import decode_audio
from cypher.audio_encoder import encode_audio
from cypher.checksum import compute_pixel_checksum, verify_checksum
from cypher.config import DEFAULT_PIXEL_DURATION
from cypher.header import create_header, get_pixel_count
from cypher.image_reader import read_image
from cypher.image_writer import write_image


def encode_command(args: argparse.Namespace) -> None:
    """
    Encode image -> audio.

    V1 note:
    The header is created and printed, but not yet embedded into the WAV stream.
    """
    width, height, pixels = read_image(args.input)

    checksum = compute_pixel_checksum(pixels)

    header = create_header(
        width=width,
        height=height,
        pixel_duration=args.pixel_duration,
        checksum=checksum,
    )

    encode_audio(
        pixels=pixels,
        output_path=args.output,
        pixel_duration=args.pixel_duration,
    )

    print("Encode completed.")
    print(f"Input image : {args.input}")
    print(f"Output audio: {args.output}")
    print(f"Resolution  : {width}x{height}")
    print(f"Pixels      : {len(pixels)}")
    print(f"Checksum    : {header.checksum}")
    print()
    print("Header metadata:")
    print(header)


def decode_command(args: argparse.Namespace) -> None:
    """
    Decode audio -> image.

    V1 note:
    Width, height and checksum are provided through CLI options until
    header embedding/reading is implemented.
    """
    pixels = decode_audio(
        path=args.input,
        pixel_duration=args.pixel_duration,
    )

    header = create_header(
        width=args.width,
        height=args.height,
        pixel_duration=args.pixel_duration,
        checksum=args.checksum or "unchecked",
    )

    expected_pixels = get_pixel_count(header)

    if len(pixels) < expected_pixels:
        raise ValueError(
            f"Decoded pixel count is too small: "
            f"expected {expected_pixels}, got {len(pixels)}"
        )

    pixels = pixels[:expected_pixels]

    actual_checksum = compute_pixel_checksum(pixels)

    if args.checksum is not None:
        if not verify_checksum(args.checksum, actual_checksum):
            raise ValueError(
                "Checksum mismatch: "
                f"expected {args.checksum}, got {actual_checksum}"
            )

    write_image(
        path=args.output,
        width=header.width,
        height=header.height,
        pixels=pixels,
    )

    print("Decode completed.")
    print(f"Input audio : {args.input}")
    print(f"Output image: {args.output}")
    print(f"Resolution  : {header.width}x{header.height}")
    print(f"Pixels      : {len(pixels)}")
    print(f"Checksum    : {actual_checksum}")


def build_parser() -> argparse.ArgumentParser:
    """
    Build CLI parser.
    """
    parser = argparse.ArgumentParser(
        prog="cypher",
        description="Encode images into audio and decode audio back into images.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    encode_parser = subparsers.add_parser(
        "encode",
        help="Encode image to WAV audio",
    )

    encode_parser.add_argument(
        "input",
        type=Path,
        help="Input image path",
    )

    encode_parser.add_argument(
        "output",
        type=Path,
        help="Output WAV path",
    )

    encode_parser.add_argument(
        "--pixel-duration",
        type=float,
        default=DEFAULT_PIXEL_DURATION,
        help="Pixel frame duration in seconds",
    )

    encode_parser.set_defaults(func=encode_command)

    decode_parser = subparsers.add_parser(
        "decode",
        help="Decode WAV audio to image",
    )

    decode_parser.add_argument(
        "input",
        type=Path,
        help="Input WAV path",
    )

    decode_parser.add_argument(
        "output",
        type=Path,
        help="Output image path",
    )

    decode_parser.add_argument(
        "--width",
        type=int,
        required=True,
        help="Image width",
    )

    decode_parser.add_argument(
        "--height",
        type=int,
        required=True,
        help="Image height",
    )

    decode_parser.add_argument(
        "--pixel-duration",
        type=float,
        default=DEFAULT_PIXEL_DURATION,
        help="Pixel frame duration in seconds",
    )

    decode_parser.add_argument(
        "--checksum",
        type=str,
        default=None,
        help="Expected SHA256 checksum of decoded RGB pixel stream",
    )

    decode_parser.set_defaults(func=decode_command)

    return parser


def main() -> None:
    """
    CLI entrypoint.
    """
    parser = build_parser()
    args = parser.parse_args()

    args.func(args)


if __name__ == "__main__":
    main()
