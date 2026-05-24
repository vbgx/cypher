from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

import cypher.main as cypher

PASSWORD = b"cypher-test-password"


def write_pair(tmp_path):
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"

    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(PASSWORD),
        )
    )

    public_path.write_bytes(
        public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    return private_path, public_path


def test_single_recipient_encrypt_decrypt_roundtrip(tmp_path, monkeypatch) -> None:
    private_key, public_key = write_pair(tmp_path)

    monkeypatch.setattr(
        cypher,
        "load_private_key_password_from_keychain",
        lambda: PASSWORD.decode(),
    )

    payload = b"legacy single recipient"

    ciphertext, meta = cypher.encrypt_payload(payload, public_key)

    assert meta["crypto_mode"] == cypher.CRYPTO_MODE_X25519_AESGCM
    assert cypher.decrypt_payload(ciphertext, meta, private_key) == payload


def test_load_public_key_rejects_private_key(tmp_path) -> None:
    private_key, _public_key = write_pair(tmp_path)

    try:
        cypher.load_public_key(private_key)
    except (TypeError, ValueError):
        return

    raise AssertionError("private key should not load as public key")
