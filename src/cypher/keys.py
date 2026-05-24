from __future__ import annotations

import argparse
import secrets
import subprocess
import threading
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from LocalAuthentication import (
    LAContext,
    LAPolicyDeviceOwnerAuthenticationWithBiometrics,
)

PRIVATE_KEY_PASSWORD_BYTES = 32

KEYS_DIR = Path(".keys")

DEFAULT_PRIVATE_KEY_PATH = KEYS_DIR / "cypher_private.pem"
DEFAULT_PUBLIC_KEY_PATH = KEYS_DIR / "cypher_public.pem"

KEYCHAIN_SERVICE = "cypher"
KEYCHAIN_PRIVATE_KEY_ACCOUNT = "cypher_private_key_password"

TOUCH_ID_DECODE_REASON = (
    "En attente ton empreinte digitale pour déchiffrer le fichier."
)

TOUCH_ID_UNBUNDLE_REASON = (
    "En attente ton empreinte digitale pour restaurer le bundle."
)


def generate_private_key_password() -> str:
    return secrets.token_urlsafe(PRIVATE_KEY_PASSWORD_BYTES)


def save_private_key_password_to_keychain(password: str) -> None:
    subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            KEYCHAIN_PRIVATE_KEY_ACCOUNT,
            "-w",
            password,
        ],
        check=True,
    )


def load_private_key_password_from_keychain() -> str | None:
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            KEYCHAIN_PRIVATE_KEY_ACCOUNT,
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    password = result.stdout.strip()
    return password or None


def delete_private_key_password_from_keychain() -> None:
    subprocess.run(
        [
            "security",
            "delete-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            KEYCHAIN_PRIVATE_KEY_ACCOUNT,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def generate_keypair(
    private_key_path: Path = DEFAULT_PRIVATE_KEY_PATH,
    public_key_path: Path = DEFAULT_PUBLIC_KEY_PATH,
    force: bool = False,
) -> None:
    if not force:
        existing = [
            path
            for path in [private_key_path, public_key_path]
            if path.exists()
        ]

        if existing:
            raise FileExistsError(
                "Key file already exists. Use --force to overwrite:\n"
                + "\n".join(str(path) for path in existing)
            )
    else:
        delete_private_key_password_from_keychain()

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)

    password = generate_private_key_password()

    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(
            password.encode("utf-8")
        ),
    )

    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.write_bytes(private_bytes)
    public_key_path.write_bytes(public_bytes)

    save_private_key_password_to_keychain(password)

    print("Keypair generated.")
    print(f"Private key: {private_key_path}")
    print(f"Public key : {public_key_path}")
    print("Password   : stored in macOS Keychain")
    print()
    print("Private PEM is encrypted at rest.")
    print("Touch ID / macOS authentication depends on your Keychain policy.")


def load_public_key(path: str | Path) -> x25519.X25519PublicKey:
    key = serialization.load_pem_public_key(
        Path(path).read_bytes()
    )

    if not isinstance(key, x25519.X25519PublicKey):
        raise TypeError(
            "Public key must be an X25519 public key"
        )

    return key


def load_private_key(
    path: str | Path,
) -> x25519.X25519PrivateKey:
    password = load_private_key_password_from_keychain()

    if password is None:
        raise ValueError(
            "Private key password not found in macOS Keychain. "
            "The encrypted private PEM exists, but Cypher cannot unlock it. "
            "Run `cypher keygen --force` to create a new local keypair, "
            "or restore the missing Keychain item."
        )

    key = serialization.load_pem_private_key(
        Path(path).read_bytes(),
        password=password.encode("utf-8"),
    )

    if not isinstance(key, x25519.X25519PrivateKey):
        raise TypeError(
            "Private key must be an X25519 private key"
        )

    return key


def require_touch_id(reason: str) -> None:
    context = LAContext.alloc().init()

    can_evaluate, error = (
        context.canEvaluatePolicy_error_(
            LAPolicyDeviceOwnerAuthenticationWithBiometrics,
            None,
        )
    )

    if not can_evaluate:
        raise PermissionError(
            "Touch ID is not available or no fingerprint is enrolled. "
            "On macOS, enable Touch ID for this user or adjust Keychain access. "
            f"System detail: {error}"
        )

    done = threading.Event()

    result: dict[str, object] = {
        "success": False,
        "error": None,
    }

    def reply(
        success: bool,
        auth_error: object,
    ) -> None:
        result["success"] = bool(success)
        result["error"] = auth_error
        done.set()

    context.evaluatePolicy_localizedReason_reply_(
        LAPolicyDeviceOwnerAuthenticationWithBiometrics,
        reason,
        reply,
    )

    done.wait()

    if not bool(result["success"]):
        raise PermissionError(
            "Touch ID authentication failed or was cancelled. "
            "The private key was not unlocked. "
            f"System detail: {result['error']}"
        )



def public_key_fingerprint(path: str | Path) -> str:
    public_key = load_public_key(path)
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    digest = hashes.Hash(hashes.SHA256())
    digest.update(raw)
    fingerprint = digest.finalize().hex()
    return ":".join(
        fingerprint[index : index + 2]
        for index in range(0, len(fingerprint), 2)
    )


def key_info_command(args: argparse.Namespace) -> None:
    key_path = Path(args.file)
    fingerprint = public_key_fingerprint(key_path)

    print("Cypher public key")
    print("-----------------")
    print(f"File        : {key_path}")
    print("Type        : X25519 public key")
    print(f"Fingerprint : {fingerprint}")


def keygen_command(
    args: argparse.Namespace,
) -> None:
    generate_keypair(
        private_key_path=Path(args.private_key),
        public_key_path=Path(args.public_key),
        force=args.force,
    )
