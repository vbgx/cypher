from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from LocalAuthentication import (
    LAContext,
    LAPolicyDeviceOwnerAuthenticationWithBiometrics,
)

import cypher.audio as audio_mod
import cypher.benchmark as benchmark_mod
import cypher.bundle as bundle_mod
import cypher.cli as cli_mod
import cypher.container as container_mod
import cypher.crypto as crypto_mod
import cypher.inspect as inspect_mod
import cypher.keys as keys_mod

from cypher.audio import *
from cypher.benchmark import *
from cypher.bundle import *
from cypher.cli import *
from cypher.container import *
from cypher.crypto import *
from cypher.inspect import *
from cypher.keys import *

PROJECT_NAME = "cypher"
VERSION = "1.0.0"

DATA_DIR = Path("data")
INPUT_DIR = DATA_DIR / "input"
AUDIO_DIR = DATA_DIR / "audio"
BUNDLE_AUDIO_DIR = AUDIO_DIR / "bundle"
OUTPUT_DIR = DATA_DIR / "output"
WAVEFORM_DIR = OUTPUT_DIR / "waveforms"

KEYS_DIR = Path(".keys")
DEFAULT_PRIVATE_KEY_PATH = KEYS_DIR / "cypher_private.pem"
DEFAULT_PUBLIC_KEY_PATH = KEYS_DIR / "cypher_public.pem"


def _sync_runtime_config() -> None:
    audio_mod.DATA_DIR = DATA_DIR
    audio_mod.AUDIO_DIR = AUDIO_DIR
    audio_mod.BUNDLE_AUDIO_DIR = BUNDLE_AUDIO_DIR
    audio_mod.OUTPUT_DIR = OUTPUT_DIR
    audio_mod.WAVEFORM_DIR = WAVEFORM_DIR

    container_mod.DATA_DIR = DATA_DIR
    container_mod.INPUT_DIR = INPUT_DIR
    container_mod.AUDIO_DIR = AUDIO_DIR
    container_mod.BUNDLE_AUDIO_DIR = BUNDLE_AUDIO_DIR
    container_mod.OUTPUT_DIR = OUTPUT_DIR
    container_mod.DEFAULT_PRIVATE_KEY_PATH = DEFAULT_PRIVATE_KEY_PATH
    container_mod.DEFAULT_PUBLIC_KEY_PATH = DEFAULT_PUBLIC_KEY_PATH

    bundle_mod.BUNDLE_AUDIO_DIR = BUNDLE_AUDIO_DIR

    keys_mod.DEFAULT_PRIVATE_KEY_PATH = DEFAULT_PRIVATE_KEY_PATH
    keys_mod.DEFAULT_PUBLIC_KEY_PATH = DEFAULT_PUBLIC_KEY_PATH

    container_mod.resolve_input_file = resolve_input_file
    container_mod.resolve_input_audio = resolve_input_audio
    container_mod.resolve_audio_output = resolve_audio_output
    container_mod.resolve_decoded_output = resolve_decoded_output
    container_mod.resolve_bundle_output_dir = resolve_bundle_output_dir
    container_mod.resolve_default_public_key = resolve_default_public_key
    container_mod.resolve_default_public_keys = resolve_default_public_keys
    container_mod.resolve_default_private_key = resolve_default_private_key

    bundle_mod.resolve_input_file = resolve_input_file
    bundle_mod.resolve_audio_output = resolve_audio_output
    bundle_mod.resolve_bundle_output_dir = resolve_bundle_output_dir

    inspect_mod.resolve_input_audio = resolve_input_audio
    inspect_mod.read_audio_payload = read_audio_payload

    benchmark_mod.resolve_default_public_keys = resolve_default_public_keys

    crypto_mod.load_public_key = load_public_key
    crypto_mod.load_private_key = load_private_key

    keys_mod.save_private_key_password_to_keychain = save_private_key_password_to_keychain
    keys_mod.load_private_key_password_from_keychain = load_private_key_password_from_keychain
    keys_mod.delete_private_key_password_from_keychain = delete_private_key_password_from_keychain


def resolve_input_file(path: str | Path) -> Path:
    candidate = Path(path)

    if candidate.exists():
        return candidate

    candidate = INPUT_DIR / Path(path)

    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Input file not found: {path}")


def resolve_input_audio(path: str | Path) -> Path:
    candidate = Path(path)

    if candidate.exists():
        return candidate

    candidate = AUDIO_DIR / Path(path)

    if candidate.exists():
        return candidate

    candidate = BUNDLE_AUDIO_DIR / Path(path)

    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Audio file not found: {path}")


def resolve_audio_output(
    input_path: Path,
    audio_format: str,
    obfuscate_name: bool = True,
) -> Path:
    audio_mod.AUDIO_DIR = AUDIO_DIR
    return audio_mod.resolve_audio_output(
        input_path=input_path,
        audio_format=audio_format,
        obfuscate_name=obfuscate_name,
    )


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


def resolve_bundle_output_dir(
    output_name: str | None,
    bundle_name: str | None = None,
) -> Path:
    if output_name is not None:
        output_path = Path(output_name)

        if output_path.parent != Path("."):
            return output_path

        return OUTPUT_DIR / output_name

    if bundle_name:
        return OUTPUT_DIR / bundle_name

    return OUTPUT_DIR / DEFAULT_BUNDLE_NAME


def resolve_default_public_key(args_public_key: str | None) -> str | None:
    if args_public_key is not None:
        return args_public_key

    if DEFAULT_PUBLIC_KEY_PATH.exists():
        return str(DEFAULT_PUBLIC_KEY_PATH)

    return None


def resolve_default_public_keys(args_public_keys) -> list[str]:
    if args_public_keys:
        return list(args_public_keys)

    return []


def resolve_default_private_key(args_private_key: str | None) -> str | None:
    if args_private_key is not None:
        return args_private_key

    if DEFAULT_PRIVATE_KEY_PATH.exists():
        return str(DEFAULT_PRIVATE_KEY_PATH)

    return None


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


def load_private_key(path: str | Path) -> x25519.X25519PrivateKey:
    password = load_private_key_password_from_keychain()

    if password is None:
        raise ValueError(
            "Private key password not found in macOS Keychain. "
            "Run make keygen-force or restore the Keychain item."
        )

    key = serialization.load_pem_private_key(
        Path(path).read_bytes(),
        password=password.encode("utf-8"),
    )

    if not isinstance(key, x25519.X25519PrivateKey):
        raise TypeError("Private key must be an X25519 private key")

    return key


def require_touch_id(reason: str) -> None:
    context = LAContext.alloc().init()

    can_evaluate, error = context.canEvaluatePolicy_error_(
        LAPolicyDeviceOwnerAuthenticationWithBiometrics,
        None,
    )

    if not can_evaluate:
        raise PermissionError(
            "Touch ID is not available or no fingerprint is enrolled."
        )

    done = threading.Event()
    result: dict[str, object] = {
        "success": False,
        "error": None,
    }

    def reply(success: bool, auth_error: object) -> None:
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
            f"Touch ID authentication failed: {result['error']}"
        )


def keygen_command(args: argparse.Namespace) -> None:
    generate_keypair(
        private_key_path=Path(args.private_key),
        public_key_path=Path(args.public_key),
        force=args.force,
    )


def encrypt_payload(payload: bytes, recipient_public_key_path: str | Path):
    _sync_runtime_config()
    return crypto_mod.encrypt_payload(payload, recipient_public_key_path)


def decrypt_payload(ciphertext: bytes, crypto_meta: dict[str, str], private_key_path: str | Path):
    _sync_runtime_config()
    return crypto_mod.decrypt_payload(ciphertext, crypto_meta, private_key_path)


def encrypt_payload_multi(payload: bytes, recipient_public_key_paths):
    _sync_runtime_config()
    return crypto_mod.encrypt_payload_multi(payload, recipient_public_key_paths)


def decrypt_payload_multi(ciphertext: bytes, crypto_meta: dict[str, object], private_key_path: str | Path):
    _sync_runtime_config()
    return crypto_mod.decrypt_payload_multi(ciphertext, crypto_meta, private_key_path)


def encode_command(args: argparse.Namespace) -> None:
    _sync_runtime_config()
    container_mod.encode_command(args)



def decode_chunked_payload(payload: bytes, private_key: str | None):
    original_decrypt_payload = container_mod.decrypt_payload
    original_decrypt_payload_multi = container_mod.decrypt_payload_multi

    try:
        container_mod.decrypt_payload = decrypt_payload
        container_mod.decrypt_payload_multi = decrypt_payload_multi

        from cypher.container import decode_chunked_payload as _decode_chunked_payload

        return _decode_chunked_payload(
            payload,
            private_key,
        )

    finally:
        container_mod.decrypt_payload = original_decrypt_payload
        container_mod.decrypt_payload_multi = original_decrypt_payload_multi


_ORIGINAL_CONTAINER_DECODE_CHUNKED = container_mod.decode_chunked_payload

def decode_chunked_payload(payload: bytes, private_key: str | None):
    original_decrypt_payload = container_mod.decrypt_payload
    original_decrypt_payload_multi = container_mod.decrypt_payload_multi

    try:
        container_mod.decrypt_payload = decrypt_payload
        container_mod.decrypt_payload_multi = decrypt_payload_multi

        return _ORIGINAL_CONTAINER_DECODE_CHUNKED(
            payload,
            private_key,
        )

    finally:
        container_mod.decrypt_payload = original_decrypt_payload
        container_mod.decrypt_payload_multi = original_decrypt_payload_multi


def decode_command(args: argparse.Namespace) -> None:
    _sync_runtime_config()

    container_mod.read_audio_payload = read_audio_payload
    container_mod.decode_chunked_payload = decode_chunked_payload
    container_mod.parse_container = parse_container
    container_mod.compute_checksum = compute_checksum
    container_mod.verify_checksum = verify_checksum
    container_mod.resolve_input_audio = resolve_input_audio
    container_mod.resolve_default_private_key = resolve_default_private_key
    container_mod.require_touch_id = require_touch_id
    container_mod.decrypt_payload = decrypt_payload
    container_mod.decrypt_payload_multi = decrypt_payload_multi

    container_mod.decode_command(args)


def bundle_command(args: argparse.Namespace) -> None:
    _sync_runtime_config()
    bundle_mod.bundle_command(args)


def unbundle_command(args: argparse.Namespace) -> None:
    _sync_runtime_config()
    decode_command(args)


def inspect_command(args: argparse.Namespace) -> None:
    _sync_runtime_config()
    inspect_mod.inspect_command(args)


def benchmark_command(args: argparse.Namespace) -> None:
    _sync_runtime_config()
    benchmark_mod.benchmark_command(args)


def build_parser() -> argparse.ArgumentParser:
    _sync_runtime_config()
    parser = cli_mod.build_parser()

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for subparser in action.choices.values():
                defaults = getattr(subparser, "_defaults", {})
                func = defaults.get("func")

                if func is keys_mod.keygen_command:
                    subparser.set_defaults(func=keygen_command)
                elif func is container_mod.encode_command:
                    subparser.set_defaults(func=encode_command)
                elif func is benchmark_mod.benchmark_command:
                    subparser.set_defaults(func=benchmark_command)
                elif func is bundle_mod.bundle_command:
                    subparser.set_defaults(func=bundle_command)
                elif func is container_mod.decode_command:
                    subparser.set_defaults(func=decode_command)
                elif func is bundle_mod.unbundle_command:
                    subparser.set_defaults(func=unbundle_command)
                elif func is inspect_mod.inspect_command:
                    subparser.set_defaults(func=inspect_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)



def read_audio_payload(path):
    sample_rate, samples = read_audio(path)
    audio_payload = int16_samples_to_bytes(samples)
    return parse_audio_payload(audio_payload)

if __name__ == "__main__":
    main()
