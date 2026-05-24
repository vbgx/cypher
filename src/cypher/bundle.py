from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from cypher.audio import BUNDLE_AUDIO_DIR, resolve_audio_output
from cypher.container import (
    BUNDLE_PAYLOAD_MODE,
    DEFAULT_BUNDLE_NAME,
    CHECKSUM_ALGORITHM,
    CypherHeader,
    build_container,
    compute_checksum,
    create_header,
    emit_progress,
    encode_container_to_audio,
    read_file,
    resolve_bundle_output_dir,
    resolve_input_file,
    safe_relative_path,
    unique_output_path,
    validate_header,
    verify_checksum,
    write_file,
)

BUNDLE_MAGIC = b"CYPHERBUNDLE47"
BUNDLE_VERSION = 100


@dataclass(frozen=True)
class BundleHeader:
    files_count: int
    magic: str = "CYPHER_BUNDLE"
    version: int = BUNDLE_VERSION
    checksum_algorithm: str = CHECKSUM_ALGORITHM


def validate_bundle_header(header: BundleHeader) -> None:
    if header.magic != "CYPHER_BUNDLE":
        raise ValueError(f"Invalid bundle magic: {header.magic}")

    if header.version != BUNDLE_VERSION:
        raise ValueError(f"Unsupported bundle version: {header.version}")

    if header.files_count < 1:
        raise ValueError("Bundle must contain at least one file")


def build_bundle_container(files: list[tuple[CypherHeader, bytes]]) -> bytes:
    if not files:
        raise ValueError("Bundle requires at least one file")

    bundle_header = BundleHeader(files_count=len(files))
    validate_bundle_header(bundle_header)

    bundle_header_bytes = json.dumps(
        asdict(bundle_header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    payload = BUNDLE_MAGIC
    payload += len(bundle_header_bytes).to_bytes(8, "big")
    payload += bundle_header_bytes

    total_files = len(files)

    for index, (header, file_payload) in enumerate(files, start=1):
        emit_progress(
            phase="files",
            current=index,
            total=total_files,
        )

        validate_header(header)

        if len(file_payload) != header.raw_size:
            raise ValueError(
                f"Invalid bundled payload size for {header.original_name}: "
                f"expected {header.raw_size}, got {len(file_payload)}"
            )

        actual_checksum = compute_checksum(file_payload)

        if not verify_checksum(header.checksum, actual_checksum):
            raise ValueError(
                f"Checksum mismatch before bundling {header.original_name}: "
                f"expected {header.checksum}, got {actual_checksum}"
            )

        header_bytes = json.dumps(
            asdict(header),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        payload += len(header_bytes).to_bytes(8, "big")
        payload += header_bytes
        payload += len(file_payload).to_bytes(8, "big")
        payload += file_payload

    return payload


def is_bundle_container(payload: bytes) -> bool:
    return payload.startswith(BUNDLE_MAGIC)


def parse_bundle_container(payload: bytes) -> list[tuple[CypherHeader, bytes]]:
    from cypher.container import decode_header

    cursor = 0

    if payload[: len(BUNDLE_MAGIC)] != BUNDLE_MAGIC:
        raise ValueError("Invalid cypher bundle magic")

    cursor += len(BUNDLE_MAGIC)

    bundle_header_size = int.from_bytes(payload[cursor : cursor + 8], "big")
    cursor += 8

    bundle_header = BundleHeader(
        **json.loads(payload[cursor : cursor + bundle_header_size].decode("utf-8"))
    )
    validate_bundle_header(bundle_header)

    cursor += bundle_header_size

    files: list[tuple[CypherHeader, bytes]] = []

    for _index in range(bundle_header.files_count):
        header_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        header = decode_header(payload[cursor : cursor + header_size])
        cursor += header_size

        file_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        file_payload = payload[cursor : cursor + file_size]
        cursor += file_size

        if len(file_payload) != header.raw_size:
            raise ValueError(
                f"Invalid bundled payload size for {header.original_name}: "
                f"expected {header.raw_size}, got {len(file_payload)}"
            )

        actual_checksum = compute_checksum(file_payload)

        if not verify_checksum(header.checksum, actual_checksum):
            raise ValueError(
                f"Checksum mismatch for bundled file {header.original_name}: "
                f"expected {header.checksum}, got {actual_checksum}"
            )

        files.append((header, file_payload))

    if cursor != len(payload):
        raise ValueError("Unexpected trailing bytes after bundle payload")

    return files


def restore_bundle_payload(
    audio_path: Path,
    restored_payload: bytes,
    bundle_checksum: str,
    output_dir: Path | None = None,
    bundle_name: str | None = None,
) -> None:
    files = parse_bundle_container(restored_payload)

    inferred_root = bundle_name

    if inferred_root is None:
        roots = {
            Path(file_header.relative_path).parts[0]
            for file_header, _file_payload in files
            if file_header.relative_path
            and len(Path(file_header.relative_path).parts) > 1
        }

        if len(roots) == 1:
            inferred_root = next(iter(roots))

    if output_dir is None:
        output_dir = resolve_bundle_output_dir(
            None,
            inferred_root,
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Decode completed: bundle detected.")
    print(f"Audio             : {audio_path}")
    print(f"Output directory  : {output_dir}")
    print(f"Files count       : {len(files)}")
    print(f"Bundle checksum   : {bundle_checksum}")

    for file_header, file_payload in files:
        restore_name = file_header.relative_path or file_header.original_name
        restore_path = Path(restore_name)

        if restore_path.is_absolute() or ".." in restore_path.parts:
            raise ValueError(
                f"Unsafe restore path in bundle: {restore_name}"
            )

        if (
            inferred_root
            and restore_path.parts
            and restore_path.parts[0] == inferred_root
        ):
            restore_path = Path(*restore_path.parts[1:])

        target_dir = output_dir / restore_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        output_path = unique_output_path(
            target_dir,
            restore_path.name,
        )

        write_file(
            path=output_path,
            payload=file_payload,
        )

        print(f"- restored         : {output_path}")


def bundle_command(args: argparse.Namespace) -> None:
    print("Starting multi-file bundle encode...")

    raw_inputs = [
        Path(file_arg)
        for file_arg in args.files
    ]

    input_paths: list[Path] = []
    directory_roots: list[Path] = []

    for path in raw_inputs:
        resolved = resolve_input_file(path)

        if resolved.is_file():
            input_paths.append(resolved)
            continue

        if resolved.is_dir():
            directory_roots.append(resolved)

            files = sorted(
                child
                for child in resolved.rglob("*")
                if child.is_file()
            )

            input_paths.extend(files)
            continue

        raise ValueError(f"Unsupported path: {resolved}")

    if not input_paths:
        raise ValueError("Bundle is empty.")

    print(f"Files count       : {len(input_paths)}")

    if len(directory_roots) == 1 and len(raw_inputs) == 1:
        common_root = directory_roots[0].parent
        bundle_root_name = directory_roots[0].name
    else:
        try:
            common_root = Path(
                os.path.commonpath(
                    [
                        str(path.parent)
                        for path in input_paths
                    ]
                )
            )
        except ValueError:
            common_root = Path.cwd()

        bundle_root_name = common_root.name

    bundle_entries: list[tuple[CypherHeader, bytes]] = []
    total_size = 0
    total_files = len(input_paths)

    for index, input_path in enumerate(input_paths, start=1):
        emit_progress(
            phase="scan",
            current=index,
            total=total_files,
        )

        payload = read_file(input_path)
        checksum = compute_checksum(payload)

        try:
            relative_path = safe_relative_path(
                input_path.relative_to(common_root)
            )
        except ValueError:
            relative_path = input_path.name

        header = create_header(
            input_path=input_path,
            raw_size=len(payload),
            checksum=checksum,
            payload_mode="ANY_FILE_SELF_CONTAINED_AUDIO",
            relative_path=relative_path,
        )

        bundle_entries.append((header, payload))
        total_size += len(payload)

        print(
            f"- {relative_path} "
            f"({len(payload):,} bytes, {header.mime_type})"
        )

    print(f"Total raw size    : {total_size:,} bytes")

    emit_progress(
        phase="container",
        current=0,
        total=1,
    )

    bundle_payload = build_bundle_container(bundle_entries)

    emit_progress(
        phase="container",
        current=1,
        total=1,
    )

    bundle_name = args.name or bundle_root_name or DEFAULT_BUNDLE_NAME

    bundle_header = create_header(
        input_path=Path(f"{bundle_name}.cypherbundle"),
        raw_size=len(bundle_payload),
        checksum=compute_checksum(bundle_payload),
        payload_mode=BUNDLE_PAYLOAD_MODE,
        relative_path=bundle_name,
    )

    wrapped_container = build_container(
        header=bundle_header,
        payload=bundle_payload,
    )

    output_path = resolve_audio_output(
        input_path=Path(bundle_name),
        audio_format=args.format,
        obfuscate_name=not args.keep_name,
    )

    output_path = BUNDLE_AUDIO_DIR / output_path.name

    print(f"Bundle name       : {bundle_name}")
    print(f"Bundle size       : {len(bundle_payload):,} bytes")
    print(f"Sample rate       : {args.sample_rate} Hz")

    encode_container_to_audio(
        container=wrapped_container,
        header=bundle_header,
        output_path=output_path,
        sample_rate=args.sample_rate,
        compression_level=args.compression_level,
        public_key=args.public_key,
    )


def unbundle_command(args: argparse.Namespace) -> None:
    from cypher.container import decode_command

    decode_command(args)
