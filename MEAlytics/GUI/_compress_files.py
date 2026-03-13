import os
import threading
import traceback
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from MEAlytics.core._utilities import rechunk_dataset
from MEAlytics.GUI._theme import (
    ACCENT,
    BORDER_COLOR,
    DANGER,
    STYLESHEET,
    SUCCESS,
    SURFACE_3,
    TEXT_MUTED,
    TEXT_SECONDARY,
    WARNING,
    make_divider,
    make_label,
)


class CompressWindow(QMainWindow):
    _progress_updated = pyqtSignal(int, int, str)
    _file_finished = pyqtSignal(str, bool)
    _compression_done = pyqtSignal(list, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MEAlytics — Rechunk / Compress")
        self.resize(680, 520)
        self.setMinimumSize(520, 420)
        self.setStyleSheet(STYLESHEET)

        self._selected_file: str = ""
        self._compression_method: str = "lzf"
        self._abort_flag: bool = False

        self._progress_updated.connect(self._on_progress_updated)
        self._file_finished.connect(self._on_file_finished)
        self._compression_done.connect(self._on_compression_done)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        root.addWidget(self._build_settings_panel(), 0)
        root.addWidget(self._build_progress_panel(), 1)

    def _build_settings_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(260)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # File selection
        file_card = QFrame()
        file_card.setObjectName("Card")
        fc = QVBoxLayout(file_card)
        fc.setContentsMargins(16, 14, 16, 14)
        fc.setSpacing(8)
        fc.addWidget(make_label("Input File", "SectionLabel"))
        fc.addWidget(make_divider())

        self._file_btn = QPushButton("Select a file")
        self._file_btn.setObjectName("PrimaryBtn")
        self._file_btn.setMinimumHeight(38)
        self._file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._file_btn.clicked.connect(self._open_file)
        fc.addWidget(self._file_btn)

        self._compress_all_cb = QCheckBox("Compress all .h5 files in same folder")
        self._compress_all_cb.setStyleSheet("background: transparent")
        self._compress_all_cb.setChecked(False)
        fc.addWidget(self._compress_all_cb)

        layout.addWidget(file_card)

        # Compression method
        method_card = QFrame()
        method_card.setObjectName("Card")
        mc = QVBoxLayout(method_card)
        mc.setContentsMargins(16, 14, 16, 14)
        mc.setSpacing(10)
        mc.addWidget(make_label("Compression Method", "SectionLabel"))
        mc.addWidget(make_divider())

        self._btn_group = QButtonGroup(self)

        self._lzf_radio = QRadioButton("LZF  (fast, moderate ratio)")
        self._lzf_radio.setStyleSheet("background: transparent")
        self._lzf_radio.setChecked(True)
        self._btn_group.addButton(self._lzf_radio)
        mc.addWidget(self._lzf_radio)

        self._gzip_radio = QRadioButton("GZIP  (slower, better ratio)")
        self._gzip_radio.setStyleSheet("background: transparent")
        self._btn_group.addButton(self._gzip_radio)
        mc.addWidget(self._gzip_radio)

        self._btn_group.buttonClicked.connect(self._on_method_changed)

        mc.addWidget(make_divider())

        gzip_row = QHBoxLayout()
        gzip_level_lbl = QLabel("GZIP level:")
        gzip_level_lbl.setStyleSheet("background: transparent")
        gzip_row.addWidget(gzip_level_lbl)
        self._gzip_level_lbl = QLabel("1")
        self._gzip_level_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent"
        )
        gzip_row.addWidget(self._gzip_level_lbl)
        gzip_row.addStretch()
        mc.addLayout(gzip_row)

        self._gzip_slider = QSlider(Qt.Orientation.Horizontal)
        self._gzip_slider.setMinimum(1)
        self._gzip_slider.setMaximum(9)
        self._gzip_slider.setValue(1)
        self._gzip_slider.setTickInterval(1)
        self._gzip_slider.setEnabled(False)
        self._gzip_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {SURFACE_3};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:disabled {{
                background: {BORDER_COLOR};
            }}d
            QSlider::sub-page:horizontal {{
                background: {ACCENT};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal:disabled {{
                background: {BORDER_COLOR};
            }}
        """)
        self._gzip_slider.valueChanged.connect(
            lambda v: self._gzip_level_lbl.setText(str(v))
        )
        mc.addWidget(self._gzip_slider)

        layout.addWidget(method_card)

        # Start / abort buttons
        self._start_btn = QPushButton("▶  Start Compression")
        self._start_btn.setObjectName("PrimaryBtn")
        self._start_btn.setMinimumHeight(42)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._start_compression)
        layout.addWidget(self._start_btn)

        self._abort_btn = QPushButton("Cancel")
        self._abort_btn.setObjectName("DangerBtn")
        self._abort_btn.setMinimumHeight(38)
        self._abort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._abort_btn.setVisible(False)
        self._abort_btn.clicked.connect(self._abort_compression)
        layout.addWidget(self._abort_btn)

        layout.addStretch()
        return panel

    def _build_progress_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        layout.addWidget(make_label("Progress", "SectionLabel"))
        layout.addWidget(make_divider())

        self._status_lbl = QLabel("No compression running.")
        self._status_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; background: transparent"
        )
        layout.addWidget(self._status_lbl)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        layout.addWidget(make_divider())
        layout.addWidget(make_label("Results", "SectionLabel"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._log_container = QWidget()
        self._log_layout = QVBoxLayout(self._log_container)
        self._log_layout.setContentsMargins(0, 0, 0, 0)
        self._log_layout.setSpacing(4)
        self._log_layout.addStretch()

        scroll.setWidget(self._log_container)
        layout.addWidget(scroll, 1)

        return panel

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select HDF5 File", "", "MEA data (*.h5);;All Files (*)"
        )
        if path:
            self._selected_file = path
            self._file_btn.setText(Path(path).name)
            self._file_btn.setToolTip(path)

    def _on_method_changed(self):
        gzip = self._gzip_radio.isChecked()
        self._gzip_slider.setEnabled(gzip)
        self._compression_method = "gzip" if gzip else "lzf"

    def _abort_compression(self):
        self._abort_flag = True
        self._abort_btn.setText("Aborting…")
        self._abort_btn.setEnabled(False)
        self._status_lbl.setText("Aborting after current file…")
        self._status_lbl.setStyleSheet(f"color: {WARNING}; font-size: 12px;")

    def _start_compression(self):
        if not self._selected_file:
            self._status_lbl.setText("Please select a file first.")
            self._status_lbl.setStyleSheet(f"color: {WARNING}; font-size: 12px;")
            return

        if self._compress_all_cb.isChecked():
            folder = os.path.dirname(self._selected_file)
            files = [
                os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".h5")
            ]
        else:
            files = [self._selected_file]

        self._abort_flag = False
        self._progress_bar.setMaximum(len(files))
        self._progress_bar.setValue(0)
        self._status_lbl.setText(
            f"Compressing {len(files)} file{'s' if len(files) != 1 else ''}…"
        )
        self._status_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._clear_log()
        self._start_btn.setEnabled(False)
        self._abort_btn.setVisible(True)
        self._abort_btn.setEnabled(True)
        self._abort_btn.setText("Cancel")

        threading.Thread(
            target=self._compress_thread,
            args=(files, self._compression_method, self._gzip_slider.value()),
            daemon=True,
        ).start()

    def _compress_thread(self, files: list[str], method: str, level: int):
        success_files: list[str] = []
        failed_files: list[str] = []

        for i, file in enumerate(files):
            if self._abort_flag:
                self._abort_flag = False
                break

            self._progress_updated.emit(i, len(files), Path(file).name)

            try:
                rechunk_dataset(
                    fileadress=file,
                    compression_method=method,
                    compression_level=level,
                    always_compress_files=True,
                )
                success_files.append(file)
                self._file_finished.emit(file, True)
            except Exception:
                traceback.print_exc()
                failed_files.append(file)
                self._file_finished.emit(file, False)

        self._compression_done.emit(success_files, failed_files)

    def _on_progress_updated(self, current: int, total: int, filename: str):
        self._progress_bar.setValue(current)
        self._status_lbl.setText(f"[{current + 1}/{total}]  {filename}")

    def _on_file_finished(self, filepath: str, success: bool):
        name = Path(filepath).name
        lbl = QLabel(f"{'✔' if success else '✘'}  {name}")
        lbl.setStyleSheet(f"color: {SUCCESS if success else DANGER}; font-size: 12px;")
        lbl.setToolTip(filepath)
        lbl.setWordWrap(True)
        self._log_layout.insertWidget(self._log_layout.count() - 1, lbl)

    def _on_compression_done(self, success_files: list[str], failed_files: list[str]):
        self._progress_bar.setValue(self._progress_bar.maximum())
        n_ok = len(success_files)
        n_fail = len(failed_files)

        if n_fail == 0:
            msg = (
                f"Done - {n_ok} file{'s' if n_ok != 1 else ''} compressed successfully."
            )
            color = SUCCESS
        else:
            msg = f"Done - {n_ok} succeeded, {n_fail} failed."
            color = WARNING

        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")

        self._start_btn.setEnabled(True)
        self._abort_btn.setVisible(False)

    def _clear_log(self):
        while self._log_layout.count() > 1:
            item = self._log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
