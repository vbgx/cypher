from __future__ import annotations

import argparse

from cypher.audio import read_audio_payload
from cypher.container import resolve_input_audio
from cypher.crypto import CRYPTO_MODE_NONE
from cypher.signatures import signature_status_for_file


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

    signature = signature_status_for_file(audio_path)

    print()
    print("Signature")
    print("---------")

    if signature is None:
        print("Status        : not signed")
    else:
        print("Status        : sidecar signature found")
        print(f"Algorithm     : {signature.algorithm}")
        print(f"Signed SHA256 : {signature.signed_sha256}")
        print(f"Fingerprint   : {signature.public_key_fingerprint}")


def recipients_command(args: argparse.Namespace) -> None:
    audio_path = resolve_input_audio(args.file)

    print("Inspecting cypher recipients...")

    crypto_meta, _payload = read_audio_payload(audio_path)
    crypto_mode = crypto_meta.get("crypto_mode", CRYPTO_MODE_NONE)

    print()
    print("Cypher recipients")
    print("-----------------")
    print(f"Audio file  : {audio_path}")
    print(f"Encryption  : {crypto_mode}")

    if crypto_mode == CRYPTO_MODE_NONE:
        print("Recipients  : none")
        print("Status      : payload is not encrypted")
        return

    recipients = crypto_meta.get("recipients")

    if not isinstance(recipients, list):
        print("Recipients  : unknown")
        print("Status      : encrypted metadata has no recipient list")
        return

    print(f"Recipients  : {len(recipients)}")

    for index, recipient in enumerate(recipients, start=1):
        if not isinstance(recipient, dict):
            print(f"- recipient {index}: invalid metadata")
            continue

        wrapped_key = recipient.get("wrapped_key", "")
        ephemeral = recipient.get("ephemeral_public_key", "")

        print(
            f"- recipient {index}: "
            f"wrapped_key={len(str(wrapped_key))} chars, "
            f"ephemeral_public_key={len(str(ephemeral))} chars"
        )
