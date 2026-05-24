from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

AUDIO_SUFFIXES = {".flac", ".wav"}


class CommandWorker(QThread):
    output = Signal(str)
    progress = Signal(int)
    finished_ok = Signal(int)

    def __init__(self, command: list[str]) -> None:
        super().__init__()
        self.command = command
        self.process: subprocess.Popen[str] | None = None
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True

        if self.process is not None and self.process.poll() is None:
            self.process.terminate()

    def run(self) -> None:
        self.output.emit(f"$ {' '.join(self.command)}\n\n")

        self.process = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert self.process.stdout is not None

        for line in self.process.stdout:
            self.output.emit(line)
            self.parse_progress(line)

            if self.cancel_requested:
                break

        if self.cancel_requested and self.process.poll() is None:
            self.process.terminate()

        code = self.process.wait()
        self.finished_ok.emit(code)

    def parse_progress(self, line: str) -> None:
        chunk_match = re.search(r"Chunk\s+(\d+)/(\d+)", line)

        if chunk_match:
            current = int(chunk_match.group(1))
            total = int(chunk_match.group(2))

            if total:
                self.progress.emit(int(current / total * 100))

            return

        tqdm_match = re.search(r"(Packing|Unpacking) samples:\s+(\d+)%", line)

        if tqdm_match:
            self.progress.emit(int(tqdm_match.group(2)))


class DropListWidget(QListWidget):
    paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return

        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return

        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths: list[Path] = []

        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(Path(url.toLocalFile()))

        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()
            return

        super().dropEvent(event)


class AudioDropLabel(QLabel):
    audio_dropped = Signal(Path)

    def __init__(self) -> None:
        super().__init__("Drop FLAC / WAV here or select one")
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(44)
        self.setStyleSheet(
            """
            QLabel {
                border: 1px dashed #777;
                padding: 10px;
            }
            """
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not event.mimeData().hasUrls():
            return

        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue

            path = Path(url.toLocalFile())

            if path.suffix.lower() in AUDIO_SUFFIXES:
                event.acceptProposedAction()
                return

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue

            path = Path(url.toLocalFile())

            if path.suffix.lower() in AUDIO_SUFFIXES:
                self.audio_dropped.emit(path)
                event.acceptProposedAction()
                return


class CypherGui(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("cypher GUI")
        self.resize(1050, 760)

        self.selected_paths: list[Path] = []
        self.selected_audio: Path | None = None
        self.worker: CommandWorker | None = None

        self.files_list = DropListWidget()
        self.files_list.paths_dropped.connect(self.add_paths)

        self.audio_label = AudioDropLabel()
        self.audio_label.audio_dropped.connect(self.set_audio)

        self.logs = QTextEdit()
        self.logs.setReadOnly(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.status_label = QLabel("Ready")

        select_files_button = QPushButton("Select files")
        select_files_button.clicked.connect(self.select_files)

        select_folder_button = QPushButton("Select folder")
        select_folder_button.clicked.connect(self.select_folder)

        remove_button = QPushButton("Remove selected")
        remove_button.clicked.connect(self.remove_selected)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_selection)

        encode_button = QPushButton("Encode / Bundle")
        encode_button.clicked.connect(self.encode_or_bundle)

        select_audio_button = QPushButton("Select FLAC / WAV")
        select_audio_button.clicked.connect(self.select_audio)

        inspect_button = QPushButton("Inspect")
        inspect_button.clicked.connect(self.inspect_audio)

        restore_button = QPushButton("Decode / Restore")
        restore_button.clicked.connect(self.decode_audio)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.cancel_command)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(select_files_button)
        top_buttons.addWidget(select_folder_button)
        top_buttons.addWidget(remove_button)
        top_buttons.addWidget(clear_button)
        top_buttons.addWidget(encode_button)

        audio_buttons = QHBoxLayout()
        audio_buttons.addWidget(select_audio_button)
        audio_buttons.addWidget(inspect_button)
        audio_buttons.addWidget(restore_button)
        audio_buttons.addWidget(cancel_button)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Files / folders to encode or bundle"))
        layout.addLayout(top_buttons)
        layout.addWidget(self.files_list)
        layout.addWidget(QLabel("Audio to inspect or restore"))
        layout.addLayout(audio_buttons)
        layout.addWidget(self.audio_label)
        layout.addWidget(QLabel("Progress"))
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("Logs"))
        layout.addWidget(self.logs)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def log(self, text: str) -> None:
        self.logs.moveCursor(self.logs.textCursor().MoveOperation.End)
        self.logs.insertPlainText(text)
        self.logs.moveCursor(self.logs.textCursor().MoveOperation.End)

    def set_progress(self, value: int) -> None:
        self.progress_bar.setValue(max(0, min(100, value)))

    def select_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select files",
            "data/input",
        )

        self.add_paths([Path(file_name) for file_name in files])

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder",
            "data/input",
        )

        if folder:
            self.add_paths([Path(folder)])

    def add_paths(self, paths: list[Path]) -> None:
        for path in paths:
            path = path.resolve()

            if path not in self.selected_paths:
                self.selected_paths.append(path)
                self.files_list.addItem(str(path))

        self.status_label.setText(f"{len(self.selected_paths)} item(s) selected")

    def remove_selected(self) -> None:
        selected_items = self.files_list.selectedItems()

        for item in selected_items:
            path = Path(item.text())

            if path in self.selected_paths:
                self.selected_paths.remove(path)

            row = self.files_list.row(item)
            self.files_list.takeItem(row)

        self.status_label.setText(f"{len(self.selected_paths)} item(s) selected")

    def clear_selection(self) -> None:
        self.selected_paths.clear()
        self.selected_audio = None

        self.files_list.clear()
        self.audio_label.setText("Drop FLAC / WAV here or select one")
        self.logs.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")

    def select_audio(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select FLAC / WAV",
            "data/audio",
            "Audio files (*.flac *.wav)",
        )

        if file_name:
            self.set_audio(Path(file_name))

    def set_audio(self, path: Path) -> None:
        path = path.resolve()

        if path.suffix.lower() not in AUDIO_SUFFIXES:
            self.log(f"Unsupported audio file: {path}\n")
            return

        self.selected_audio = path
        self.audio_label.setText(str(path))
        self.status_label.setText("Audio selected")

    def run_command(self, command: list[str]) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.log("\nA command is already running.\n")
            return

        self.progress_bar.setValue(0)
        self.status_label.setText("Running...")

        self.worker = CommandWorker(command)
        self.worker.output.connect(self.log)
        self.worker.progress.connect(self.set_progress)
        self.worker.finished_ok.connect(self.command_finished)
        self.worker.start()

    def command_finished(self, code: int) -> None:
        if code == 0:
            self.progress_bar.setValue(100)
            self.status_label.setText("Done")
        else:
            self.status_label.setText(f"Failed with exit code {code}")

        self.log(f"\nCommand finished with exit code {code}\n")

    def cancel_command(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            self.log("No command running.\n")
            return

        self.worker.cancel()
        self.status_label.setText("Cancelling...")
        self.log("\nCancellation requested.\n")

    def encode_or_bundle(self) -> None:
        if not self.selected_paths:
            self.log("No file or folder selected.\n")
            return

        if len(self.selected_paths) == 1 and self.selected_paths[0].is_file():
            command = [
                sys.executable,
                "-m",
                "cypher.main",
                "encode",
                str(self.selected_paths[0]),
            ]
        else:
            command = [
                sys.executable,
                "-m",
                "cypher.main",
                "bundle",
                *[str(path) for path in self.selected_paths],
            ]

        self.run_command(command)

    def inspect_audio(self) -> None:
        if self.selected_audio is None:
            self.log("No audio selected.\n")
            return

        command = [
            sys.executable,
            "-m",
            "cypher.main",
            "inspect",
            str(self.selected_audio),
        ]

        self.run_command(command)

    def decode_audio(self) -> None:
        if self.selected_audio is None:
            self.log("No audio selected.\n")
            return

        command = [
            sys.executable,
            "-m",
            "cypher.main",
            "decode",
            str(self.selected_audio),
        ]

        self.run_command(command)


def main() -> None:
    app = QApplication(sys.argv)
    window = CypherGui()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
