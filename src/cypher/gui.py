from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal, QTimer
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


CYBER_QSS = """
QMainWindow {
    background: #080A12;
    color: #E6F1FF;
}

QWidget {
    background: #080A12;
    color: #E6F1FF;
    font-family: Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
}

QLabel {
    color: #A7B4C8;
    font-weight: 600;
}

QPushButton {
    background: #111827;
    color: #E6F1FF;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 700;
}

QPushButton:hover {
    background: #1E293B;
    border: 1px solid #A855F7;
    color: #FFFFFF;
}

QPushButton:pressed {
    background: #7C3AED;
    border: 1px solid #F0ABFC;
}

QListWidget, QTextEdit {
    background: #05070D;
    color: #D1E7FF;
    border: 1px solid #1E293B;
    border-radius: 10px;
    padding: 8px;
    selection-background-color: #7C3AED;
}

QProgressBar {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 8px;
    height: 16px;
    text-align: center;
    color: #E6F1FF;
    font-weight: bold;
}

QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #7C3AED,
        stop:0.5 #EC4899,
        stop:1 #22D3EE
    );
    border-radius: 8px;
}

QScrollBar:vertical {
    background: #05070D;
    width: 10px;
}

QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #A855F7;
}
"""

PHASE_WEIGHTS = {
    "scan": (0, 10),
    "read": (10, 30),
    "files": (30, 45),
    "container": (45, 50),
    "chunks": (50, 85),
    "audio": (85, 100),
}


class CommandWorker(QThread):
    output = Signal(str)
    progress = Signal(int, str, str)
    finished_ok = Signal(int)

    def __init__(self, command: list[str]) -> None:
        super().__init__()
        self.command = command
        self.process: subprocess.Popen[str] | None = None
        self.cancel_requested = False
        self.started_at = 0.0
        self.first_progress_seen = False

    def cancel(self) -> None:
        self.cancel_requested = True
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()

    def run(self) -> None:
        self.started_at = time.time()
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
        match = re.search(
            r"PROGRESS\s+phase=([a-zA-Z0-9_-]+)\s+current=(\d+)\s+total=(\d+)",
            line.strip(),
        )

        if match:
            phase = match.group(1)
            current = int(match.group(2))
            total = int(match.group(3))

            percent = self.weighted_percent(
                phase=phase,
                current=current,
                total=total,
            )

            eta = self.compute_eta(percent)

            self.progress.emit(
                percent,
                f"{phase} {current:,}/{total:,}",
                eta,
            )
            return

        chunk_match = re.search(r"Chunk\s+(\d+)/(\d+)", line)

        if chunk_match:
            current = int(chunk_match.group(1))
            total = int(chunk_match.group(2))
            percent = self.weighted_percent("chunks", current, total)
            eta = self.compute_eta(percent)
            self.progress.emit(percent, f"chunks {current}/{total}", eta)
            return

        tqdm_match = re.search(r"(Packing|Unpacking) samples:\s+(\d+)%", line)

        if tqdm_match:
            current = int(tqdm_match.group(2))
            percent = self.weighted_percent("audio", current, 100)
            eta = self.compute_eta(percent)
            self.progress.emit(percent, f"audio {current}/100", eta)

    def weighted_percent(self, phase: str, current: int, total: int) -> int:
        start, end = PHASE_WEIGHTS.get(phase, (0, 100))

        if total <= 0:
            return start

        ratio = max(0.0, min(1.0, current / total))
        return int(start + ratio * (end - start))

    def compute_eta(self, percent: int) -> str:
        if percent <= 0:
            return "ETA: calculating..."

        elapsed = time.time() - self.started_at
        estimated_total = elapsed / (percent / 100)
        remaining = max(0.0, estimated_total - elapsed)

        minutes = int(remaining // 60)
        seconds = int(remaining % 60)

        if minutes:
            return f"ETA: {minutes}m {seconds}s"

        return f"ETA: {seconds}s"


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
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in AUDIO_SUFFIXES:
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
        self.has_real_progress = False
        self.pulse_state = 0

        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.animate_pulse)

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
        self.phase_label = QLabel("Phase: idle")
        self.eta_label = QLabel("ETA: -")

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

        progress_info = QHBoxLayout()
        progress_info.addWidget(self.status_label)
        progress_info.addWidget(self.phase_label)
        progress_info.addWidget(self.eta_label)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Files / folders to encode or bundle"))
        layout.addLayout(top_buttons)
        layout.addWidget(self.files_list)
        layout.addWidget(QLabel("Audio to inspect or restore"))
        layout.addLayout(audio_buttons)
        layout.addWidget(self.audio_label)
        layout.addWidget(QLabel("Progress"))
        layout.addWidget(self.progress_bar)
        layout.addLayout(progress_info)
        layout.addWidget(QLabel("Logs"))
        layout.addWidget(self.logs)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def log(self, text: str) -> None:
        self.logs.moveCursor(self.logs.textCursor().MoveOperation.End)
        self.logs.insertPlainText(text)
        self.logs.moveCursor(self.logs.textCursor().MoveOperation.End)

    def animate_pulse(self) -> None:
        self.pulse_state = (self.pulse_state + 1) % 4
        dots = "." * (self.pulse_state + 1)

        if self.worker is not None and self.worker.isRunning():
            if not self.has_real_progress:
                self.status_label.setText(
                    f"SYSTEM: INITIALIZING PAYLOAD PIPELINE{dots}"
                )

    def update_progress(self, value: int, phase: str, eta: str) -> None:
        if not self.has_real_progress:
            self.has_real_progress = True
            self.progress_bar.setRange(0, 100)

        value = max(0, min(100, value))
        self.progress_bar.setValue(value)
        self.status_label.setText(f"Running... {value}%")
        self.phase_label.setText(f"Phase: {phase}")
        self.eta_label.setText(eta)

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
        self.phase_label.setText("Phase: idle")
        self.eta_label.setText("ETA: -")

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
        self.has_real_progress = False

        self.files_list.clear()
        self.audio_label.setText("Drop FLAC / WAV here or select one")
        self.logs.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")
        self.phase_label.setText("Phase: idle")
        self.eta_label.setText("ETA: -")

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
        self.phase_label.setText("Phase: idle")
        self.eta_label.setText("ETA: -")

    def run_command(self, command: list[str]) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.log("\nA command is already running.\n")
            return

        self.has_real_progress = False
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Preparing and encoding...")
        self.phase_label.setText("Phase: starting")
        self.eta_label.setText("ETA: refining...")

        self.worker = CommandWorker(command)
        self.worker.output.connect(self.log)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished_ok.connect(self.command_finished)
        self.pulse_timer.start(350)
        self.worker.start()

    def command_finished(self, code: int) -> None:
        self.pulse_timer.stop()
        self.progress_bar.setRange(0, 100)

        if code == 0:
            self.progress_bar.setValue(100)
            self.status_label.setText("Done 100%")
            self.phase_label.setText("Phase: completed")
            self.eta_label.setText("ETA: 0s")
        else:
            self.status_label.setText(f"Failed with exit code {code}")
            self.phase_label.setText("Phase: failed")
            self.eta_label.setText("ETA: -")

        if code == 0:
            self.log("\nOperation completed successfully.\n")
        else:
            self.log(f"\nOperation failed with exit code {code}.\n")

    def cancel_command(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            self.log("No command running.\n")
            return

        self.worker.cancel()
        self.status_label.setText("Cancelling...")
        self.phase_label.setText("Phase: cancelling")
        self.eta_label.setText("ETA: -")
        self.pulse_timer.stop()
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
    app.setStyleSheet(CYBER_QSS)
    window = CypherGui()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
