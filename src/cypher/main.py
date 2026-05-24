from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import secrets
import subprocess
import zlib
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np
import soundfile as sf
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from tqdm import tqdm

import threading

from LocalAuthentication import (
    LAContext,
    LAPolicyDeviceOwnerAuthenticationWithBiometrics,
)


PROJECT_NAME = "cypher"
VERSION = "0.4.9"

MAGIC = "CYPHER"
CONTAINER_MAGIC = b"CYPHER45"
AUDIO_MAGIC = b"CYPHERAUDIO49"
BUNDLE_MAGIC = b"CYPHERBUNDLE47"

HEADER_VERSION = 45
BUNDLE_VERSION = 47

PAYLOAD_MODE = "ANY_FILE_SELF_CONTAINED_AUDIO"
BUNDLE_PAYLOAD_MODE = "MULTI_FILE_SELF_CONTAINED_AUDIO"
STREAMING_PAYLOAD_MODE = "CHUNKED_STREAM"

CHECKSUM_ALGORITHM = "SHA256"
COMPRESSION_ALGORITHM = "zlib"

CRYPTO_MODE_NONE = "none"
CRYPTO_MODE_X25519_AESGCM = "x25519-aesgcm"
CRYPTO_MODE_CHUNKED_X25519_AESGCM = "chunked-x25519-aesgcm"

DEFAULT_SAMPLE_RATE = 44_100
DEFAULT_AUDIO_FORMAT = "flac"
DEFAULT_COMPRESSION_LEVEL = 9
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024
DEFAULT_OBFUSCATED_NAME_LENGTH = 24
PRIVATE_KEY_PASSWORD_BYTES = 32

LOSSLESS_AUDIO_OUTPUT = {".wav", ".flac"}
UNSAFE_AUDIO_OUTPUT = {".mp3"}

DATA_DIR = Path("data")
INPUT_DIR = DATA_DIR / "input"
AUDIO_DIR = DATA_DIR / "audio"
BUNDLE_AUDIO_DIR = AUDIO_DIR / "bundle"
OUTPUT_DIR = DATA_DIR / "output"

KEYS_DIR = Path(".keys")
DEFAULT_PRIVATE_KEY_PATH = KEYS_DIR / "cypher_private.pem"
DEFAULT_PUBLIC_KEY_PATH = KEYS_DIR / "cypher_public.pem"

DEFAULT_BUNDLE_NAME = "bundle"

KEYCHAIN_SERVICE = "cypher"
KEYCHAIN_PRIVATE_KEY_ACCOUNT = "cypher_private_key_password"

TOUCH_ID_DECODE_REASON = "En attente ton empreinte digitale pour déchiffrer le fichier."
TOUCH_ID_UNBUNDLE_REASON = "En attente ton empreinte digitale pour restaurer le bundle."


@dataclass(frozen=True)
class CypherHeader:
    original_name: str
    original_suffix: str
    mime_type: str
    raw_size: int
    checksum: str
    magic: str = MAGIC
    version: int = HEADER_VERSION
    payload_mode: str = PAYLOAD_MODE
    checksum_algorithm: str = CHECKSUM_ALGORITHM
    compression_algorithm: str = COMPRESSION_ALGORITHM


@dataclass(frozen=True)
class BundleHeader:
    files_count: int
    magic: str = "CYPHER_BUNDLE"
    version: int = BUNDLE_VERSION
    checksum_algorithm: str = CHECKSUM_ALGORITHM


@dataclass(frozen=True)
class ChunkHeader:
    index: int
    total_chunks: int
    raw_size: int
    compressed_size: int
    encrypted: bool


def compute_checksum(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def verify_checksum(expected: str, actual: str) -> bool:
    return expected.lower() == actual.lower()


def generate_obfuscated_stem(length: int = DEFAULT_OBFUSCATED_NAME_LENGTH) -> str:
    return secrets.token_urlsafe(length)[:length]


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


def read_file(path: str | Path) -> bytes:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    return file_path.read_bytes()


def write_file(path: str | Path, payload: bytes) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)


def detect_mime_type(path: str | Path) -> str:
    mime_type, _encoding = mimetypes.guess_type(Path(path).name)
    return mime_type or "application/octet-stream"


def create_header(
    input_path: str | Path,
    raw_size: int,
    checksum: str,
    payload_mode: str = PAYLOAD_MODE,
) -> CypherHeader:
    path = Path(input_path)

    header = CypherHeader(
        original_name=path.name,
        original_suffix=path.suffix,
        mime_type=detect_mime_type(path),
        raw_size=raw_size,
        checksum=checksum,
        payload_mode=payload_mode,
    )

    validate_header(header)
    return header


def validate_header(header: CypherHeader) -> None:
    if header.magic != MAGIC:
        raise ValueError(f"Invalid magic: {header.magic}")

    if header.version != HEADER_VERSION:
        raise ValueError(f"Unsupported version: {header.version}")

    if header.payload_mode not in {PAYLOAD_MODE, BUNDLE_PAYLOAD_MODE}:
        raise ValueError(f"Unsupported payload mode: {header.payload_mode}")

    if header.raw_size < 0:
        raise ValueError("Invalid raw size")

    if not header.original_name:
        raise ValueError("Original filename cannot be empty")

    if not header.checksum:
        raise ValueError("Checksum cannot be empty")


def encode_header(header: CypherHeader) -> bytes:
    validate_header(header)
    return json.dumps(
        asdict(header),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_header(payload: bytes) -> CypherHeader:
    header = CypherHeader(**json.loads(payload.decode("utf-8")))
    validate_header(header)
    return header


def build_container(header: CypherHeader, payload: bytes) -> bytes:
    header_bytes = encode_header(header)
    header_size = len(header_bytes).to_bytes(8, byteorder="big")

    return CONTAINER_MAGIC + header_size + header_bytes + payload


def parse_container(container: bytes) -> tuple[CypherHeader, bytes]:
    magic_size = len(CONTAINER_MAGIC)

    if container[:magic_size] != CONTAINER_MAGIC:
        raise ValueError("Invalid cypher container magic")

    header_size_start = magic_size
    header_size_end = header_size_start + 8

    header_size = int.from_bytes(
        container[header_size_start:header_size_end],
        byteorder="big",
    )

    header_start = header_size_end
    header_end = header_start + header_size

    header = decode_header(container[header_start:header_end])
    payload = container[header_end:]

    if len(payload) != header.raw_size:
        raise ValueError(
            f"Invalid payload size: expected {header.raw_size}, got {len(payload)}"
        )

    return header, payload


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

    for header, file_payload in files:
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

        header_bytes = encode_header(header)

        payload += len(header_bytes).to_bytes(8, "big")
        payload += header_bytes
        payload += len(file_payload).to_bytes(8, "big")
        payload += file_payload

    return payload


def is_bundle_container(payload: bytes) -> bool:
    return payload.startswith(BUNDLE_MAGIC)


def parse_bundle_container(payload: bytes) -> list[tuple[CypherHeader, bytes]]:
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
    key = serialization.load_pem_public_key(Path(path).read_bytes())

    if not isinstance(key, x25519.X25519PublicKey):
        raise TypeError("Public key must be an X25519 public key")

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
    result = {
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

    if not result["success"]:
        raise PermissionError(
            f"Touch ID authentication failed: {result['error']}"
        )

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
        "ephemeral_public_key": base64.b64encode(ephemeral_public_bytes).decode("ascii"),
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


def build_audio_payload(
    payload: bytes,
    header: CypherHeader,
    crypto_meta: dict[str, str] | None = None,
) -> bytes:
    meta = crypto_meta or {"crypto_mode": CRYPTO_MODE_NONE}
    crypto_mode = meta["crypto_mode"]

    if crypto_mode == CRYPTO_MODE_NONE:
        public_meta = {
            "cypher_version": VERSION,
            "original_name": header.original_name,
            "original_suffix": header.original_suffix,
            "mime_type": header.mime_type,
            "raw_size": str(header.raw_size),
            "checksum": header.checksum,
            "payload_mode": header.payload_mode,
            "compression_algorithm": COMPRESSION_ALGORITHM,
        }
    else:
        public_meta = {
            "cypher_version": VERSION,
            "payload_mode": "ENCRYPTED_CONTAINER",
            "compression_algorithm": COMPRESSION_ALGORITHM,
        }

    meta = {**meta, "public": public_meta}

    meta_bytes = json.dumps(
        meta,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    meta_size = len(meta_bytes).to_bytes(8, byteorder="big")
    payload_size = len(payload).to_bytes(8, byteorder="big")

    return AUDIO_MAGIC + meta_size + payload_size + meta_bytes + payload


def parse_audio_payload(audio_payload: bytes) -> tuple[dict[str, str], bytes]:
    magic_size = len(AUDIO_MAGIC)

    if audio_payload[:magic_size] != AUDIO_MAGIC:
        raise ValueError("Invalid cypher audio magic")

    meta_size_start = magic_size
    meta_size_end = meta_size_start + 8

    payload_size_start = meta_size_end
    payload_size_end = payload_size_start + 8

    meta_size = int.from_bytes(
        audio_payload[meta_size_start:meta_size_end],
        byteorder="big",
    )

    payload_size = int.from_bytes(
        audio_payload[payload_size_start:payload_size_end],
        byteorder="big",
    )

    meta_start = payload_size_end
    meta_end = meta_start + meta_size

    payload_start = meta_end
    payload_end = payload_start + payload_size

    meta = json.loads(audio_payload[meta_start:meta_end].decode("utf-8"))
    payload = audio_payload[payload_start:payload_end]

    if len(payload) != payload_size:
        raise ValueError(
            f"Invalid audio payload size: expected {payload_size}, got {len(payload)}"
        )

    return meta, payload


def resolve_audio_output(
    input_path: Path,
    audio_format: str,
    obfuscate_name: bool = True,
) -> Path:
    suffix = audio_format if audio_format.startswith(".") else f".{audio_format}"

    if suffix in UNSAFE_AUDIO_OUTPUT:
        raise ValueError(
            "MP3 is lossy and cannot preserve arbitrary files bit-perfect. "
            "Use WAV or FLAC."
        )

    if suffix not in LOSSLESS_AUDIO_OUTPUT:
        raise ValueError(f"Unsupported audio format: {suffix}")

    stem = generate_obfuscated_stem() if obfuscate_name else input_path.stem

    return AUDIO_DIR / f"{stem}{suffix}"


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


def resolve_bundle_output_dir(output_name: str | None) -> Path:
    if output_name is not None:
        output_path = Path(output_name)

        if output_path.parent != Path("."):
            return output_path

        return OUTPUT_DIR / output_name

    return OUTPUT_DIR / DEFAULT_BUNDLE_NAME


def unique_output_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename

    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix

    for index in range(1, 10_000):
        deduplicated = directory / f"{stem}_{index}{suffix}"

        if not deduplicated.exists():
            return deduplicated

    raise FileExistsError(f"Unable to create unique output path for {filename}")


def compress_container(container: bytes, compression_level: int) -> bytes:
    print("Compressing chunk/container...")
    print(f"Input size        : {len(container):,} bytes")
    print(f"Compression level : {compression_level}")

    compressed = zlib.compress(container, level=compression_level)
    ratio = len(compressed) / max(len(container), 1)

    print(f"Compressed size   : {len(compressed):,} bytes")
    print(f"Compression ratio : {ratio:.2%}")

    return compressed


def decompress_container(payload: bytes) -> bytes:
    print("Decompressing chunk/container...")
    container = zlib.decompress(payload)
    print(f"Output bytes      : {len(container):,}")
    return container


def split_chunks(payload: bytes, chunk_size: int) -> list[bytes]:
    return [
        payload[index : index + chunk_size]
        for index in range(0, len(payload), chunk_size)
    ] or [b""]


def encode_chunked_payload(
    payload: bytes,
    compression_level: int,
    public_key: str | None,
) -> tuple[bytes, str, str | None]:
    chunks = split_chunks(
        payload=payload,
        chunk_size=DEFAULT_CHUNK_SIZE,
    )

    total_chunks = len(chunks)
    serialized = b""

    public_key_path = resolve_default_public_key(public_key)
    crypto_mode = (
        CRYPTO_MODE_CHUNKED_X25519_AESGCM
        if public_key_path is not None
        else CRYPTO_MODE_NONE
    )

    print(f"Chunk count       : {total_chunks}")

    for index, chunk in enumerate(chunks, start=1):
        print(f"Chunk {index}/{total_chunks}")

        compressed = compress_container(
            container=chunk,
            compression_level=compression_level,
        )

        if public_key_path is not None:
            stored_chunk, crypto_meta = encrypt_payload(
                payload=compressed,
                recipient_public_key_path=public_key_path,
            )
            encrypted = True
        else:
            stored_chunk = compressed
            crypto_meta = {"crypto_mode": CRYPTO_MODE_NONE}
            encrypted = False

        chunk_header = ChunkHeader(
            index=index,
            total_chunks=total_chunks,
            raw_size=len(chunk),
            compressed_size=len(stored_chunk),
            encrypted=encrypted,
        )

        header_bytes = json.dumps(
            asdict(chunk_header),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        crypto_bytes = json.dumps(
            crypto_meta,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        serialized += len(header_bytes).to_bytes(8, "big")
        serialized += header_bytes
        serialized += len(crypto_bytes).to_bytes(8, "big")
        serialized += crypto_bytes
        serialized += len(stored_chunk).to_bytes(8, "big")
        serialized += stored_chunk

    return serialized, crypto_mode, public_key_path


def decode_chunked_payload(payload: bytes, private_key: str | None) -> bytes:
    cursor = 0
    rebuilt = b""

    while cursor < len(payload):
        header_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        header = ChunkHeader(
            **json.loads(payload[cursor : cursor + header_size].decode("utf-8"))
        )
        cursor += header_size

        crypto_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        crypto_meta = json.loads(payload[cursor : cursor + crypto_size].decode("utf-8"))
        cursor += crypto_size

        chunk_size = int.from_bytes(payload[cursor : cursor + 8], "big")
        cursor += 8

        stored_chunk = payload[cursor : cursor + chunk_size]
        cursor += chunk_size

        if header.encrypted:
            if private_key is None:
                raise ValueError("Private key path is required for encrypted chunks")

            compressed = decrypt_payload(
                ciphertext=stored_chunk,
                crypto_meta=crypto_meta,
                private_key_path=private_key,
            )
        else:
            compressed = stored_chunk

        chunk = decompress_container(compressed)

        if len(chunk) != header.raw_size:
            raise ValueError(
                f"Invalid decoded chunk size: expected {header.raw_size}, got {len(chunk)}"
            )

        rebuilt += chunk

    return rebuilt


def bytes_to_int16_samples(payload: bytes) -> np.ndarray:
    print("Packing bytes into PCM16 audio samples...")

    if len(payload) % 2 != 0:
        payload += b"\x00"

    total_samples = len(payload) // 2

    for _ in tqdm(
        range(total_samples),
        desc="Packing samples",
        unit="sample",
    ):
        pass

    samples = np.frombuffer(payload, dtype=np.int16).copy()

    print(f"Audio samples     : {len(samples):,}")

    return samples


def int16_samples_to_bytes(samples: np.ndarray) -> bytes:
    print("Unpacking PCM16 audio samples into bytes...")

    for _ in tqdm(
        range(len(samples)),
        desc="Unpacking samples",
        unit="sample",
    ):
        pass

    return samples.astype(np.int16).tobytes()


def write_audio(
    path: str | Path,
    samples: np.ndarray,
    sample_rate: int,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing audio     : {output_path}")

    sf.write(
        file=output_path,
        data=samples,
        samplerate=sample_rate,
        subtype="PCM_16",
    )


def read_audio(path: str | Path) -> tuple[int, np.ndarray]:
    print(f"Reading audio     : {path}")

    data, sample_rate = sf.read(
        path,
        dtype="int16",
    )

    if data.ndim > 1:
        raise ValueError("Cypher payload audio must be mono")

    print(f"Sample rate       : {sample_rate} Hz")
    print(f"Audio samples     : {len(data):,}")

    return sample_rate, data


def read_audio_payload(path: str | Path) -> tuple[dict[str, str], bytes]:
    _sample_rate, samples = read_audio(path)
    audio_payload = int16_samples_to_bytes(samples)
    return parse_audio_payload(audio_payload)


def resolve_default_public_key(args_public_key: str | None) -> str | None:
    if args_public_key is not None:
        return args_public_key

    if DEFAULT_PUBLIC_KEY_PATH.exists():
        return str(DEFAULT_PUBLIC_KEY_PATH)

    return None


def resolve_default_private_key(args_private_key: str | None) -> str | None:
    if args_private_key is not None:
        return args_private_key

    if DEFAULT_PRIVATE_KEY_PATH.exists():
        return str(DEFAULT_PRIVATE_KEY_PATH)

    return None


def encode_container_to_audio(
    container: bytes,
    header: CypherHeader,
    output_path: Path,
    sample_rate: int,
    compression_level: int,
    public_key: str | None,
) -> None:
    chunked_payload, crypto_mode, public_key_path = encode_chunked_payload(
        payload=container,
        compression_level=compression_level,
        public_key=public_key,
    )

    audio_payload = build_audio_payload(
        payload=chunked_payload,
        header=header,
        crypto_meta={"crypto_mode": crypto_mode},
    )

    samples = bytes_to_int16_samples(audio_payload)

    write_audio(
        path=output_path,
        samples=samples,
        sample_rate=sample_rate,
    )

    print("Encode completed.")
    print(f"Audio             : {output_path}")
    print("Embedded metadata : yes")
    print(f"Encryption        : {crypto_mode}")
    print(f"Public key        : {public_key_path or 'none'}")
    print(f"Checksum          : {header.checksum}")


def keygen_command(args: argparse.Namespace) -> None:
    generate_keypair(
        private_key_path=Path(args.private_key),
        public_key_path=Path(args.public_key),
        force=args.force,
    )


def encode_command(args: argparse.Namespace) -> None:
    input_path = resolve_input_file(args.file)

    output_path = resolve_audio_output(
        input_path=input_path,
        audio_format=args.format,
        obfuscate_name=not args.keep_name,
    )

    payload = read_file(input_path)
    checksum = compute_checksum(payload)

    header = create_header(
        input_path=input_path,
        raw_size=len(payload),
        checksum=checksum,
        payload_mode=PAYLOAD_MODE,
    )

    container = build_container(
        header=header,
        payload=payload,
    )

    print("Starting V4.9 self-contained encode...")
    print(f"Input file        : {input_path}")
    print(f"MIME type         : {header.mime_type}")
    print(f"Raw size          : {len(payload):,} bytes")
    print(f"Sample rate       : {args.sample_rate} Hz")

    encode_container_to_audio(
        container=container,
        header=header,
        output_path=output_path,
        sample_rate=args.sample_rate,
        compression_level=args.compression_level,
        public_key=args.public_key,
    )


def bundle_command(args: argparse.Namespace) -> None:
    input_paths = [
        resolve_input_file(file_arg)
        for file_arg in args.files
    ]

    bundled_files: list[tuple[CypherHeader, bytes]] = []
    total_size = 0

    print("Starting V4.9 multi-file bundle encode...")
    print(f"Files count       : {len(input_paths)}")

    for input_path in input_paths:
        payload = read_file(input_path)
        checksum = compute_checksum(payload)
        total_size += len(payload)

        header = create_header(
            input_path=input_path,
            raw_size=len(payload),
            checksum=checksum,
            payload_mode=PAYLOAD_MODE,
        )

        bundled_files.append((header, payload))

        print(f"- {input_path} ({len(payload):,} bytes, {header.mime_type})")

    bundle_container = build_bundle_container(bundled_files)
    bundle_checksum = compute_checksum(bundle_container)

    bundle_name = args.name or DEFAULT_BUNDLE_NAME
    pseudo_input_path = Path(f"{bundle_name}.cypherbundle")

    bundle_header = create_header(
        input_path=pseudo_input_path,
        raw_size=len(bundle_container),
        checksum=bundle_checksum,
        payload_mode=BUNDLE_PAYLOAD_MODE,
    )

    output_path = resolve_audio_output(
        input_path=Path(bundle_name),
        audio_format=args.format,
        obfuscate_name=not args.keep_name,
    )

    output_path = BUNDLE_AUDIO_DIR / output_path.name

    print(f"Total raw size    : {total_size:,} bytes")
    print(f"Bundle size       : {len(bundle_container):,} bytes")
    print(f"Sample rate       : {args.sample_rate} Hz")

    container = build_container(
        header=bundle_header,
        payload=bundle_container,
    )

    encode_container_to_audio(
        container=container,
        header=bundle_header,
        output_path=output_path,
        sample_rate=args.sample_rate,
        compression_level=args.compression_level,
        public_key=args.public_key,
    )


def decode_command(args: argparse.Namespace) -> None:
    audio_path = resolve_input_audio(args.file)

    print("Starting V4.9 chunked decode...")

    _crypto_meta, payload = read_audio_payload(audio_path)

    private_key_path = resolve_default_private_key(args.private_key)

    require_touch_id(TOUCH_ID_DECODE_REASON)

    container = decode_chunked_payload(
        payload=payload,
        private_key=private_key_path,
    )

    header, restored_payload = parse_container(container)

    actual_checksum = compute_checksum(restored_payload)

    if not verify_checksum(header.checksum, actual_checksum):
        raise ValueError(
            "Checksum mismatch: "
            f"expected {header.checksum}, got {actual_checksum}"
        )

    if header.payload_mode == BUNDLE_PAYLOAD_MODE or is_bundle_container(restored_payload):
        restore_bundle_payload(
            audio_path=audio_path,
            restored_payload=restored_payload,
            bundle_checksum=actual_checksum,
            output_dir=resolve_bundle_output_dir(args.output),
        )
        return

    output_path = resolve_decoded_output(
        output_name=args.output,
        original_name=header.original_name,
    )

    write_file(
        path=output_path,
        payload=restored_payload,
    )

    print("Decode completed.")
    print(f"Audio             : {audio_path}")
    print(f"Output file       : {output_path}")
    print(f"Original name     : {header.original_name}")
    print(f"MIME type         : {header.mime_type}")
    print(f"Checksum          : {actual_checksum}")


def restore_bundle_payload(
    audio_path: Path,
    restored_payload: bytes,
    bundle_checksum: str,
    output_dir: Path,
) -> None:
    files = parse_bundle_container(restored_payload)

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
        output_path = unique_output_path(
            output_dir,
            file_header.original_name,
        )

        write_file(
            path=output_path,
            payload=file_payload,
        )

        print(f"- restored         : {output_path}")


def unbundle_command(args: argparse.Namespace) -> None:
    audio_path = resolve_input_audio(args.file)

    print("Starting V4.9 chunked bundle restore...")

    _crypto_meta, payload = read_audio_payload(audio_path)

    private_key_path = resolve_default_private_key(args.private_key)

    require_touch_id(TOUCH_ID_UNBUNDLE_REASON)

    container = decode_chunked_payload(
        payload=payload,
        private_key=private_key_path,
    )

    header, restored_payload = parse_container(container)

    if header.payload_mode != BUNDLE_PAYLOAD_MODE:
        raise ValueError("Audio payload is not a bundle")

    actual_checksum = compute_checksum(restored_payload)

    if not verify_checksum(header.checksum, actual_checksum):
        raise ValueError(
            "Bundle checksum mismatch: "
            f"expected {header.checksum}, got {actual_checksum}"
        )

    restore_bundle_payload(
        audio_path=audio_path,
        restored_payload=restored_payload,
        bundle_checksum=actual_checksum,
        output_dir=resolve_bundle_output_dir(args.output),
    )


def inspect_command(args: argparse.Namespace) -> None:
    audio_path = resolve_input_audio(args.file)

    print("Inspecting cypher audio...")

    crypto_meta, payload = read_audio_payload(audio_path)

    public_meta = crypto_meta.get("public", {})
    crypto_mode = crypto_meta.get("crypto_mode", CRYPTO_MODE_NONE)

    print()
    print("Cypher payload")
    print("--------------")
    print(f"Audio file     : {audio_path}")
    print(f"Encryption     : {crypto_mode}")
    print(f"Cypher version : {public_meta.get('cypher_version', 'unknown')}")
    print(f"Payload mode   : {public_meta.get('payload_mode', 'unknown')}")

    if crypto_mode == CRYPTO_MODE_NONE:
        print(f"Original name  : {public_meta.get('original_name', 'unknown')}")
        print(f"MIME type      : {public_meta.get('mime_type', 'unknown')}")
        print(f"Raw size       : {public_meta.get('raw_size', 'unknown')} bytes")
        print(f"Checksum       : {public_meta.get('checksum', 'unknown')}")
    else:
        print()
        print("Metadata hidden (encrypted payload mode)")

    print(f"Stored payload : {len(payload):,} bytes")


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
        default=None,
        help=(
            "Encrypt using this public key. "
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
