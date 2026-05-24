
import pytest

import cypher.gui as gui


@pytest.fixture()
def qapp(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = gui.QApplication.instance()

    if app is None:
        app = gui.QApplication([])

    return app


def test_format_size() -> None:
    assert gui.format_size(0) == "0.0 B"
    assert gui.format_size(1024) == "1.0 KB"
    assert gui.format_size(1024 * 1024) == "1.0 MB"


def test_matrix_line_returns_randomized_line() -> None:
    line = gui.matrix_line("hello")

    assert line.endswith("\n")
    assert len(line.strip()) >= 72


def test_command_worker_weighted_percent() -> None:
    worker = gui.CommandWorker(["echo", "ok"])

    assert worker.weighted_percent("chunks", 0, 100) == 50
    assert worker.weighted_percent("chunks", 100, 100) == 85
    assert worker.weighted_percent("unknown", 50, 100) == 50
    assert worker.weighted_percent("chunks", 1, 0) == 50


def test_command_worker_compute_eta() -> None:
    worker = gui.CommandWorker(["echo", "ok"])
    worker.started_at = gui.time.time() - 1

    assert worker.compute_eta(0) == "ETA: calculating..."
    assert worker.compute_eta(100) == "ETA: 0s"


def test_command_worker_parse_progress_emits_signal(qapp) -> None:
    worker = gui.CommandWorker(["echo", "ok"])
    worker.started_at = gui.time.time() - 1

    received = []

    worker.progress.connect(
        lambda percent, phase, eta: received.append(
            (percent, phase, eta)
        )
    )

    worker.parse_progress("PROGRESS phase=chunks current=5 total=10")

    assert received
    assert received[0][0] > 50
    assert received[0][1] == "chunks 5/10"


def test_command_worker_parse_chunk_line_emits_signal(qapp) -> None:
    worker = gui.CommandWorker(["echo", "ok"])
    worker.started_at = gui.time.time() - 1

    received = []

    worker.progress.connect(
        lambda percent, phase, eta: received.append(
            (percent, phase, eta)
        )
    )

    worker.parse_progress("Chunk 2/4")

    assert received
    assert received[0][1] == "chunks 2/4"


def test_command_worker_parse_tqdm_line_emits_signal(qapp) -> None:
    worker = gui.CommandWorker(["echo", "ok"])
    worker.started_at = gui.time.time() - 1

    received = []

    worker.progress.connect(
        lambda percent, phase, eta: received.append(
            (percent, phase, eta)
        )
    )

    worker.parse_progress("Packing samples: 42%")

    assert received
    assert received[0][1] == "audio 42/100"


def test_gui_initial_state(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()

    assert window.current_theme() == "Obsidian Purple"
    assert window.selected_paths == []
    assert window.selected_audio is None
    assert window.selected_public_keys == []


def test_gui_add_and_clear_paths(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    file_path = tmp_path / "payload.txt"
    file_path.write_text("payload")

    window = gui.CypherGui()
    window.add_paths([file_path])

    assert window.selected_paths == [file_path.resolve()]
    assert "ITEMS: 1" in window.metric_items.text()
    assert "MODE: SINGLE" in window.metric_mode.text()

    window.clear_selection()

    assert window.selected_paths == []
    assert window.selected_public_keys == []
    assert window.selected_audio is None


def test_gui_bundle_mode_for_folder(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file.txt").write_text("payload")

    window = gui.CypherGui()
    window.add_paths([folder])

    assert "MODE: BUNDLE" in window.metric_mode.text()
    assert "ITEMS: 1" in window.metric_items.text()


def test_gui_public_key_args(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    key_a = tmp_path / "alice.pem"
    key_b = tmp_path / "bob.pem"

    key_a.write_text("a")
    key_b.write_text("b")

    window = gui.CypherGui()
    window.selected_public_keys = [key_a, key_b]

    assert window.public_key_args() == [
        "--public-key",
        str(key_a),
        "--public-key",
        str(key_b),
    ]


def test_gui_set_audio_rejects_unsupported_suffix(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.set_audio(tmp_path / "bad.mp3")

    assert window.selected_audio is None


def test_gui_set_audio_accepts_flac(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    audio = tmp_path / "payload.flac"
    audio.write_text("audio")

    window = gui.CypherGui()
    window.set_audio(audio)

    assert window.selected_audio == audio.resolve()
    assert str(audio.resolve()) in window.audio_label.text()


def test_gui_capture_artifact_from_log(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    audio = tmp_path / "payload.flac"

    window = gui.CypherGui()
    window.capture_artifact_from_log(f"Audio             : {audio}\n")

    assert window.last_artifact == audio
    assert str(audio) in window.artifact_label.text()


def test_gui_update_artifact_preview_from_log(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.update_artifact_preview_from_log(
        "Encryption        : x25519-aesgcm-multi"
    )

    assert "x25519-aesgcm-multi" in window.preview_label.text()


def test_gui_open_artifact_folder_without_artifact(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.open_artifact_folder()

    assert window.last_artifact is None


def test_gui_open_artifact_folder_runs_open(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    calls = []

    monkeypatch.setattr(
        gui.subprocess,
        "run",
        lambda command, check: calls.append((command, check)),
    )

    audio = tmp_path / "payload.flac"

    window = gui.CypherGui()
    window.last_artifact = audio
    window.open_artifact_folder()

    assert calls == [(["open", str(audio.parent)], False)]


def test_gui_run_command_refuses_when_worker_running(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    class FakeWorker:
        def isRunning(self):
            return True

    window = gui.CypherGui()
    window.worker = FakeWorker()

    window.run_command(["echo", "ok"])

    assert window.worker is not None


def test_gui_encode_or_bundle_builds_encode_command(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    payload = tmp_path / "payload.txt"
    payload.write_text("payload")

    commands = []

    window = gui.CypherGui()
    window.add_paths([payload])
    monkeypatch.setattr(
        window,
        "run_command",
        lambda command: commands.append(command),
    )

    window.encode_or_bundle()

    assert commands
    assert "encode" in commands[0]
    assert str(payload.resolve()) in commands[0]


def test_gui_encode_or_bundle_builds_bundle_command(
    qapp,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    folder = tmp_path / "folder"
    folder.mkdir()

    commands = []

    window = gui.CypherGui()
    window.add_paths([folder])
    monkeypatch.setattr(
        window,
        "run_command",
        lambda command: commands.append(command),
    )

    window.encode_or_bundle()

    assert commands
    assert "bundle" in commands[0]


def test_gui_inspect_audio_requires_selection(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.inspect_audio()

    assert window.selected_audio is None


def test_gui_decode_audio_builds_command(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    audio = tmp_path / "payload.flac"
    audio.write_text("audio")

    commands = []

    window = gui.CypherGui()
    window.set_audio(audio)
    monkeypatch.setattr(
        window,
        "run_command",
        lambda command: commands.append(command),
    )

    window.decode_audio()

    assert commands
    assert "decode" in commands[0]
    assert str(audio.resolve()) in commands[0]


def test_gui_cancel_command_without_worker(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.cancel_command()

    assert window.worker is None


def test_gui_command_finished_success(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.command_finished(0)

    assert window.progress_bar.value() == 100
    assert "COMPLETE" in window.status_label.text()


def test_gui_command_finished_failure(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.command_finished(9)

    assert "FAILED" in window.status_label.text()


def test_gui_update_progress(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.update_progress(42, "chunks", "ETA: 1s")

    assert window.progress_bar.value() == 42
    assert "CHUNKS" in window.phase_label.text()
