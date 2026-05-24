import pytest

import cypher.main as cypher


def test_encrypt_payload_multi_requires_recipient() -> None:
    with pytest.raises(ValueError, match="At least one public key"):
        cypher.encrypt_payload_multi(b"payload", [])


def test_decrypt_payload_multi_rejects_missing_recipients(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        cypher,
        "load_private_key",
        lambda _path: object(),
    )

    with pytest.raises(ValueError, match="Invalid multi-recipient metadata"):
        cypher.decrypt_payload_multi(
            ciphertext=b"ciphertext",
            crypto_meta={
                "crypto_mode": cypher.CRYPTO_MODE_X25519_AESGCM_MULTI,
                "nonce": "AAAA",
            },
            private_key_path=tmp_path / "private.pem",
        )


def test_resolve_default_public_keys_returns_empty_without_default(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        cypher,
        "DEFAULT_PUBLIC_KEY_PATH",
        tmp_path / "missing_public.pem",
    )

    assert cypher.resolve_default_public_keys(None) == []


def test_resolve_default_public_keys_uses_explicit_values() -> None:
    assert cypher.resolve_default_public_keys(["a.pem", "b.pem"]) == [
        "a.pem",
        "b.pem",
    ]
