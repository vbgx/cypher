from __future__ import annotations

import base64
import os
from collections.abc import Sequence
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from cypher.keys import load_private_key, load_public_key

CRYPTO_MODE_NONE = "none"
CRYPTO_MODE_X25519_AESGCM = "x25519-aesgcm"
CRYPTO_MODE_CHUNKED_X25519_AESGCM = "chunked-x25519-aesgcm"
CRYPTO_MODE_X25519_AESGCM_MULTI = "x25519-aesgcm-multi"
CRYPTO_MODE_CHUNKED_X25519_AESGCM_MULTI = "chunked-x25519-aesgcm-multi"


def derive_aes_key(shared_secret: bytes, salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"cypher-v4.9-x25519-aesgcm",
    ).derive(shared_secret)


def encrypt_payload(
    payload: bytes,
    recipient_public_key_path: str | Path,
) -> tuple[bytes, dict[str, str]]:
    print("Encrypting payload with public key...")

    recipient_public_key = load_public_key(recipient_public_key_path)

    ephemeral_private_key = x25519.X25519PrivateKey.generate()
    ephemeral_public_key = ephemeral_private_key.public_key()

    shared_secret = ephemeral_private_key.exchange(recipient_public_key)

    salt = os.urandom(16)
    nonce = os.urandom(12)

    aes_key = derive_aes_key(
        shared_secret=shared_secret,
        salt=salt,
    )

    ciphertext = AESGCM(aes_key).encrypt(
        nonce,
        payload,
        None,
    )

    ephemeral_public_bytes = ephemeral_public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    crypto_meta = {
        "crypto_mode": CRYPTO_MODE_X25519_AESGCM,
        "ephemeral_public_key": base64.b64encode(
            ephemeral_public_bytes
        ).decode("ascii"),
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_size": str(len(ciphertext)),
    }

    print(f"Ciphertext size   : {len(ciphertext):,} bytes")

    return ciphertext, crypto_meta


def decrypt_payload(
    ciphertext: bytes,
    crypto_meta: dict[str, str],
    private_key_path: str | Path,
) -> bytes:
    print("Decrypting payload with private key...")

    if "ephemeral_public_key" not in crypto_meta:
        raise ValueError("Invalid payload metadata")

    private_key = load_private_key(private_key_path)

    ephemeral_public_key = x25519.X25519PublicKey.from_public_bytes(
        base64.b64decode(crypto_meta["ephemeral_public_key"])
    )

    salt = base64.b64decode(crypto_meta["salt"])
    nonce = base64.b64decode(crypto_meta["nonce"])

    shared_secret = private_key.exchange(ephemeral_public_key)

    aes_key = derive_aes_key(
        shared_secret=shared_secret,
        salt=salt,
    )

    return AESGCM(aes_key).decrypt(
        nonce,
        ciphertext,
        None,
    )


def encrypt_payload_multi(
    payload: bytes,
    recipient_public_key_paths: Sequence[str | Path],
) -> tuple[bytes, dict[str, object]]:
    if not recipient_public_key_paths:
        raise ValueError("At least one public key is required for encryption")

    print("Encrypting payload for multiple recipients...")
    print(f"Recipients        : {len(recipient_public_key_paths)}")

    content_key = os.urandom(32)
    payload_nonce = os.urandom(12)

    ciphertext = AESGCM(content_key).encrypt(
        payload_nonce,
        payload,
        None,
    )

    recipients: list[dict[str, str]] = []

    for public_key_path in recipient_public_key_paths:
        recipient_public_key = load_public_key(public_key_path)

        ephemeral_private_key = x25519.X25519PrivateKey.generate()
        ephemeral_public_key = ephemeral_private_key.public_key()

        shared_secret = ephemeral_private_key.exchange(recipient_public_key)

        salt = os.urandom(16)
        wrap_nonce = os.urandom(12)

        wrapping_key = derive_aes_key(
            shared_secret=shared_secret,
            salt=salt,
        )

        wrapped_key = AESGCM(wrapping_key).encrypt(
            wrap_nonce,
            content_key,
            None,
        )

        ephemeral_public_bytes = ephemeral_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        recipients.append(
            {
                "ephemeral_public_key": base64.b64encode(
                    ephemeral_public_bytes
                ).decode("ascii"),
                "salt": base64.b64encode(salt).decode("ascii"),
                "wrap_nonce": base64.b64encode(wrap_nonce).decode("ascii"),
                "wrapped_key": base64.b64encode(wrapped_key).decode("ascii"),
            }
        )

    crypto_meta: dict[str, object] = {
        "crypto_mode": CRYPTO_MODE_X25519_AESGCM_MULTI,
        "nonce": base64.b64encode(payload_nonce).decode("ascii"),
        "ciphertext_size": str(len(ciphertext)),
        "recipients": recipients,
    }

    print(f"Ciphertext size   : {len(ciphertext):,} bytes")

    return ciphertext, crypto_meta


def decrypt_payload_multi(
    ciphertext: bytes,
    crypto_meta: dict[str, object],
    private_key_path: str | Path,
) -> bytes:
    print("Decrypting payload with private key...")

    recipients = crypto_meta.get("recipients")

    if not isinstance(recipients, list):
        raise ValueError("Invalid multi-recipient metadata")

    payload_nonce_raw = crypto_meta.get("nonce")

    if not isinstance(payload_nonce_raw, str):
        raise ValueError("Invalid payload nonce")

    private_key = load_private_key(private_key_path)
    payload_nonce = base64.b64decode(payload_nonce_raw)

    for recipient in recipients:
        if not isinstance(recipient, dict):
            continue

        try:
            ephemeral_public_key = x25519.X25519PublicKey.from_public_bytes(
                base64.b64decode(recipient["ephemeral_public_key"])
            )

            salt = base64.b64decode(recipient["salt"])
            wrap_nonce = base64.b64decode(recipient["wrap_nonce"])
            wrapped_key = base64.b64decode(recipient["wrapped_key"])

            shared_secret = private_key.exchange(ephemeral_public_key)

            wrapping_key = derive_aes_key(
                shared_secret=shared_secret,
                salt=salt,
            )

            content_key = AESGCM(wrapping_key).decrypt(
                wrap_nonce,
                wrapped_key,
                None,
            )

            return AESGCM(content_key).decrypt(
                payload_nonce,
                ciphertext,
                None,
            )
        except Exception:
            continue

    raise ValueError("No matching private key found for this encrypted payload")
