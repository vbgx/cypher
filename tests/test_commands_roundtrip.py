from argparse import Namespace

import cypher.main as cypher


def test_encode_command_creates_audio_file(tmp_path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    audio_dir = tmp_path / "audio"
    waveform_dir = tmp_path / "waveforms"

    input_dir.mkdir()
    audio_dir.mkdir()
    waveform_dir.mkdir()

    payload = input_dir / "secret.txt"
    payload.write_bytes(b"hello from command")

    monkeypatch.setattr(cypher, "INPUT_DIR", input_dir)
    monkeypatch.setattr(cypher, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(cypher, "WAVEFORM_DIR", waveform_dir)
    monkeypatch.setattr(
        cypher,
        "DEFAULT_PUBLIC_KEY_PATH",
        tmp_path / "missing_public.pem",
    )

    args = Namespace(
        file=str(payload),
        format="flac",
        keep_name=True,
        sample_rate=cypher.DEFAULT_SAMPLE_RATE,
        compression_level=cypher.DEFAULT_COMPRESSION_LEVEL,
        public_key=None,
    )

    cypher.encode_command(args)

    audio_file = audio_dir / "secret.flac"
    waveform_file = waveform_dir / "secret.pgm"

    assert audio_file.exists()
    assert waveform_file.exists()


def test_decode_command_restores_file_no_crypto(tmp_path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    audio_dir = tmp_path / "audio"
    output_dir = tmp_path / "output"
    waveform_dir = tmp_path / "waveforms"

    for directory in [input_dir, audio_dir, output_dir, waveform_dir]:
        directory.mkdir()

    payload = input_dir / "note.txt"
    payload.write_bytes(b"decode command roundtrip")

    monkeypatch.setattr(cypher, "INPUT_DIR", input_dir)
    monkeypatch.setattr(cypher, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(cypher, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(cypher, "WAVEFORM_DIR", waveform_dir)
    monkeypatch.setattr(
        cypher,
        "DEFAULT_PUBLIC_KEY_PATH",
        tmp_path / "missing_public.pem",
    )
    monkeypatch.setattr(cypher, "require_touch_id", lambda _reason: None)

    encode_args = Namespace(
        file=str(payload),
        format="flac",
        keep_name=True,
        sample_rate=cypher.DEFAULT_SAMPLE_RATE,
        compression_level=cypher.DEFAULT_COMPRESSION_LEVEL,
        public_key=None,
    )

    cypher.encode_command(encode_args)

    decode_args = Namespace(
        file=str(audio_dir / "note.flac"),
        output=None,
        private_key=None,
    )

    cypher.decode_command(decode_args)

    assert (output_dir / "note.txt").read_bytes() == b"decode command roundtrip"


def test_inspect_command_reads_audio_metadata(tmp_path, monkeypatch, capsys) -> None:
    input_dir = tmp_path / "input"
    audio_dir = tmp_path / "audio"
    waveform_dir = tmp_path / "waveforms"

    for directory in [input_dir, audio_dir, waveform_dir]:
        directory.mkdir()

    payload = input_dir / "public.txt"
    payload.write_bytes(b"inspect me")

    monkeypatch.setattr(cypher, "INPUT_DIR", input_dir)
    monkeypatch.setattr(cypher, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(cypher, "WAVEFORM_DIR", waveform_dir)
    monkeypatch.setattr(
        cypher,
        "DEFAULT_PUBLIC_KEY_PATH",
        tmp_path / "missing_public.pem",
    )

    cypher.encode_command(
        Namespace(
            file=str(payload),
            format="flac",
            keep_name=True,
            sample_rate=cypher.DEFAULT_SAMPLE_RATE,
            compression_level=cypher.DEFAULT_COMPRESSION_LEVEL,
            public_key=None,
        )
    )

    cypher.inspect_command(Namespace(file=str(audio_dir / "public.flac")))

    output = capsys.readouterr().out

    assert "Cypher payload" in output
    assert "Encryption     : none" in output
    assert "Original name  : public.txt" in output
