from argparse import Namespace

import cypher.main as cypher


def test_bundle_command_creates_audio_bundle(tmp_path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    audio_dir = tmp_path / "audio"
    bundle_audio_dir = audio_dir / "bundle"
    waveform_dir = tmp_path / "waveforms"

    for directory in [input_dir, audio_dir, bundle_audio_dir, waveform_dir]:
        directory.mkdir(parents=True)

    project = input_dir / "project"
    project.mkdir()
    (project / "README.md").write_text("hello")
    (project / "main.py").write_text("print('x')")

    monkeypatch.setattr(cypher, "INPUT_DIR", input_dir)
    monkeypatch.setattr(cypher, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(cypher, "BUNDLE_AUDIO_DIR", bundle_audio_dir)
    monkeypatch.setattr(cypher, "WAVEFORM_DIR", waveform_dir)
    monkeypatch.setattr(
        cypher,
        "DEFAULT_PUBLIC_KEY_PATH",
        tmp_path / "missing_public.pem",
    )

    cypher.bundle_command(
        Namespace(
            files=[str(project)],
            name="project",
            format="flac",
            keep_name=True,
            sample_rate=cypher.DEFAULT_SAMPLE_RATE,
            compression_level=cypher.DEFAULT_COMPRESSION_LEVEL,
            public_key=None,
        )
    )

    assert (bundle_audio_dir / "project.flac").exists()


def test_unbundle_command_delegates_to_decode(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(
        cypher,
        "decode_command",
        lambda args: calls.append(args),
    )

    args = Namespace(file="payload.flac", output=None, private_key=None)

    cypher.unbundle_command(args)

    assert calls == [args]
