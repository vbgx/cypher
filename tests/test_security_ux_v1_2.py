from argparse import Namespace
from pathlib import Path

import cypher.main as cypher


def test_parser_has_v1_2_security_ux_commands() -> None:
    parser = cypher.build_parser()

    args = parser.parse_args(["key-info", "public.pem"])
    assert args.file == "public.pem"

    args = parser.parse_args(["recipients", "payload.flac"])
    assert args.file == "payload.flac"

    args = parser.parse_args(["encode", "secret.txt", "--no-encrypt"])
    assert args.no_encrypt is True


def test_resolve_default_public_keys_warns_when_default_used(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    default_public = tmp_path / "cypher_public.pem"
    default_public.write_text("fake")

    monkeypatch.setattr(cypher, "DEFAULT_PUBLIC_KEY_PATH", default_public)

    assert cypher.resolve_default_public_keys(None) == [str(default_public)]
    assert "Warning: using default public key automatically" in capsys.readouterr().out


def test_resolve_default_public_keys_no_encrypt_disables_default(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    default_public = tmp_path / "cypher_public.pem"
    default_public.write_text("fake")

    monkeypatch.setattr(cypher, "DEFAULT_PUBLIC_KEY_PATH", default_public)

    assert cypher.resolve_default_public_keys(None, no_encrypt=True) == []
    assert "Warning" not in capsys.readouterr().out


def test_key_info_command_prints_fingerprint(tmp_path, monkeypatch, capsys) -> None:
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"

    monkeypatch.setattr(
        cypher,
        "save_private_key_password_to_keychain",
        lambda password: None,
    )

    cypher.generate_keypair(private_path, public_path)

    cypher.key_info_command(Namespace(file=str(public_path)))

    output = capsys.readouterr().out

    assert "Cypher public key" in output
    assert "Fingerprint" in output
    assert ":" in output


def test_recipients_command_no_crypto(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cypher,
        "resolve_input_audio",
        lambda file: Path("payload.flac"),
    )
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: ({"crypto_mode": cypher.CRYPTO_MODE_NONE}, b"payload"),
    )

    cypher.recipients_command(Namespace(file="payload.flac"))

    output = capsys.readouterr().out

    assert "Cypher recipients" in output
    assert "Recipients  : none" in output


def test_recipients_command_multi_crypto(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cypher,
        "resolve_input_audio",
        lambda file: Path("payload.flac"),
    )
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: (
            {
                "crypto_mode": cypher.CRYPTO_MODE_X25519_AESGCM_MULTI,
                "recipients": [
                    {
                        "wrapped_key": "abc",
                        "ephemeral_public_key": "xyz",
                    },
                    {
                        "wrapped_key": "def",
                        "ephemeral_public_key": "uvw",
                    },
                ],
            },
            b"payload",
        ),
    )

    cypher.recipients_command(Namespace(file="payload.flac"))

    output = capsys.readouterr().out

    assert "Recipients  : 2" in output
    assert "recipient 1" in output
    assert "recipient 2" in output
