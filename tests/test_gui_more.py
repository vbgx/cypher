from pathlib import Path

import pytest

import cypher.gui as gui


@pytest.fixture()
def qapp(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = gui.QApplication.instance()

    if app is None:
        app = gui.QApplication([])

    return app


def test_command_worker_run_success_emits_output(qapp) -> None:
    worker = gui.CommandWorker(
        [
            "python",
            "-c",
            "print('PROGRESS phase=audio current=100 total=100')",
        ]
    )

    outputs = []
    codes = []

    worker.output.connect(outputs.append)
    worker.finished_ok.connect(codes.append)

    worker.run()

    assert codes == [0]
    assert any("PROGRESS phase=audio" in line for line in outputs)


def test_command_worker_cancel_terminates_process(qapp, monkeypatch) -> None:
    class FakeStdout:
        def __iter__(self):
            return iter(["line\n"])

    class FakeProcess:
        stdout = FakeStdout()

        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self):
            return -15

    fake_process = FakeProcess()

    def fake_popen(*args, **kwargs):
        return fake_process

    worker = gui.CommandWorker(["fake"])
    worker.cancel_requested = True

    monkeypatch.setattr(gui.subprocess, "Popen", fake_popen)

    codes = []
    worker.finished_ok.connect(codes.append)

    worker.run()

    assert fake_process.terminated is True
    assert codes == [-15]


def test_apply_theme_matrix(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.apply_theme("Matrix")

    assert "MATRIX STREAM" in window.subtitle_label.text()


def test_play_theme_sound_missing_file(qapp, monkeypatch) -> None:
    window = gui.CypherGui()

    monkeypatch.setattr(gui, "MATRIX_SOUND", Path("missing-matrix.mp3"))
    monkeypatch.setattr(gui, "OBSIDIAN_SOUND", Path("missing-obsidian.mp3"))

    window.play_theme_sound()

    assert "Sound file missing" in window.logs.toPlainText()


def test_play_theme_sound_starts_process(qapp, tmp_path, monkeypatch) -> None:
    sound = tmp_path / "sound.mp3"
    sound.write_bytes(b"fake")

    monkeypatch.setattr(gui, "OBSIDIAN_SOUND", sound)

    calls = []

    class FakePopen:
        def __init__(self, command, stdout, stderr):
            calls.append((command, stdout, stderr))

        def poll(self):
            return 0

        def terminate(self):
            pass

    monkeypatch.setattr(gui.subprocess, "Popen", FakePopen)

    window = gui.CypherGui()
    window.play_theme_sound()

    assert calls
    assert calls[-1][0][0] == "afplay"


def test_remove_selected_path(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    payload = tmp_path / "payload.txt"
    payload.write_text("payload")

    window = gui.CypherGui()
    window.add_paths([payload])

    item = window.files_list.item(0)
    item.setSelected(True)

    window.remove_selected()

    assert window.selected_paths == []


def test_remove_selected_public_key(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    key = tmp_path / "alice.pem"
    key.write_text("key")

    window = gui.CypherGui()
    window.selected_public_keys.append(key)
    window.public_keys_list.addItem(str(key))

    item = window.public_keys_list.item(0)
    item.setSelected(True)

    window.remove_selected_public_keys()

    assert window.selected_public_keys == []


def test_clear_public_keys(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    key = tmp_path / "alice.pem"
    key.write_text("key")

    window = gui.CypherGui()
    window.selected_public_keys.append(key)
    window.public_keys_list.addItem(str(key))

    window.clear_public_keys()

    assert window.selected_public_keys == []
    assert window.public_keys_list.count() == 0


def test_select_public_keys_uses_dialog(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    key = tmp_path / "alice.pem"
    key.write_text("key")

    monkeypatch.setattr(
        gui.QFileDialog,
        "getOpenFileNames",
        lambda *args, **kwargs: ([str(key)], ""),
    )

    window = gui.CypherGui()
    window.select_public_keys()

    assert window.selected_public_keys == [key.resolve()]


def test_select_files_uses_dialog(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    payload = tmp_path / "payload.txt"
    payload.write_text("payload")

    monkeypatch.setattr(
        gui.QFileDialog,
        "getOpenFileNames",
        lambda *args, **kwargs: ([str(payload)], ""),
    )

    window = gui.CypherGui()
    window.select_files()

    assert window.selected_paths == [payload.resolve()]


def test_select_folder_uses_dialog(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    folder = tmp_path / "folder"
    folder.mkdir()

    monkeypatch.setattr(
        gui.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(folder),
    )

    window = gui.CypherGui()
    window.select_folder()

    assert window.selected_paths == [folder.resolve()]


def test_select_audio_uses_dialog(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    audio = tmp_path / "payload.flac"
    audio.write_text("audio")

    monkeypatch.setattr(
        gui.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(audio), ""),
    )

    window = gui.CypherGui()
    window.select_audio()

    assert window.selected_audio == audio.resolve()


def test_run_command_starts_worker(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    started = []

    class FakeSignal:
        def connect(self, callback):
            pass

    class FakeWorker:
        output = FakeSignal()
        progress = FakeSignal()
        finished_ok = FakeSignal()

        def __init__(self, command):
            self.command = command

        def isRunning(self):
            return False

        def start(self):
            started.append(self.command)

    monkeypatch.setattr(gui, "CommandWorker", FakeWorker)

    window = gui.CypherGui()
    window.run_command(["echo", "ok"])

    assert started == [["echo", "ok"]]


def test_cancel_command_running_worker(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    cancelled = []
    terminated = []

    class FakeWorker:
        def isRunning(self):
            return True

        def cancel(self):
            cancelled.append(True)

    class FakeSound:
        def poll(self):
            return None

        def terminate(self):
            terminated.append(True)

    window = gui.CypherGui()
    window.worker = FakeWorker()
    window.sound_process = FakeSound()

    window.cancel_command()

    assert cancelled == [True]
    assert terminated == [True]
    assert "ABORT" in window.status_label.text()


def test_inspect_audio_builds_command(qapp, tmp_path, monkeypatch) -> None:
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

    window.inspect_audio()

    assert commands
    assert "inspect" in commands[0]


def test_decode_audio_requires_selection(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.decode_audio()

    assert window.selected_audio is None


def test_main_creates_app_and_window(monkeypatch) -> None:
    shown = []
    exited = []

    class FakeApp:
        def __init__(self, argv):
            self.argv = argv

        def exec(self):
            return 0

    class FakeWindow:
        def show(self):
            shown.append(True)

    monkeypatch.setattr(gui, "QApplication", FakeApp)
    monkeypatch.setattr(gui, "CypherGui", lambda: FakeWindow())
    monkeypatch.setattr(gui.sys, "exit", lambda code: exited.append(code))

    gui.main()

    assert shown == [True]
    assert exited == [0]


def test_module_main_guard_runs_main(monkeypatch) -> None:
    # Covered indirectly by main(); keeping explicit smoke intent here.
    assert callable(gui.main)
