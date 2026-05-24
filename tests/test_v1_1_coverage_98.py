from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

import cypher.audio as audio
import cypher.bundle as bundle
import cypher.container as container
import cypher.keys as keys
import cypher.main as cypher


def test_container_resolve_input_file_from_input_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    file_path = input_dir / "inside.txt"
    file_path.write_text("ok")

    monkeypatch.setattr(cypher, "INPUT_DIR", input_dir)

    assert cypher.resolve_input_file("inside.txt") == file_path


def test_container_resolve_input_audio_from_audio_and_bundle_dirs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_dir = tmp_path / "audio"
    bundle_dir = audio_dir / "bundle"
    audio_dir.mkdir()
    bundle_dir.mkdir()

    audio_file = audio_dir / "payload.flac"
    bundle_file = bundle_dir / "bundle.flac"
    audio_file.write_bytes(b"a")
    bundle_file.write_bytes(b"b")

    monkeypatch.setattr(cypher, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(cypher, "BUNDLE_AUDIO_DIR", bundle_dir)

    assert cypher.resolve_input_audio("payload.flac") == audio_file
    assert cypher.resolve_input_audio("bundle.flac") == bundle_file


def test_container_resolve_outputs_and_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cypher, "OUTPUT_DIR", tmp_path)

    assert cypher.resolve_decoded_output(None, "x.txt") == tmp_path / "x.txt"
    assert cypher.resolve_decoded_output("x.txt", "ignored") == tmp_path / "x.txt"

    assert cypher.resolve_bundle_output_dir(None) == tmp_path / "bundle"
    assert cypher.resolve_bundle_output_dir(None, "root") == tmp_path / "root"
    assert cypher.resolve_bundle_output_dir("named") == tmp_path / "named"


def test_container_default_key_resolvers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_key = tmp_path / "public.pem"
    private_key = tmp_path / "private.pem"
    public_key.write_text("pub")
    private_key.write_text("priv")

    monkeypatch.setattr(cypher, "DEFAULT_PUBLIC_KEY_PATH", public_key)
    monkeypatch.setattr(cypher, "DEFAULT_PRIVATE_KEY_PATH", private_key)

    assert cypher.resolve_default_public_key(None) == str(public_key)
    assert cypher.resolve_default_public_key("explicit.pem") == "explicit.pem"
    assert container.resolve_default_public_keys(["a.pem"]) == ["a.pem"]
    assert cypher.resolve_default_private_key(None) == str(private_key)
    assert cypher.resolve_default_private_key("p.pem") == "p.pem"


def test_container_encode_chunked_no_crypto_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        container,
        "resolve_default_public_keys",
        lambda _keys: [],
    )

    encoded, mode, public_key_summary = (
        container.encode_chunked_payload(
            payload=b"abc",
            compression_level=9,
            public_key=None,
        )
    )

    decoded = container.decode_chunked_payload(
        encoded,
        None,
    )

    assert mode == container.CRYPTO_MODE_NONE
    assert public_key_summary is None
    assert decoded.endswith(b"abc")



def test_bundle_restore_payload_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_payload = b"hello"
    header = container.create_header(
        input_path="hello.txt",
        raw_size=len(file_payload),
        checksum=container.compute_checksum(file_payload),
        relative_path="root/hello.txt",
    )
    payload = bundle.build_bundle_container([(header, file_payload)])

    monkeypatch.setattr(cypher, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(
        bundle,
        "resolve_bundle_output_dir",
        container.resolve_bundle_output_dir,
    )

    bundle.restore_bundle_payload(
        audio_path=Path("payload.flac"),
        restored_payload=payload,
        bundle_checksum=container.compute_checksum(payload),
        output_dir=None,
        bundle_name=None,
    )

    assert (tmp_path / "root" / "hello.txt").read_bytes() == file_payload


def test_bundle_restore_rejects_unsafe_path(tmp_path: Path) -> None:
    file_payload = b"x"
    header = container.create_header(
        input_path="x.txt",
        raw_size=len(file_payload),
        checksum=container.compute_checksum(file_payload),
        relative_path="../x.txt",
    )
    payload = bundle.build_bundle_container([(header, file_payload)])

    with pytest.raises(ValueError, match="Unsafe restore path"):
        bundle.restore_bundle_payload(
            audio_path=Path("payload.flac"),
            restored_payload=payload,
            bundle_checksum="checksum",
            output_dir=tmp_path,
        )


def test_bundle_unbundle_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    monkeypatch.setattr(
        container,
        "decode_command",
        lambda args: calls.append(args.file),
    )

    bundle.unbundle_command(argparse.Namespace(file="payload.flac"))

    assert calls == ["payload.flac"]


def test_audio_read_audio_payload_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = audio.build_audio_payload(
        payload=b"abc",
        header=container.create_header(
            input_path="x.txt",
            raw_size=3,
            checksum=container.compute_checksum(b"abc"),
        ),
    )

    samples = audio.bytes_to_int16_samples(raw)
    monkeypatch.setattr(audio, "read_audio", lambda _path: (44100, samples))

    meta, payload = audio.read_audio_payload("x.flac")

    assert meta["crypto_mode"] == "none"
    assert payload == b"abc"


def test_keys_generate_keypair_success_and_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved = []
    deleted = []

    monkeypatch.setattr(keys, "save_private_key_password_to_keychain", saved.append)
    monkeypatch.setattr(
        keys,
        "delete_private_key_password_from_keychain",
        lambda: deleted.append(True),
    )

    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"

    keys.generate_keypair(private_key, public_key, force=True)

    assert private_key.exists()
    assert public_key.exists()
    assert saved
    assert deleted == [True]


def test_keys_load_private_key_success_and_rejects_public(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    password = "secret"
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"

    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                password.encode()
            ),
        )
    )
    public_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    monkeypatch.setattr(
        keys,
        "load_private_key_password_from_keychain",
        lambda: password,
    )

    assert isinstance(keys.load_private_key(private_path), x25519.X25519PrivateKey)

    with pytest.raises(ValueError):
        keys.load_private_key(public_path)


def test_keys_load_private_key_requires_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_path = tmp_path / "private.pem"
    private_path.write_bytes(b"not-used")

    monkeypatch.setattr(
        keys,
        "load_private_key_password_from_keychain",
        lambda: None,
    )

    with pytest.raises(ValueError, match="Private key password not found"):
        keys.load_private_key(private_path)


def test_keys_require_touch_id_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeContext:
        def canEvaluatePolicy_error_(self, _policy, _error):
            return False, object()

    class FakeLAContext:
        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            return FakeContext()

    monkeypatch.setattr(keys, "LAContext", FakeLAContext)

    with pytest.raises(PermissionError, match="Touch ID is not available"):
        keys.require_touch_id("reason")


def test_keys_require_touch_id_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeContext:
        def canEvaluatePolicy_error_(self, _policy, _error):
            return True, None

        def evaluatePolicy_localizedReason_reply_(self, _policy, _reason, reply):
            reply(False, "nope")

    class FakeLAContext:
        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            return FakeContext()

    monkeypatch.setattr(keys, "LAContext", FakeLAContext)

    with pytest.raises(PermissionError, match="Touch ID authentication failed"):
        keys.require_touch_id("reason")


def test_keys_require_touch_id_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeContext:
        def canEvaluatePolicy_error_(self, _policy, _error):
            return True, None

        def evaluatePolicy_localizedReason_reply_(self, _policy, _reason, reply):
            reply(True, None)

    class FakeLAContext:
        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            return FakeContext()

    monkeypatch.setattr(keys, "LAContext", FakeLAContext)

    keys.require_touch_id("reason")


def test_main_decode_chunked_wrapper_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cypher,
        "_ORIGINAL_CONTAINER_DECODE_CHUNKED",
        lambda payload, private_key: payload + b"-ok",
    )

    assert cypher.decode_chunked_payload(b"x", None) == b"x-ok"
