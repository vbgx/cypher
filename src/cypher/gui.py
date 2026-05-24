from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class CommandWorker(QThread):
    output = Signal(str)
    finished_ok = Signal(int)

    def __init__(self, command: list[str]) -> None:
        super().__init__()
        self.command = command

    def run(self) -> None:
        self.output.emit(f"$ {' '.join(self.command)}\n")

        process = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert process.stdout is not None

        for line in process.stdout:
            self.output.emit(line)

        code = process.wait()
        self.finished_ok.emit(code)


class CypherGui(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("cypher GUI")
        self.resize(900, 650)

        self.selected_paths: list[Path] = []
        self.selected_audio: Path | None = None
        self.worker: CommandWorker | None = None

        self.files_list = QListWidget()
        self.audio_label = QLabel("No audio selected")

        self.logs = QTextEdit()
        self.logs.setReadOnly(True)

        select_files_button = QPushButton("Select files")
        select_files_button.clicked.connect(self.select_files)

        select_folder_button = QPushButton("Select folder")
        select_folder_button.clicked.connect(self.select_folder)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_selection)

        encode_button = QPushButton("Encode / Bundle")
        encode_button.clicked.connect(self.encode_or_bundle)

        select_audio_button = QPushButton("Select FLAC / WAV")
        select_audio_button.clicked.connect(self.select_audio)

        decode_button = QPushButton("Decode")
        decode_button.clicked.connect(self.decode_audio)

        unbundle_button = QPushButton("Unbundle")
        unbundle_button.clicked.connect(self.unbundle_audio)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(select_files_button)
        top_buttons.addWidget(select_folder_button)
        top_buttons.addWidget(clear_button)
        top_buttons.addWidget(encode_button)

        audio_buttons = QHBoxLayout()
        audio_buttons.addWidget(select_audio_button)
        audio_buttons.addWidget(decode_button)
        audio_buttons.addWidget(unbundle_button)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Files / folders to encode or bundle"))
        layout.addLayout(top_buttons)
        layout.addWidget(self.files_list)
        layout.addWidget(QLabel("Audio to decode or unbundle"))
        layout.addLayout(audio_buttons)
        layout.addWidget(self.audio_label)
        layout.addWidget(QLabel("Logs"))
        layout.addWidget(self.logs)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

    def log(self, text: str) -> None:
        self.logs.moveCursor(self.logs.textCursor().MoveOperation.End)
        self.logs.insertPlainText(text)
        self.logs.moveCursor(self.logs.textCursor().MoveOperation.End)

    def select_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select files",
            "data/input",
        )

        for file_name in files:
            path = Path(file_name)
            if path not in self.selected_paths:
                self.selected_paths.append(path)
                self.files_list.addItem(str(path))

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder",
            "data/input",
        )

        if not folder:
            return

        root = Path(folder)

        files = [
            path
            for path in root.rglob("*")
            if path.is_file()
        ]

        for path in files:
            if path not in self.selected_paths:
                self.selected_paths.append(path)
                self.files_list.addItem(str(path))

    def select_audio(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select FLAC / WAV",
            "data/audio",
            "Audio files (*.flac *.wav)",
        )

        if not file_name:
            return

        self.selected_audio = Path(file_name)
        self.audio_label.setText(str(self.selected_audio))

    def clear_selection(self) -> None:
        self.selected_paths.clear()
        self.selected_audio = None
        self.files_list.clear()
        self.audio_label.setText("No audio selected")
        self.logs.clear()

    def run_command(self, command: list[str]) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.log("\nA command is already running.\n")
            return

        self.worker = CommandWorker(command)
        self.worker.output.connect(self.log)
        self.worker.finished_ok.connect(self.command_finished)
        self.worker.start()

    def command_finished(self, code: int) -> None:
        self.log(f"\nCommand finished with exit code {code}\n")

    def encode_or_bundle(self) -> None:
        if not self.selected_paths:
            self.log("No file selected.\n")
            return

        if len(self.selected_paths) == 1:
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

    def unbundle_audio(self) -> None:
        if self.selected_audio is None:
            self.log("No audio selected.\n")
            return

        command = [
            sys.executable,
            "-m",
            "cypher.main",
            "unbundle",
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
