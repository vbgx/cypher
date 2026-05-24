from __future__ import annotations

import argparse
import time
import zlib

from cypher.audio import (
    DEFAULT_CHUNK_SIZE,
    bytes_to_int16_samples,
)
from cypher.container import (
    PAYLOAD_MODE,
    build_container,
    compute_checksum,
    create_header,
    read_file,
    resolve_default_public_keys,
    resolve_input_file,
    split_chunks,
)
from cypher.crypto import (
    CRYPTO_MODE_NONE,
    CRYPTO_MODE_X25519_AESGCM_MULTI,
    encrypt_payload_multi,
)


def benchmark_command(
    args: argparse.Namespace,
) -> None:
    input_path = resolve_input_file(args.file)
    payload = read_file(input_path)

    print("Cypher benchmark")
    print("================")
    print(f"Input file        : {input_path}")
    print(f"Raw size          : {len(payload):,} bytes")
    print(
        f"Compression level : "
        f"{args.compression_level}"
    )
    print()

    t0 = time.perf_counter()
    checksum = compute_checksum(payload)
    t_checksum = (
        time.perf_counter() - t0
    )

    header = create_header(
        input_path=input_path,
        raw_size=len(payload),
        checksum=checksum,
        payload_mode=PAYLOAD_MODE,
    )

    t0 = time.perf_counter()

    container = build_container(
        header=header,
        payload=payload,
    )

    t_container = (
        time.perf_counter() - t0
    )

    t0 = time.perf_counter()

    compressed = zlib.compress(
        container,
        level=args.compression_level,
    )

    t_compress = (
        time.perf_counter() - t0
    )

    public_key_paths = (
        resolve_default_public_keys(
            args.public_key
        )
    )

    if public_key_paths:
        t0 = time.perf_counter()

        encrypted, _crypto_meta = (
            encrypt_payload_multi(
                payload=compressed,
                recipient_public_key_paths=(
                    public_key_paths
                ),
            )
        )

        t_crypto = (
            time.perf_counter() - t0
        )

        crypto_mode = (
            CRYPTO_MODE_X25519_AESGCM_MULTI
        )

        crypto_size = len(encrypted)

    else:
        t_crypto = 0.0
        crypto_mode = CRYPTO_MODE_NONE
        crypto_size = len(compressed)

    t0 = time.perf_counter()

    samples = bytes_to_int16_samples(
        crypto_size.to_bytes(8, "big")
        + compressed
    )

    t_audio = (
        time.perf_counter() - t0
    )

    total = (
        t_checksum
        + t_container
        + t_compress
        + t_crypto
        + t_audio
    )

    mb = len(payload) / 1024 / 1024

    throughput = (
        mb / total
        if total > 0
        else 0.0
    )

    ratio = len(compressed) / max(
        len(container),
        1,
    )

    chunk_count = len(
        split_chunks(
            container,
            DEFAULT_CHUNK_SIZE,
        )
    )

    print()
    print("Results")
    print("-------")
    print(
        f"Container size    : "
        f"{len(container):,} bytes"
    )
    print(
        f"Compressed size   : "
        f"{len(compressed):,} bytes"
    )
    print(
        f"Compression ratio : "
        f"{ratio:.2%}"
    )
    print(
        f"Chunks            : "
        f"{chunk_count}"
    )
    print(
        f"Crypto            : "
        f"{crypto_mode}"
    )
    print(
        f"Crypto size       : "
        f"{crypto_size:,} bytes"
    )
    print(
        f"Audio samples     : "
        f"{len(samples):,}"
    )
    print(
        f"Throughput        : "
        f"{throughput:.2f} MB/s"
    )
    print()

    print("Timings")
    print("-------")
    print(
        f"Checksum          : "
        f"{t_checksum:.4f}s"
    )
    print(
        f"Container build   : "
        f"{t_container:.4f}s"
    )
    print(
        f"Compression       : "
        f"{t_compress:.4f}s"
    )
    print(
        f"Crypto            : "
        f"{t_crypto:.4f}s"
    )
    print(
        f"Audio generation  : "
        f"{t_audio:.4f}s"
    )
    print(
        f"Total             : "
        f"{total:.4f}s"
    )
