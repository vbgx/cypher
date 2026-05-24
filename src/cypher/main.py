import argparse
import base64
import json
import mimetypes
import os
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


PROJECT_NAME = "cypher"
VERSION = "0.4.4"

MAGIC = "CYPHER"
CONTAINER_MAGIC = b"CYPHER44"
AUDIO_MAGIC = b"CYPHERAUDIO44"
HEADER_VERSION = 44

PAYLOAD_MODE = "ANY_FILE_SELF_CONTAINED_AUDIO"
CHECKSUM_ALGORITHM = "SHA256"
COMPRESSION_ALGORITHM = "zlib"

CRYPTO_MODE_NONE = "none"
CRYPTO_MODE_X25519_AESGCM = "x25519-aesgcm"

DEFAULT_SAMPLE_RATE = 44_100
DEFAULT_AUDIO_FORMAT = "flac"
DEFAULT_COMPRESSION_LEVEL = 9

LOSSLESS_AUDIO_OUTPUT = {".wav", ".flac"}
UNSAFE_AUDIO_OUTPUT = {".mp3"}

DATA_DIR = Path("data")
INPUT_DIR = DATA_DIR / "input"
AUDIO_DIR = DATA_DIR / "audio"
OUTPUT_DIR = DATA_DIR / "output"
KEYS_DIR = Path(".keys")

DEFAULT_PRIVATE_KEY_PATH = KEYS_DIR / "cypher_private.pem"
DEFAULT_PUBLIC_KEY_PATH = KEYS_DIR / "cypher_public.pem"


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


def compute_checksum(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def verify_checksum(expected: str, actual: str) -> bool:
    return expected.lower() == actual.lower()


def resolve_input_file(path: str | Path) -> Path:
    candidate = Path(path)

    if candidate.exists():
        return candidate

    candidate = INPUT_DIR / path

    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Input file not found: {path}")


def resolve_input_audio(path: str | Path) -> Path:
    candidate = Path(path)

    if candidate.exists():
        return candidate

    candidate = AUDIO_DIR / path

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
) -> CypherHeader:
    path = Path(input_path)

    header = CypherHeader(
        original_name=path.name,
        original_suffix=path.suffix,
        mime_type=detect_mime_type(path),
        raw_size=raw_size,
        checksum=checksum,
    )

    validate_header(header)

    return header


def validate_header(header: CypherHeader) -> None:
    if header.magic != MAGIC:
        raise ValueError(f"Invalid magic: {header.magic}")

    if header.version != HEADER_VERSION:
        raise ValueError(f"Unsupported version: {header.version}")

    if header.payload_mode != PAYLOAD_MODE:
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
    data = json.loads(payload.decode("utf-8"))
    header = CypherHeader(**data)
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


def generate_keypair(
    private_key_path: Path = DEFAULT_PRIVATE_KEY_PATH,
    public_key_path: Path = DEFAULT_PUBLIC_KEY_PATH,
) -> None:
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.write_bytes(private_bytes)
    public_key_path.write_bytes(public_bytes)

    print("Keypair generated.")
    print(f"Private key: {private_key_path}")
    print(f"Public key : {public_key_path}")
    print()
    print("Keep the private key secret.")


def load_public_key(path: str | Path) -> x25519.X25519PublicKey:
    data = Path(path).read_bytes()

    key = serialization.load_pem_public_key(data)

    if not isinstance(key, x25519.X25519PublicKey):
        raise TypeError("Public key must be an X25519 public key")

    return key


def load_private_key(path: str | Path) -> x25519.X25519PrivateKey:
    data = Path(path).read_bytes()

    key = serialization.load_pem_private_key(
        data,
        password=None,
    )

    if not isinstance(key, x25519.X25519PrivateKey):
        raise TypeError("Private key must be an X25519 private key")

    return key


def derive_aes_key(
    shared_secret: bytes,
    salt: bytes,
) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"cypher-v4.4-x25519-aesgcm",
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

    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(
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

    aesgcm = AESGCM(aes_key)

    return aesgcm.decrypt(
        nonce,
        ciphertext,
        None,
    )


def build_audio_payload(
    payload: bytes,
    crypto_meta: dict[str, str] | None = None,
) -> bytes:
    meta = crypto_meta or {"crypto_mode": CRYPTO_MODE_NONE}
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

    return meta, payload


def resolve_audio_output(input_path: Path, audio_format: str) -> Path:
    suffix = audio_format if audio_format.startswith(".") else f".{audio_format}"

    if suffix in UNSAFE_AUDIO_OUTPUT:
        raise ValueError(
            "MP3 is lossy and cannot preserve arbitrary files bit-perfect. "
            "Use WAV or FLAC."
        )

    if suffix not in LOSSLESS_AUDIO_OUTPUT:
        raise ValueError(f"Unsupported audio format: {suffix}")

    return AUDIO_DIR / f"{input_path.stem}{suffix}"


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


def compress_container(
    container: bytes,
    compression_level: int,
) -> bytes:
    print("Compressing embedded container...")
    print(f"Container size    : {len(container):,} bytes")
    print(f"Compression level : {compression_level}")

    compressed = zlib.compress(container, level=compression_level)
    ratio = len(compressed) / max(len(container), 1)

    print(f"Compressed size   : {len(compressed):,} bytes")
    print(f"Compression ratio : {ratio:.2%}")

    return compressed


def decompress_container(payload: bytes) -> bytes:
    print("Decompressing embedded container...")

    container = zlib.decompress(payload)

    print(f"Container bytes   : {len(container):,}")

    return container


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


def keygen_command(args: argparse.Namespace) -> None:
    generate_keypair(
        private_key_path=Path(args.private_key),
        public_key_path=Path(args.public_key),
    )


def encode_command(args: argparse.Namespace) -> None:
    input_path = resolve_input_file(args.file)
    output_path = resolve_audio_output(input_path, args.format)

    payload = read_file(input_path)
    checksum = compute_checksum(payload)

    header = create_header(
        input_path=input_path,
        raw_size=len(payload),
        checksum=checksum,
    )

    container = build_container(
        header=header,
        payload=payload,
    )

    print("Starting V4.4 self-contained encode...")
    print(f"Input file        : {input_path}")
    print(f"MIME type         : {header.mime_type}")
    print(f"Raw size          : {len(payload):,} bytes")
    print(f"Sample rate       : {args.sample_rate} Hz")

    compressed = compress_container(
        container=container,
        compression_level=args.compression_level,
    )

    public_key_path = args.public_key

    if public_key_path is None:
        value = input("Public key path for encryption [empty = no encryption]: ").strip()
        public_key_path = value or None

    if public_key_path is not None:
        encrypted_payload, crypto_meta = encrypt_payload(
            payload=compressed,
            recipient_public_key_path=public_key_path,
        )
    else:
        encrypted_payload = compressed
        crypto_meta = {"crypto_mode": CRYPTO_MODE_NONE}

    audio_payload = build_audio_payload(
        payload=encrypted_payload,
        crypto_meta=crypto_meta,
    )

    samples = bytes_to_int16_samples(audio_payload)

    write_audio(
        path=output_path,
        samples=samples,
        sample_rate=args.sample_rate,
    )

    print("Encode completed.")
    print(f"Audio             : {output_path}")
    print(f"Embedded metadata : yes")
    print(f"Encryption        : {crypto_meta['crypto_mode']}")
    print(f"Checksum          : {checksum}")


def decode_command(args: argparse.Namespace) -> None:
    audio_path = resolve_input_audio(args.file)

    print("Starting V4.4 self-contained decode...")

    _sample_rate, samples = read_audio(audio_path)

    audio_payload = int16_samples_to_bytes(samples)
    crypto_meta, payload = parse_audio_payload(audio_payload)

    crypto_mode = crypto_meta.get("crypto_mode", CRYPTO_MODE_NONE)

    if crypto_mode == CRYPTO_MODE_X25519_AESGCM:
        private_key_path = args.private_key

        if private_key_path is None:
            private_key_path = input(
                "Private key path for decryption: "
            ).strip()

        if not private_key_path:
            raise ValueError("Private key path is required for encrypted payloads")

        compressed = decrypt_payload(
            ciphertext=payload,
            crypto_meta=crypto_meta,
            private_key_path=private_key_path,
        )
    elif crypto_mode == CRYPTO_MODE_NONE:
        compressed = payload
    else:
        raise ValueError(f"Unsupported crypto mode: {crypto_mode}")

    container = decompress_container(compressed)

    header, restored_payload = parse_container(container)

    actual_checksum = compute_checksum(restored_payload)

    if not verify_checksum(header.checksum, actual_checksum):
        raise ValueError(
            "Checksum mismatch: "
            f"expected {header.checksum}, got {actual_checksum}"
        )

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
    print(f"Encryption        : {crypto_mode}")
    print(f"Checksum          : {actual_checksum}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cypher",
        description=(
            "Encode any file into self-contained lossless audio "
            "and decode it back."
        ),
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
        help="Generate PGP-like public/private keys",
    )

    keygen_parser.add_argument(
        "--private-key",
        default=str(DEFAULT_PRIVATE_KEY_PATH),
    )

    keygen_parser.add_argument(
        "--public-key",
        default=str(DEFAULT_PUBLIC_KEY_PATH),
    )

    keygen_parser.set_defaults(func=keygen_command)

    encode_parser = subparsers.add_parser(
        "encode",
        help="Encode any file to self-contained audio",
    )

    encode_parser.add_argument("file")

    encode_parser.add_argument(
        "--format",
        default=DEFAULT_AUDIO_FORMAT,
        choices=["wav", "flac", "mp3"],
    )

    encode_parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
    )

    encode_parser.add_argument(
        "--compression-level",
        type=int,
        default=DEFAULT_COMPRESSION_LEVEL,
        choices=range(0, 10),
        metavar="[0-9]",
    )

    encode_parser.add_argument(
        "--public-key",
        default=None,
        help="Encrypt payload for this public key",
    )

    encode_parser.set_defaults(func=encode_command)

    decode_parser = subparsers.add_parser(
        "decode",
        help="Decode self-contained audio back to original file",
    )

    decode_parser.add_argument("file")

    decode_parser.add_argument(
        "output",
        nargs="?",
        default=None,
    )

    decode_parser.add_argument(
        "--private-key",
        default=None,
        help="Private key required for encrypted payloads",
    )

    decode_parser.set_defaults(func=decode_command)

    decore_parser = subparsers.add_parser(
        "decore",
        help="Alias for decode",
    )

    decore_parser.add_argument("file")

    decore_parser.add_argument(
        "output",
        nargs="?",
        default=None,
    )

    decore_parser.add_argument(
        "--private-key",
        default=None,
        help="Private key required for encrypted payloads",
    )

    decore_parser.set_defaults(func=decode_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
