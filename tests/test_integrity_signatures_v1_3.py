from argparse import Namespace

import pytest

import cypher.main as cypher


def test_signing_keygen_sign_and_verify_roundtrip(tmp_path) -> None:
    private_key = tmp_path / "signing_private.pem"
    public_key = tmp_path / "signing_public.pem"
    payload = tmp_path / "payload.flac"

    payload.write_bytes(b"audio payload")

    cypher.generate_signing_keypair(
        private_key_path=private_key,
        public_key_path=public_key,
    )

    signature = cypher.sign_file(
        file_path=payload,
        private_key_path=private_key,
    )

    assert signature == tmp_path / "payload.flac.sig"
    assert signature.exists()

    assert cypher.verify_file_signature(
        file_path=payload,
        signature_path=signature,
        public_key_path=public_key,
    )


def test_verify_rejects_tampered_payload(tmp_path) -> None:
    private_key = tmp_path / "signing_private.pem"
    public_key = tmp_path / "signing_public.pem"
    payload = tmp_path / "payload.flac"

    payload.write_bytes(b"original")

    cypher.generate_signing_keypair(private_key, public_key)

    signature = cypher.sign_file(payload, private_key)

    payload.write_bytes(b"tampered")

    assert not cypher.verify_file_signature(payload, signature, public_key)


def test_signature_manifest_rejects_bad_magic(tmp_path) -> None:
    manifest = tmp_path / "payload.sig"
    manifest.write_text(
        """{
  "algorithm": "Ed25519",
  "magic": "BAD",
  "public_key_fingerprint": "x",
  "signature": "x",
  "signed_at": "now",
  "signed_file": "payload.flac",
  "signed_sha256": "abc",
  "signed_size": 1,
  "version": 1
}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid signature manifest magic"):
        cypher.read_signature_manifest(manifest)


def test_signature_cli_commands_exist() -> None:
    parser = cypher.build_parser()

    sign_args = parser.parse_args(["sign", "payload.flac"])
    verify_args = parser.parse_args(["verify", "payload.flac"])
    keygen_args = parser.parse_args(["signing-keygen"])

    assert sign_args.file == "payload.flac"
    assert verify_args.file == "payload.flac"
    assert callable(keygen_args.func)


def test_sign_and_verify_commands_print_status(tmp_path, capsys) -> None:
    private_key = tmp_path / "signing_private.pem"
    public_key = tmp_path / "signing_public.pem"
    payload = tmp_path / "payload.flac"

    payload.write_bytes(b"payload")

    cypher.generate_signing_keypair(private_key, public_key)

    cypher.sign_command(
        Namespace(
            file=str(payload),
            private_key=str(private_key),
            output=None,
        )
    )

    cypher.verify_command(
        Namespace(
            file=str(payload),
            signature=None,
            public_key=str(public_key),
        )
    )

    output = capsys.readouterr().out

    assert "Cypher signature created" in output
    assert "Valid     : yes" in output


def test_verify_command_exits_on_invalid_signature(tmp_path) -> None:
    private_key = tmp_path / "signing_private.pem"
    public_key = tmp_path / "signing_public.pem"
    payload = tmp_path / "payload.flac"

    payload.write_bytes(b"payload")

    cypher.generate_signing_keypair(private_key, public_key)
    cypher.sign_file(payload, private_key)

    payload.write_bytes(b"tampered")

    with pytest.raises(SystemExit):
        cypher.verify_command(
            Namespace(
                file=str(payload),
                signature=None,
                public_key=str(public_key),
            )
        )


def test_inspect_prints_signature_sidecar(monkeypatch, tmp_path, capsys) -> None:
    audio = tmp_path / "payload.flac"
    audio.write_bytes(b"audio")

    private_key = tmp_path / "signing_private.pem"
    public_key = tmp_path / "signing_public.pem"

    cypher.generate_signing_keypair(private_key, public_key)
    cypher.sign_file(audio, private_key)

    monkeypatch.setattr(cypher, "resolve_input_audio", lambda file: audio)
    monkeypatch.setattr(
        cypher,
        "read_audio_payload",
        lambda path: (
            {
                "crypto_mode": cypher.CRYPTO_MODE_NONE,
                "public": {
                    "cypher_version": cypher.VERSION,
                    "payload_mode": cypher.PAYLOAD_MODE,
                    "original_name": "payload.bin",
                    "mime_type": "application/octet-stream",
                    "raw_size": "5",
                    "checksum": "abc",
                },
            },
            b"bytes",
        ),
    )

    cypher.inspect_command(Namespace(file=str(audio)))

    output = capsys.readouterr().out

    assert "Signature" in output
    assert "sidecar signature found" in output
    assert "Ed25519" in output
