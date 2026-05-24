import pytest

import cypher.gui as gui


@pytest.fixture()
def qapp(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = gui.QApplication.instance()

    if app is None:
        app = gui.QApplication([])

    return app


def test_command_worker_cancel_when_process_already_done() -> None:
    class FakeProcess:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return 0

        def terminate(self):
            self.terminated = True

    worker = gui.CommandWorker(["fake"])
    worker.process = FakeProcess()

    worker.cancel()

    assert worker.cancel_requested is True
    assert worker.process.terminated is False


def test_command_worker_run_cancel_branch_after_stdout(
    qapp,
    monkeypatch,
) -> None:
    class FakeStdout:
        def __iter__(self):
            return iter(["line\n", "line2\n"])

    class FakeProcess:
        stdout = FakeStdout()

        def __init__(self):
            self.terminated = False
            self._poll = None

        def poll(self):
            return self._poll

        def terminate(self):
            self.terminated = True
            self._poll = -15

        def wait(self):
            return -15

    fake_process = FakeProcess()

    monkeypatch.setattr(
        gui.subprocess,
        "Popen",
        lambda *args, **kwargs: fake_process,
    )

    worker = gui.CommandWorker(["fake"])

    def cancel_on_output(_line):
        worker.cancel_requested = True

    worker.output.connect(cancel_on_output)

    codes = []
    worker.finished_ok.connect(codes.append)

    worker.run()

    assert fake_process.terminated is True
    assert codes == [-15]


def test_gui_log_obsidian_mode(qapp, monkeypatch) -> None:
    monkeypatch.setattr(gui.CypherGui, "play_theme_sound", lambda self: None)

    window = gui.CypherGui()
    window.theme_select.setCurrentText("Obsidian Purple")
    window.log("plain log\n")

    assert "plain log" in window.logs.toPlainText()
