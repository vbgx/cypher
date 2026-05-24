
import pytest

import cypher.main as cypher


def test_generate_private_key_password_is_not_empty() -> None:
    password = cypher.generate_private_key_password()

    assert isinstance(password, str)
    assert len(password) > 20


def test_generate_keypair_writes_encrypted_private_and_public_key(
    tmp_path,
    monkeypatch,
) -> None:
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"

    saved_passwords = []

    monkeypatch.setattr(
        cypher,
        "save_private_key_password_to_keychain",
        lambda password: saved_passwords.append(password),
    )

    cypher.generate_keypair(
        private_key_path=private_key,
        public_key_path=public_key,
    )

    assert private_key.exists()
    assert public_key.exists()
    assert saved_passwords

    assert b"ENCRYPTED" in private_key.read_bytes()
    assert b"PUBLIC KEY" in public_key.read_bytes()


def test_generate_keypair_refuses_to_overwrite_without_force(
    tmp_path,
    monkeypatch,
) -> None:
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"

    private_key.write_text("existing")
    public_key.write_text("existing")

    monkeypatch.setattr(
        cypher,
        "save_private_key_password_to_keychain",
        lambda password: None,
    )

    with pytest.raises(FileExistsError, match="Key file already exists"):
        cypher.generate_keypair(
            private_key_path=private_key,
            public_key_path=public_key,
        )


def test_generate_keypair_force_deletes_old_keychain_item(
    tmp_path,
    monkeypatch,
) -> None:
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"

    private_key.write_text("existing")
    public_key.write_text("existing")

    deleted = []

    monkeypatch.setattr(
        cypher,
        "delete_private_key_password_from_keychain",
        lambda: deleted.append(True),
    )
    monkeypatch.setattr(
        cypher,
        "save_private_key_password_to_keychain",
        lambda password: None,
    )

    cypher.generate_keypair(
        private_key_path=private_key,
        public_key_path=public_key,
        force=True,
    )

    assert deleted == [True]
    assert b"ENCRYPTED" in private_key.read_bytes()


def test_load_private_key_requires_keychain_password(tmp_path, monkeypatch) -> None:
    private_key = tmp_path / "private.pem"
    private_key.write_text("not used")

    monkeypatch.setattr(
        cypher,
        "load_private_key_password_from_keychain",
        lambda: None,
    )

    with pytest.raises(ValueError, match="Private key password not found"):
        cypher.load_private_key(private_key)
