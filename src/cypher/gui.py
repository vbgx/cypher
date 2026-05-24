from __future__ import annotations

import random
import re
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
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

MATRIX_ALPHABET = "01░▒▓█◇◆◈▣▤▥▦▧▨▩<>[]{}#$%&@+-*/=|:;"

SOUND_DIR = Path("src/sounds_library")
MATRIX_SOUND = SOUND_DIR / "matrix.mp3"
OBSIDIAN_SOUND = SOUND_DIR / "unlimited_power.mp3"

ASCII_CYPHER = r"""
 ██████╗██╗   ██╗██████╗ ██╗  ██╗███████╗██████╗
██╔════╝╚██╗ ██╔╝██╔══██╗██║  ██║██╔════╝██╔══██╗
██║      ╚████╔╝ ██████╔╝███████║█████╗  ██████╔╝
██║       ╚██╔╝  ██╔═══╝ ██╔══██║██╔══╝  ██╔══██╗
╚██████╗   ██║   ██║     ██║  ██║███████╗██║  ██║
 ╚═════╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""

THEMES = {
    "Obsidian Purple": """
QMainWindow, QWidget {
    background:#080A12;
    color:#E6F1FF;
    font-family:Menlo, Monaco, Consolas, monospace;
    font-size:12px;
}
QLabel {
    color:#A7B4C8;
    font-weight:700;
}
QPushButton {
    background:#111827;
    color:#E6F1FF;
    border:1px solid #334155;
    border-radius:9px;
    padding:8px 12px;
    font-weight:800;
}
QPushButton:hover {
    background:#1E293B;
    border:1px solid #A855F7;
    color:#FFFFFF;
}
QPushButton:pressed {
    background:#7C3AED;
    border:1px solid #F0ABFC;
}
QListWidget, QTextEdit, QComboBox {
    background:#05070D;
    color:#D1E7FF;
    border:1px solid #1E293B;
    border-radius:10px;
    padding:8px;
    selection-background-color:#7C3AED;
}
QProgressBar {
    background:#111827;
    border:1px solid #334155;
    border-radius:8px;
    height:16px;
    text-align:center;
    color:#E6F1FF;
    font-weight:bold;
}
QProgressBar::chunk {
    background:qlineargradient(
        x1:0,y1:0,x2:1,y2:0,
        stop:0 #7C3AED,
        stop:.5 #EC4899,
        stop:1 #22D3EE
    );
    border-radius:8px;
}
QFrame#Panel {
    background:#0B1020;
    border:1px solid #1E293B;
    border-radius:14px;
}
QLabel#AsciiTitle {
    color:#E879F9;
    font-size:10px;
    font-weight:900;
}
QLabel#Subtitle {
    color:#22D3EE;
    font-size:12px;
}
QLabel#Metric {
    color:#E6F1FF;
    background:#111827;
    border:1px solid #334155;
    border-radius:10px;
    padding:8px;
}
QLabel#Artifact {
    color:#BBF7D0;
    background:#052E16;
    border:1px solid #16A34A;
    border-radius:10px;
    padding:10px;
}
""",
    "Matrix": """
QMainWindow, QWidget {
    background:#000000;
    color:#BBF7D0;
    font-family:Menlo, Monaco, Consolas, monospace;
    font-size:12px;
}
QLabel {
    color:#22C55E;
    font-weight:800;
}
QPushButton {
    background:#031A0A;
    color:#BBF7D0;
    border:1px solid #166534;
    border-radius:9px;
    padding:8px 12px;
    font-weight:900;
}
QPushButton:hover {
    background:#064E3B;
    border:1px solid #22C55E;
    color:#FFFFFF;
}
QPushButton:pressed {
    background:#16A34A;
}
QListWidget, QTextEdit, QComboBox {
    background:#000000;
    color:#00FF66;
    border:1px solid #14532D;
    border-radius:10px;
    padding:8px;
    selection-background-color:#166534;
}
QProgressBar {
    background:#031A0A;
    border:1px solid #166534;
    border-radius:8px;
    height:16px;
    text-align:center;
    color:#BBF7D0;
    font-weight:bold;
}
QProgressBar::chunk {
    background:#00FF66;
    border-radius:8px;
}
QFrame#Panel {
    background:#020D05;
    border:1px solid #14532D;
    border-radius:14px;
}
QLabel#AsciiTitle {
    color:#00FF66;
    font-size:10px;
    font-weight:900;
}
QLabel#Subtitle {
    color:#22C55E;
    font-size:12px;
}
QLabel#Metric {
    color:#BBF7D0;
    background:#031A0A;
    border:1px solid #166534;
    border-radius:10px;
    padding:8px;
}
QLabel#Artifact {
    color:#DCFCE7;
    background:#052E16;
    border:1px solid #22C55E;
    border-radius:10px;
    padding:10px;
}
""",
}

PHASE_WEIGHTS = {
    "scan": (0, 10),
    "read": (10, 30),
    "files": (30, 45),
    "container": (45, 50),
    "chunks": (50, 85),
    "audio": (85, 100),
}


def format_size(num: int) -> str:
    value = float(num)

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024:
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{value:.1f} PB"


def matrix_line(seed_text: str) -> str:
    base_len = max(72, min(160, len(seed_text) + 28))
    payload = "".join(random.choice(MATRIX_ALPHABET) for _ in range(base_len))
    return f"{payload}\n"


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
            percent = self.weighted_percent(phase, current, total)
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

            self.progress.emit(
                percent,
                f"chunks {current}/{total}",
                eta,
            )
            return

        tqdm_match = re.search(r"(Packing|Unpacking) samples:\s+(\d+)%", line)

        if tqdm_match:
            current = int(tqdm_match.group(2))
            percent = self.weighted_percent("audio", current, 100)
            eta = self.compute_eta(percent)

            self.progress.emit(
                percent,
                f"audio {current}/100",
                eta,
            )

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


class CypherGui(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("CYPHER // AUDIO PAYLOAD CONTROL")
        self.resize(1180, 860)

        self.selected_paths: list[Path] = []
        self.selected_audio: Path | None = None
        self.worker: CommandWorker | None = None
        self.has_real_progress = False
        self.last_artifact: Path | None = None

        self.sound_process: subprocess.Popen[bytes] | None = None

        self.files_list = QListWidget()
        self.files_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        self.audio_label = QLabel("NO AUDIO SELECTED")
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.status_label = QLabel("SYSTEM: READY")
        self.phase_label = QLabel("PHASE: IDLE")
        self.eta_label = QLabel("ETA: --")

        self.title_label = QLabel(ASCII_CYPHER)
        self.title_label.setObjectName("AsciiTitle")

        self.subtitle_label = QLabel(
            "AUDIO PAYLOAD CONTROL // ENCRYPTED TRANSPORT ENGINE"
        )
        self.subtitle_label.setObjectName("Subtitle")

        self.theme_select = QComboBox()
        self.theme_select.addItems(["Obsidian Purple", "Matrix"])
        self.theme_select.currentTextChanged.connect(self.apply_theme)

        self.metric_items = QLabel("ITEMS: 0")
        self.metric_items.setObjectName("Metric")

        self.metric_size = QLabel("SIZE: 0 B")
        self.metric_size.setObjectName("Metric")

        self.metric_mode = QLabel("MODE: IDLE")
        self.metric_mode.setObjectName("Metric")

        self.metric_crypto = QLabel("CRYPTO: AUTO")
        self.metric_crypto.setObjectName("Metric")

        self.artifact_label = QLabel("ARTIFACT: none")
        self.artifact_label.setObjectName("Artifact")

        self.open_artifact_button = QPushButton("OPEN OUTPUT FOLDER")
        self.open_artifact_button.clicked.connect(self.open_artifact_folder)

        select_files_button = QPushButton("＋ FILES")
        select_files_button.clicked.connect(self.select_files)

        select_folder_button = QPushButton("＋ FOLDER")
        select_folder_button.clicked.connect(self.select_folder)

        remove_button = QPushButton("－ REMOVE")
        remove_button.clicked.connect(self.remove_selected)

        clear_button = QPushButton("⌫ CLEAR")
        clear_button.clicked.connect(self.clear_selection)

        encode_button = QPushButton("⚡ ENCODE / BUNDLE")
        encode_button.clicked.connect(self.encode_or_bundle)

        select_audio_button = QPushButton("◎ SELECT AUDIO")
        select_audio_button.clicked.connect(self.select_audio)

        inspect_button = QPushButton("◉ INSPECT")
        inspect_button.clicked.connect(self.inspect_audio)

        restore_button = QPushButton("⟲ DECODE / RESTORE")
        restore_button.clicked.connect(self.decode_audio)

        cancel_button = QPushButton("✕ ABORT")
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

        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.addWidget(self.title_label)
        header_text.addWidget(self.subtitle_label)
        header_layout.addLayout(header_text)
        header_layout.addWidget(QLabel("THEME"))
        header_layout.addWidget(self.theme_select)

        dashboard = QHBoxLayout()
        dashboard.addWidget(self.metric_items)
        dashboard.addWidget(self.metric_size)
        dashboard.addWidget(self.metric_mode)
        dashboard.addWidget(self.metric_crypto)

        input_panel = QFrame()
        input_panel.setObjectName("Panel")
        input_layout = QVBoxLayout()
        input_layout.addWidget(QLabel("▌ PAYLOAD INPUT // FILES + FOLDERS"))
        input_layout.addLayout(top_buttons)
        input_layout.addWidget(self.files_list)
        input_panel.setLayout(input_layout)

        audio_panel = QFrame()
        audio_panel.setObjectName("Panel")
        audio_layout = QVBoxLayout()
        audio_layout.addWidget(QLabel("▌ AUDIO CONTAINER // FLAC + WAV"))
        audio_layout.addLayout(audio_buttons)
        audio_layout.addWidget(self.audio_label)
        audio_panel.setLayout(audio_layout)

        telemetry_panel = QFrame()
        telemetry_panel.setObjectName("Panel")
        telemetry_layout = QVBoxLayout()
        telemetry_layout.addWidget(QLabel("▌ EXECUTION TELEMETRY"))
        telemetry_layout.addWidget(self.progress_bar)
        telemetry_layout.addLayout(progress_info)
        telemetry_layout.addWidget(self.artifact_label)
        telemetry_layout.addWidget(self.open_artifact_button)
        telemetry_panel.setLayout(telemetry_layout)

        logs_panel = QFrame()
        logs_panel.setObjectName("Panel")
        logs_layout = QVBoxLayout()
        logs_layout.addWidget(QLabel("▌ TERMINAL STREAM"))
        logs_layout.addWidget(self.logs)
        logs_panel.setLayout(logs_layout)

        layout = QVBoxLayout()
        layout.addLayout(header_layout)
        layout.addLayout(dashboard)
        layout.addWidget(input_panel)
        layout.addWidget(audio_panel)
        layout.addWidget(telemetry_panel)
        layout.addWidget(logs_panel)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.apply_theme(self.theme_select.currentText())
        self.boot_sequence()
        self.update_dashboard()

    def current_theme(self) -> str:
        return self.theme_select.currentText()

    def apply_theme(self, name: str) -> None:
        QApplication.instance().setStyleSheet(THEMES[name])

        if name == "Matrix":
            self.subtitle_label.setText("MATRIX STREAM // ENCRYPTED SIGNAL VIEW")
            self.logs.clear()
            self.log("> MATRIX STREAM ONLINE\n")
            self.log("> VISUAL LOG OBFUSCATION ENABLED\n\n")
            return

        self.subtitle_label.setText(
            "AUDIO PAYLOAD CONTROL // ENCRYPTED TRANSPORT ENGINE"
        )
        self.logs.clear()
        self.log("> obsidian console ready\n")
        self.log("> normal log stream enabled\n\n")

    def boot_sequence(self) -> None:
        self.log("> loading cypher gui shell...\n")
        self.log("> initializing payload panels...\n")
        self.log("> binding encrypted audio transport...\n")
        self.log("> telemetry channel online...\n")
        self.log("> SYSTEM READY.\n\n")

    def log(self, text: str) -> None:
        self.capture_artifact_from_log(text)

        if self.current_theme() == "Matrix":
            rendered = matrix_line(text)
        else:
            rendered = text

        self.logs.moveCursor(self.logs.textCursor().MoveOperation.End)
        self.logs.insertPlainText(rendered)
        self.logs.moveCursor(self.logs.textCursor().MoveOperation.End)

    def play_theme_sound(self) -> None:
        if self.current_theme() == "Matrix":
            sound = MATRIX_SOUND
        else:
            sound = OBSIDIAN_SOUND

        if not sound.exists():
            self.log(f"Sound file missing: {sound}\n")
            return

        if self.sound_process is not None and self.sound_process.poll() is None:
            self.sound_process.terminate()

        self.sound_process = subprocess.Popen(
            ["afplay", str(sound.resolve())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def capture_artifact_from_log(self, line: str) -> None:
        match = re.search(r"Audio\s+:\s+(.+)", line)

        if not match:
            return

        candidate = Path(match.group(1).strip())
        self.last_artifact = candidate
        self.artifact_label.setText(f"ARTIFACT: {candidate}")

    def open_artifact_folder(self) -> None:
        if self.last_artifact is None:
            self.log("No artifact folder to open.\n")
            return

        subprocess.run(
            ["open", str(self.last_artifact.parent)],
            check=False,
        )

    def selected_total_size(self) -> int:
        total = 0

        for path in self.selected_paths:
            if path.is_file():
                total += path.stat().st_size
                continue

            if path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file():
                        total += child.stat().st_size

        return total

    def update_dashboard(self) -> None:
        total_size = self.selected_total_size()
        items = len(self.selected_paths)

        if items == 0:
            mode = "IDLE"
        elif items == 1 and self.selected_paths[0].is_file():
            mode = "SINGLE"
        else:
            mode = "BUNDLE"

        self.metric_items.setText(f"ITEMS: {items}")
        self.metric_size.setText(f"SIZE: {format_size(total_size)}")
        self.metric_mode.setText(f"MODE: {mode}")
        self.metric_crypto.setText("CRYPTO: AUTO")

    def update_progress(self, value: int, phase: str, eta: str) -> None:
        if not self.has_real_progress:
            self.has_real_progress = True
            self.progress_bar.setRange(0, 100)

        value = max(0, min(100, value))
        self.progress_bar.setValue(value)
        self.status_label.setText(f"SYSTEM: RUNNING // {value}%")
        self.phase_label.setText(f"PHASE: {phase.upper()}")
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
        self.phase_label.setText("PHASE: IDLE")
        self.eta_label.setText("ETA: --")
        self.update_dashboard()

    def remove_selected(self) -> None:
        selected_items = self.files_list.selectedItems()

        for item in selected_items:
            path = Path(item.text())

            if path in self.selected_paths:
                self.selected_paths.remove(path)

            row = self.files_list.row(item)
            self.files_list.takeItem(row)

        self.status_label.setText(f"{len(self.selected_paths)} item(s) selected")
        self.update_dashboard()

    def clear_selection(self) -> None:
        self.selected_paths.clear()
        self.selected_audio = None
        self.has_real_progress = False
        self.last_artifact = None

        self.files_list.clear()
        self.audio_label.setText("NO AUDIO SELECTED")
        self.logs.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText("SYSTEM: READY")
        self.phase_label.setText("PHASE: IDLE")
        self.eta_label.setText("ETA: --")
        self.artifact_label.setText("ARTIFACT: none")
        self.update_dashboard()

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
        self.status_label.setText("AUDIO SELECTED")
        self.phase_label.setText("PHASE: IDLE")
        self.eta_label.setText("ETA: --")

    def run_command(self, command: list[str]) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.log("\nA command is already running.\n")
            return

        self.has_real_progress = False
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("SYSTEM: INITIALIZING PAYLOAD PIPELINE")
        self.phase_label.setText("PHASE: STARTING")
        self.eta_label.setText("ETA: REFINING")

        self.play_theme_sound()

        self.worker = CommandWorker(command)
        self.worker.output.connect(self.log)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished_ok.connect(self.command_finished)
        self.worker.start()

    def command_finished(self, code: int) -> None:
        self.progress_bar.setRange(0, 100)

        if code == 0:
            self.progress_bar.setValue(100)
            self.status_label.setText("SYSTEM: COMPLETE // 100%")
            self.phase_label.setText("PHASE: COMPLETED")
            self.eta_label.setText("ETA: 0s")
            self.log("\nOperation completed successfully.\n")
            return

        self.status_label.setText(f"SYSTEM: FAILED // EXIT {code}")
        self.phase_label.setText("PHASE: FAILED")
        self.eta_label.setText("ETA: --")
        self.log(f"\nOperation failed with exit code {code}.\n")

    def cancel_command(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            self.log("No command running.\n")
            return

        self.worker.cancel()
        if self.sound_process is not None and self.sound_process.poll() is None:
            self.sound_process.terminate()

        self.status_label.setText("SYSTEM: ABORT REQUESTED")
        self.phase_label.setText("PHASE: CANCELLING")
        self.eta_label.setText("ETA: --")
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
