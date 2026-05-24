from __future__ import annotations

import argparse

from cypher.audio import (
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_COMPRESSION_LEVEL,
    DEFAULT_SAMPLE_RATE,
)
from cypher.benchmark import benchmark_command
from cypher.bundle import bundle_command, unbundle_command
from cypher.inspect import inspect_command
from cypher.keys import (
    DEFAULT_PRIVATE_KEY_PATH,
    DEFAULT_PUBLIC_KEY_PATH,
    keygen_command,
)
from cypher.container import decode_command, encode_command

PROJECT_NAME = "cypher"
VERSION = "1.0.0"


def add_audio_encode_options(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument(
        "--format",
        default=DEFAULT_AUDIO_FORMAT,
        choices=["wav", "flac"],
        help="Output audio format",
    )

    command_parser.add_argument(
        "--keep-name",
        action="store_true",
        help="Keep original filename stem instead of generating an obfuscated name",
    )

    command_parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
    )

    command_parser.add_argument(
        "--compression-level",
        type=int,
        default=DEFAULT_COMPRESSION_LEVEL,
        choices=range(0, 10),
        metavar="[0-9]",
    )

    command_parser.add_argument(
        "--public-key",
        action="append",
        default=None,
        help=(
            "Encrypt for this recipient public key. "
            "Can be passed multiple times. "
            "Defaults to .keys/cypher_public.pem if present."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cypher",
        description="Encode any file into self-contained lossless audio.",
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

    keygen_parser = subparsers.add_parser(
        "keygen",
        help="Generate X25519 keypair",
    )
    keygen_parser.add_argument(
        "--private-key",
        default=str(DEFAULT_PRIVATE_KEY_PATH),
    )
    keygen_parser.add_argument(
        "--public-key",
        default=str(DEFAULT_PUBLIC_KEY_PATH),
    )
    keygen_parser.add_argument(
        "--force",
        action="store_true",
    )
    keygen_parser.set_defaults(func=keygen_command)

    encode_parser = subparsers.add_parser(
        "encode",
        help="Encode one file into audio",
    )
    encode_parser.add_argument("file")
    add_audio_encode_options(encode_parser)
    encode_parser.set_defaults(func=encode_command)

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Benchmark compression, crypto and audio payload generation",
    )
    benchmark_parser.add_argument("file")
    benchmark_parser.add_argument(
        "--compression-level",
        type=int,
        default=DEFAULT_COMPRESSION_LEVEL,
    )
    benchmark_parser.add_argument(
        "--public-key",
        action="append",
        default=None,
    )
    benchmark_parser.set_defaults(func=benchmark_command)

    bundle_parser = subparsers.add_parser(
        "bundle",
        help="Encode multiple files into one audio bundle",
    )
    bundle_parser.add_argument("files", nargs="+")
    bundle_parser.add_argument(
        "--name",
        default=None,
        help="Bundle output stem when --keep-name is used",
    )
    add_audio_encode_options(bundle_parser)
    bundle_parser.set_defaults(func=bundle_command)

    decode_parser = subparsers.add_parser(
        "decode",
        help="Decode audio back to file or bundle directory",
    )
    decode_parser.add_argument("file")
    decode_parser.add_argument("output", nargs="?", default=None)
    decode_parser.add_argument(
        "--private-key",
        default=None,
        help=(
            "Decrypt using this private key. "
            "Defaults to .keys/cypher_private.pem if present."
        ),
    )
    decode_parser.set_defaults(func=decode_command)

    unbundle_parser = subparsers.add_parser(
        "unbundle",
        help="Restore multiple files from a bundle audio container",
    )
    unbundle_parser.add_argument(
        "file",
        help="Bundle FLAC/WAV file",
    )
    unbundle_parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Optional output directory",
    )
    unbundle_parser.add_argument(
        "--private-key",
        default=None,
        help=(
            "Decrypt using this private key. "
            "Defaults to .keys/cypher_private.pem if present."
        ),
    )
    unbundle_parser.set_defaults(func=unbundle_command)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect cypher audio metadata",
    )
    inspect_parser.add_argument("file")
    inspect_parser.set_defaults(func=inspect_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
