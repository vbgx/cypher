import pytest

import cypher.gui as gui


@pytest.fixture()
def qapp(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = gui.QApplication.instance()

    if app is None:
        app = gui.QApplication([])

    return app


def test_command_worker_cancel_without_process() -> None:
    worker = gui.CommandWorker(["echo", "ok"])

    worker.cancel()

    assert worker.cancel_requested is True


def test_command_worker_parse_progress_ignores_unknown_line(qapp) -> None:
    worker = gui.CommandWorker(["echo", "ok"])

    received = []

    worker.progress.connect(
        lambda percent, phase, eta: received.append(
            (percent, phase, eta)
        )
    )

    worker.parse_progress("nothing useful here")

    assert received == []


def test_gui_log_matrix_mode(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.theme_select.setCurrentText("Matrix")
    window.log("hello\n")

    assert window.logs.toPlainText()


def test_gui_run_command_when_busy_logs_message(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    class FakeWorker:
        def isRunning(self):
            return True

    window = gui.CypherGui()
    window.worker = FakeWorker()

    window.run_command(["echo", "ok"])

    assert "already running" in window.logs.toPlainText()


def test_gui_encode_or_bundle_without_selection(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.encode_or_bundle()

    assert "No file or folder selected" in window.logs.toPlainText()


def test_gui_inspect_audio_builds_command_again(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    audio = tmp_path / "payload.wav"
    audio.write_text("audio")

    commands = []

    window = gui.CypherGui()
    window.set_audio(audio)
    monkeypatch.setattr(window, "run_command", commands.append)

    window.inspect_audio()

    assert commands[0][3] == "inspect"


def test_gui_cancel_command_terminates_sound_only_if_running(
    qapp,
    monkeypatch,
) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    cancelled = []

    class FakeWorker:
        def isRunning(self):
            return True

        def cancel(self):
            cancelled.append(True)

    class FakeSound:
        def poll(self):
            return 0

        def terminate(self):
            raise AssertionError("should not terminate stopped sound")

    window = gui.CypherGui()
    window.worker = FakeWorker()
    window.sound_process = FakeSound()

    window.cancel_command()

    assert cancelled == [True]
