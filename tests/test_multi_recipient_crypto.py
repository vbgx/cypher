from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

import cypher.main as cypher

PASSWORD = b"cypher-test-password"


def write_pair(tmp_path, name):
    private_path = tmp_path / f"{name}_private.pem"
    public_path = tmp_path / f"{name}_public.pem"

    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(
                PASSWORD
            ),
        )
    )

    public_path.write_bytes(
        public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    return private_path, public_path


def test_multi_recipient_crypto(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        cypher,
        "load_private_key_password_from_keychain",
        lambda: PASSWORD.decode(),
    )

    monkeypatch.setattr(
        cypher,
        "require_touch_id",
        lambda reason: None,
    )

    alice_private, alice_public = write_pair(
        tmp_path,
        "alice",
    )

    bob_private, bob_public = write_pair(
        tmp_path,
        "bob",
    )

    charlie_private, _ = write_pair(
        tmp_path,
        "charlie",
    )

    payload = b"secret"

    ciphertext, meta = cypher.encrypt_payload_multi(
        payload,
        [alice_public, bob_public],
    )

    assert len(meta["recipients"]) == 2

    assert (
        cypher.decrypt_payload_multi(
            ciphertext,
            meta,
            alice_private,
        )
        == payload
    )

    assert (
        cypher.decrypt_payload_multi(
            ciphertext,
            meta,
            bob_private,
        )
        == payload
    )

    try:
        cypher.decrypt_payload_multi(
            ciphertext,
            meta,
            charlie_private,
        )
    except ValueError:
        return

    raise AssertionError(
        "charlie should not decrypt"
    )
