import pytest

import cypher.gui as gui


@pytest.fixture()
def qapp(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = gui.QApplication.instance()

    if app is None:
        app = gui.QApplication([])

    return app


def test_command_worker_cancel_while_process_exists() -> None:
    class FakeProcess:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    worker = gui.CommandWorker(["fake"])
    worker.process = FakeProcess()

    worker.cancel()

    assert worker.cancel_requested is True
    assert worker.process.terminated is True


def test_command_worker_compute_eta_minutes() -> None:
    worker = gui.CommandWorker(["echo", "ok"])
    worker.started_at = gui.time.time() - 3600

    eta = worker.compute_eta(50)

    assert eta.startswith("ETA:")
    assert "m" in eta


def test_gui_apply_theme_without_qapplication(monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()

    monkeypatch.setattr(gui.QApplication, "instance", lambda: None)

    window.apply_theme("Obsidian Purple")

    assert "AUDIO PAYLOAD CONTROL" in window.subtitle_label.text()


def test_gui_update_dashboard_idle_no_recipients(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.update_dashboard()

    assert "IDLE" in window.metric_mode.text()
    assert "AUTO" in window.metric_crypto.text()


def test_gui_select_folder_empty_dialog(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)
    monkeypatch.setattr(
        gui.QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: "",
    )

    window = gui.CypherGui()
    window.select_folder()

    assert window.selected_paths == []


def test_gui_select_audio_empty_dialog(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)
    monkeypatch.setattr(
        gui.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: ("", ""),
    )

    window = gui.CypherGui()
    window.select_audio()

    assert window.selected_audio is None
