from __future__ import annotations

import argparse
import base64
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

SIGNATURE_MAGIC = "CYPHER_SIGNATURE"
SIGNATURE_VERSION = 1
SIGNATURE_ALGORITHM = "Ed25519"

SIGNING_PRIVATE_KEY_PATH = Path(".keys/cypher_signing_private.pem")
SIGNING_PUBLIC_KEY_PATH = Path(".keys/cypher_signing_public.pem")


@dataclass(frozen=True)
class SignatureManifest:
    magic: str
    version: int
    algorithm: str
    signed_file: str
    signed_size: int
    signed_sha256: str
    signature: str
    public_key_fingerprint: str
    signed_at: str


def compute_file_sha256(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def ed25519_public_key_fingerprint(
    public_key: ed25519.Ed25519PublicKey,
) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    digest = sha256(raw).hexdigest()
    return ":".join(digest[index : index + 2] for index in range(0, len(digest), 2))


def generate_signing_keypair(
    private_key_path: Path = SIGNING_PRIVATE_KEY_PATH,
    public_key_path: Path = SIGNING_PUBLIC_KEY_PATH,
    force: bool = False,
) -> None:
    existing = [
        path
        for path in [private_key_path, public_key_path]
        if path.exists()
    ]

    if existing and not force:
        raise FileExistsError(
            "Signing key file already exists. Use --force to overwrite:\n"
            + "\n".join(str(path) for path in existing)
        )

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    public_key_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    print("Signing keypair generated.")
    print(f"Private key : {private_key_path}")
    print(f"Public key  : {public_key_path}")
    print(f"Fingerprint : {ed25519_public_key_fingerprint(public_key)}")


def load_signing_private_key(path: str | Path) -> ed25519.Ed25519PrivateKey:
    key = serialization.load_pem_private_key(
        Path(path).read_bytes(),
        password=None,
    )

    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise TypeError("Signing private key must be an Ed25519 private key")

    return key


def load_signing_public_key(path: str | Path) -> ed25519.Ed25519PublicKey:
    key = serialization.load_pem_public_key(Path(path).read_bytes())

    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise TypeError("Signing public key must be an Ed25519 public key")

    return key


def default_signature_path(path: str | Path) -> Path:
    source = Path(path)
    return source.with_name(f"{source.name}.sig")


def build_signature_manifest(
    file_path: Path,
    private_key: ed25519.Ed25519PrivateKey,
) -> SignatureManifest:
    payload = file_path.read_bytes()
    public_key = private_key.public_key()

    signature = private_key.sign(payload)

    return SignatureManifest(
        magic=SIGNATURE_MAGIC,
        version=SIGNATURE_VERSION,
        algorithm=SIGNATURE_ALGORITHM,
        signed_file=file_path.name,
        signed_size=len(payload),
        signed_sha256=sha256(payload).hexdigest(),
        signature=base64.b64encode(signature).decode("ascii"),
        public_key_fingerprint=ed25519_public_key_fingerprint(public_key),
        signed_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def write_signature_manifest(
    manifest: SignatureManifest,
    output_path: str | Path,
) -> None:
    Path(output_path).write_text(
        json.dumps(
            asdict(manifest),
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def read_signature_manifest(path: str | Path) -> SignatureManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest = SignatureManifest(**data)

    if manifest.magic != SIGNATURE_MAGIC:
        raise ValueError(f"Invalid signature manifest magic: {manifest.magic}")

    if manifest.version != SIGNATURE_VERSION:
        raise ValueError(f"Unsupported signature manifest version: {manifest.version}")

    if manifest.algorithm != SIGNATURE_ALGORITHM:
        raise ValueError(f"Unsupported signature algorithm: {manifest.algorithm}")

    return manifest


def sign_file(
    file_path: str | Path,
    private_key_path: str | Path = SIGNING_PRIVATE_KEY_PATH,
    output_path: str | Path | None = None,
) -> Path:
    source = Path(file_path)
    private_key = load_signing_private_key(private_key_path)
    manifest = build_signature_manifest(source, private_key)

    signature_path = Path(output_path) if output_path else default_signature_path(source)
    write_signature_manifest(manifest, signature_path)

    return signature_path


def verify_file_signature(
    file_path: str | Path,
    signature_path: str | Path | None = None,
    public_key_path: str | Path = SIGNING_PUBLIC_KEY_PATH,
) -> bool:
    source = Path(file_path)
    sidecar = Path(signature_path) if signature_path else default_signature_path(source)

    manifest = read_signature_manifest(sidecar)

    payload = source.read_bytes()
    actual_sha256 = sha256(payload).hexdigest()

    if len(payload) != manifest.signed_size:
        return False

    if actual_sha256 != manifest.signed_sha256:
        return False

    public_key = load_signing_public_key(public_key_path)

    try:
        public_key.verify(
            base64.b64decode(manifest.signature),
            payload,
        )
    except InvalidSignature:
        return False

    return True


def signature_status_for_file(file_path: str | Path) -> SignatureManifest | None:
    sidecar = default_signature_path(file_path)

    if not sidecar.exists():
        return None

    return read_signature_manifest(sidecar)


def signing_keygen_command(args: argparse.Namespace) -> None:
    generate_signing_keypair(
        private_key_path=Path(args.private_key),
        public_key_path=Path(args.public_key),
        force=args.force,
    )


def sign_command(args: argparse.Namespace) -> None:
    signature_path = sign_file(
        file_path=args.file,
        private_key_path=args.private_key,
        output_path=args.output,
    )

    manifest = read_signature_manifest(signature_path)

    print("Cypher signature created")
    print("------------------------")
    print(f"File        : {args.file}")
    print(f"Signature   : {signature_path}")
    print(f"Algorithm   : {manifest.algorithm}")
    print(f"SHA256      : {manifest.signed_sha256}")
    print(f"Fingerprint : {manifest.public_key_fingerprint}")


def verify_command(args: argparse.Namespace) -> None:
    valid = verify_file_signature(
        file_path=args.file,
        signature_path=args.signature,
        public_key_path=args.public_key,
    )

    print("Cypher signature verification")
    print("-----------------------------")
    print(f"File      : {args.file}")
    print(f"Signature : {args.signature or default_signature_path(args.file)}")
    print(f"Valid     : {'yes' if valid else 'no'}")

    if not valid:
        raise SystemExit(1)
