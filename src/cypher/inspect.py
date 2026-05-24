from __future__ import annotations

import argparse

from cypher.audio import read_audio_payload
from cypher.container import resolve_input_audio
from cypher.crypto import CRYPTO_MODE_NONE


def inspect_command(args: argparse.Namespace) -> None:
    audio_path = resolve_input_audio(args.file)

    print("Inspecting cypher audio...")

    crypto_meta, payload = read_audio_payload(audio_path)

    raw_public_meta = crypto_meta.get("public", {})
    public_meta: dict[str, object] = (
        raw_public_meta
        if isinstance(raw_public_meta, dict)
        else {}
    )

    crypto_mode = crypto_meta.get(
        "crypto_mode",
        CRYPTO_MODE_NONE,
    )

    print()
    print("Cypher payload")
    print("--------------")
    print(f"Audio file     : {audio_path}")
    print(f"Encryption     : {crypto_mode}")
    print(
        "Cypher version : "
        f"{public_meta.get('cypher_version', 'unknown')}"
    )
    print(
        "Payload mode   : "
        f"{public_meta.get('payload_mode', 'unknown')}"
    )

    if crypto_mode == CRYPTO_MODE_NONE:
        print(
            "Original name  : "
            f"{public_meta.get('original_name', 'unknown')}"
        )
        print(
            "MIME type      : "
            f"{public_meta.get('mime_type', 'unknown')}"
        )
        print(
            "Raw size       : "
            f"{public_meta.get('raw_size', 'unknown')} bytes"
        )
        print(
            "Checksum       : "
            f"{public_meta.get('checksum', 'unknown')}"
        )
    else:
        print()
        print(
            "Metadata hidden "
            "(encrypted payload mode)"
        )

    print(f"Stored payload : {len(payload):,} bytes")
