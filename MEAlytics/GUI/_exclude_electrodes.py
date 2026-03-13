import json
import os
import threading
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from MEAlytics.core._features import recalculate_features
from MEAlytics.GUI._helpers import _adjust_color, _electrode_grid, _well_grid
from MEAlytics.GUI._theme import (
    ACCENT_MUTED,
    BORDER_COLOR,
    STYLESHEET,
    SUCCESS,
    SURFACE_2,
    SURFACE_3,
    TEXT_MUTED,
    TEXT_SECONDARY,
    WARNING,
    make_divider,
    make_label,
)

_COLOR_SELECTED = "#3d8ef0"
_COLOR_UNSELECTED = "#ef4444"
_COLOR_SELECTED_HOVER = "#1e3a6e"
_COLOR_UNSELECTED_HOVER = "#7f1d1d"

_FILE_SELECTED_STYLE = f"""
    QPushButton {{
        background-color: {ACCENT_MUTED};
        color: {_COLOR_SELECTED};
        border: 1px solid {_COLOR_SELECTED};
        border-radius: 7px;
        text-align: left;
        padding: 6px 10px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {_COLOR_SELECTED_HOVER};
    }}
"""

_FILE_DESELECTED_STYLE = f"""
    QPushButton {{
        background-color: {SURFACE_3};
        color: {TEXT_MUTED};
        border: 1px solid {BORDER_COLOR};
        border-radius: 7px;
        text-align: left;
        padding: 6px 10px;
        font-size: 12px;
        text-decoration: line-through;
    }}
    QPushButton:hover {{
        background-color: {SURFACE_2};
        color: {TEXT_SECONDARY};
    }}
"""


class _ConfigThumbnail(QWidget):
    _CELL = 6  # px per electrode square
    _GAP = 3  # px gap between wells
    _MARGIN = 4  # px outer margin

    def __init__(self):
        super().__init__()
        self._config: np.ndarray | None = None
        self._well_amnt: int = 0
        self._electrode_amnt: int = 0
        self.setMinimumSize(60, 40)
        self._recalc_size()

    def set_config(self, config: np.ndarray, well_amnt: int, electrode_amnt: int):
        self._config = config
        self._well_amnt = well_amnt
        self._electrode_amnt = electrode_amnt
        self._recalc_size()
        self.update()

    def _recalc_size(self):
        if self._well_amnt == 0:
            return
        mask = _electrode_grid(self._electrode_amnt)
        e_cols, e_rows = mask.shape[1], mask.shape[0]
        w_cols, w_rows = _well_grid(self._well_amnt)

        cell = self._CELL
        gap = self._GAP
        m = self._MARGIN

        total_w = m * 2 + w_cols * (e_cols * cell + gap) - gap
        total_h = m * 2 + w_rows * (e_rows * cell + gap) - gap
        self.setFixedSize(total_w, total_h)

    def paintEvent(self, event):
        if self._config is None or self._well_amnt == 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        mask = _electrode_grid(self._electrode_amnt)
        e_cols = mask.shape[1]
        e_rows = mask.shape[0]
        w_cols, w_rows = _well_grid(self._well_amnt)

        cell = self._CELL
        gap = self._GAP
        m = self._MARGIN

        config_idx = 0

        for wr in range(w_rows):
            for wc in range(w_cols):
                well_x = m + wc * (e_cols * cell + gap)
                well_y = m + wr * (e_rows * cell + gap)

                for er in range(e_rows):
                    for ec in range(e_cols):
                        if not mask[er, ec]:
                            continue
                        active = (
                            bool(self._config[config_idx])
                            if config_idx < len(self._config)
                            else True
                        )
                        color = QColor(_COLOR_SELECTED if active else _COLOR_UNSELECTED)
                        painter.fillRect(
                            well_x + ec * cell,
                            well_y + er * cell,
                            cell - 1,
                            cell - 1,
                            color,
                        )
                        config_idx += 1

        painter.end()


class EditConfigurationDialog(QDialog):
    def __init__(
        self,
        wells: int,
        electrodes: int,
        existing_config: np.ndarray | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("MEAlytics — Electrode Configuration")
        self.setStyleSheet(STYLESHEET)
        self.setMinimumSize(400, 300)

        self._wells = wells
        self._electrodes = electrodes
        self._electrode_buttons: dict[str, dict] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        ctrl = QWidget()
        ctrl.setFixedWidth(190)
        ctrl_layout = QVBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(12)

        manage_card = QFrame()
        manage_card.setObjectName("Card")
        mc = QVBoxLayout(manage_card)
        mc.setContentsMargins(16, 14, 16, 14)
        mc.setSpacing(8)
        mc.addWidget(make_label("Configuration", "SectionLabel"))
        mc.addWidget(make_divider())

        for text, slot in [
            ("Load configuration", self._load_config),
            ("Save configuration", self._save_config),
            ("Apply configuration", self._apply_config),
        ]:
            btn = QPushButton(text)
            btn.setObjectName(
                "SecondaryBtn" if text != "Apply configuration" else "PrimaryBtn"
            )
            btn.setMinimumHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            mc.addWidget(btn)

        ctrl_layout.addWidget(manage_card)

        sel_card = QFrame()
        sel_card.setObjectName("Card")
        sc = QVBoxLayout(sel_card)
        sc.setContentsMargins(16, 14, 16, 14)
        sc.setSpacing(8)
        sc.addWidget(make_label("Selection", "SectionLabel"))
        sc.addWidget(make_divider())

        for text, slot in [
            ("Select all", self._select_all),
            ("Deselect all", self._deselect_all),
        ]:
            btn = QPushButton(text)
            btn.setObjectName("SecondaryBtn")
            btn.setMinimumHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            sc.addWidget(btn)

        ctrl_layout.addWidget(sel_card)
        ctrl_layout.addStretch()
        root.addWidget(ctrl)

        grid_card = QFrame()
        grid_card.setObjectName("Card")
        gc = QVBoxLayout(grid_card)
        gc.setContentsMargins(16, 14, 16, 14)
        gc.setSpacing(10)
        gc.addWidget(make_label("Electrode Layout", "SectionLabel"))
        gc.addWidget(make_divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(self._grid_container)
        gc.addWidget(scroll, 1)
        root.addWidget(grid_card, 1)

        self._create_buttons(wells, electrodes)
        if existing_config is not None:
            for i, value in enumerate(existing_config):
                if not value:
                    self._toggle(str(i + 1))

        self._applied_config: np.ndarray | None = None
        self._resize_to_content()

    def _create_buttons(self, wells: int, electrodes: int):
        self._electrode_buttons.clear()
        mask = _electrode_grid(electrodes)
        w_cols, w_rows = _well_grid(wells)
        btn_size = 28
        counter = 1

        for wr in range(w_rows):
            for wc in range(w_cols):
                well_frame = QFrame()
                well_frame.setObjectName("Card")
                well_frame.setStyleSheet(
                    f"QFrame#Card {{ background-color: {SURFACE_2}; border: 1px solid {BORDER_COLOR}; border-radius: 6px; }}"
                )
                wf_layout = QGridLayout(well_frame)
                wf_layout.setSpacing(0)
                wf_layout.setContentsMargins(4, 4, 4, 4)

                for er in range(mask.shape[0]):
                    for ec in range(mask.shape[1]):
                        if mask[er, ec]:
                            btn = QPushButton()
                            btn.setFixedSize(btn_size, btn_size)
                            btn.setCursor(Qt.CursorShape.PointingHandCursor)
                            btn.setToolTip(f"Electrode {counter}")
                            self._apply_btn_style(btn, active=True)
                            btn.clicked.connect(partial(self._toggle, str(counter)))
                            wf_layout.addWidget(btn, er, ec)
                            self._electrode_buttons[str(counter)] = {
                                "button": btn,
                                "state": True,
                            }
                            counter += 1

                self._grid_layout.addWidget(well_frame, wr, wc)

    def _apply_btn_style(self, btn: QPushButton, active: bool):
        color = _COLOR_SELECTED if active else _COLOR_UNSELECTED
        hover = _adjust_color(color, 0.7)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: none;
                border-radius: 0px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """)

    def _resize_to_content(self):
        self._grid_container.adjustSize()
        self.adjustSize()

    def _toggle(self, electrode: str):
        entry = self._electrode_buttons[electrode]
        entry["state"] = not entry["state"]
        self._apply_btn_style(entry["button"], active=entry["state"])

    def _select_all(self):
        for key, entry in self._electrode_buttons.items():
            entry["state"] = True
            self._apply_btn_style(entry["button"], active=True)

    def _deselect_all(self):
        for key, entry in self._electrode_buttons.items():
            entry["state"] = False
            self._apply_btn_style(entry["button"], active=False)

    def _save_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", "", "NumPy files (*.npy);;All Files (*)"
        )
        if not path:
            return
        config = np.array([e["state"] for e in self._electrode_buttons.values()])
        np.save(path, config)
        QMessageBox.information(self, "Saved", f"Configuration saved to:\n{path}")

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "", "NumPy files (*.npy);;All Files (*)"
        )
        if not path:
            return
        try:
            config = np.load(path)
        except Exception:
            QMessageBox.critical(
                self, "Error", "Could not load the configuration file."
            )
            return

        if len(config) != len(self._electrode_buttons):
            QMessageBox.critical(
                self,
                "Error",
                f"The configuration has {len(config)} electrodes, but the current "
                f"experiments have {len(self._electrode_buttons)}.",
            )
            return

        for i, value in enumerate(config):
            entry = self._electrode_buttons[str(i + 1)]
            entry["state"] = bool(value)
            self._apply_btn_style(entry["button"], active=bool(value))

    def _apply_config(self):
        self._applied_config = np.array(
            [e["state"] for e in self._electrode_buttons.values()]
        )
        self.accept()

    def get_config(self) -> np.ndarray | None:
        return self._applied_config


class ExcludeElectrodesWindow(QMainWindow):
    _recalc_done = pyqtSignal(list, list, list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MEAlytics - Exclude Electrodes")
        self.resize(1000, 640)
        self.setMinimumSize(720, 480)
        self.setStyleSheet(STYLESHEET)

        self._file_buttons: dict[str, dict] = {}
        self._well_amnt: int = 0
        self._electrode_amnt: int = 0
        self._configuration: np.ndarray | None = None
        self._config_selected: bool = False

        self._recalc_done.connect(self._on_recalculation_done)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        root.addWidget(self._build_control_panel(), 0)
        root.addWidget(self._build_file_panel(), 1)

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        actions_card = QFrame()
        actions_card.setObjectName("Card")
        ac = QVBoxLayout(actions_card)
        ac.setContentsMargins(16, 14, 16, 14)
        ac.setSpacing(8)
        ac.addWidget(make_label("Actions", "SectionLabel"))
        ac.addWidget(make_divider())

        load_btn = QPushButton("Load Folder")
        load_btn.setObjectName("PrimaryBtn")
        load_btn.setMinimumHeight(38)
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.clicked.connect(self._load_folder)
        ac.addWidget(load_btn)

        edit_btn = QPushButton("Edit / New Configuration")
        edit_btn.setObjectName("SecondaryBtn")
        edit_btn.setMinimumHeight(38)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(self._edit_configuration)
        ac.addWidget(edit_btn)

        recalc_btn = QPushButton("Recalculate Features")
        recalc_btn.setObjectName("PrimaryBtn")
        recalc_btn.setMinimumHeight(38)
        recalc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        recalc_btn.clicked.connect(self._recalculate_features_btn)
        ac.addWidget(recalc_btn)

        layout.addWidget(actions_card)

        # Config preview card
        preview_card = QFrame()
        preview_card.setObjectName("Card")
        pc = QVBoxLayout(preview_card)
        pc.setContentsMargins(16, 14, 16, 14)
        pc.setSpacing(8)
        pc.addWidget(make_label("Current Configuration", "SectionLabel"))
        pc.addWidget(make_divider())

        self._config_status = QLabel("No configuration loaded")
        self._config_status.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent"
        )
        pc.addWidget(self._config_status)

        self._thumbnail = _ConfigThumbnail()
        self._thumbnail.setVisible(False)
        pc.addWidget(self._thumbnail, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(preview_card)
        layout.addStretch()

        return panel

    def _build_file_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(make_label("Loaded Feature Files", "SectionLabel"))
        header.addStretch()

        self._file_count_lbl = QLabel("")
        self._file_count_lbl.setObjectName("StatusBadge")
        self._file_count_lbl.setVisible(False)
        header.addWidget(self._file_count_lbl)
        layout.addLayout(header)

        hint = QLabel(
            "Click a file to toggle whether it is included in the recalculation."
        )
        hint.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent"
        )
        layout.addWidget(hint)
        layout.addWidget(make_divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._files_container = QWidget()
        self._files_layout = QVBoxLayout(self._files_container)
        self._files_layout.setContentsMargins(0, 0, 0, 0)
        self._files_layout.setSpacing(6)
        self._files_layout.addStretch()

        scroll.setWidget(self._files_container)
        layout.addWidget(scroll, 1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        self._progress_label.setVisible(False)
        layout.addWidget(self._progress_label)

        return panel

    def _load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Experiments Folder")
        if not folder:
            return

        well_amnts: list[int] = []
        electrode_amnts: list[int] = []
        file_paths: list[str] = []

        for root, _, files in os.walk(folder):
            for file in files:
                if file.endswith("Features.csv") and "Electrode" not in file:
                    full_path = os.path.join(root, file)
                    data = pd.read_csv(full_path)
                    well_amnts.append(len(data))
                    file_paths.append(full_path)

                    try:
                        with open(os.path.join(root, "parameters.json")) as jf:
                            params = json.load(jf)
                        electrode_amnts.append(params["electrode amount"])
                    except Exception:
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"Could not find a complementary 'parameters.json' for '{file}'.\n"
                            "Please make sure every feature file is accompanied by its original parameters.json.",
                        )
                        return

        if not well_amnts:
            QMessageBox.critical(
                self, "Error", "No feature files found in the selected folder."
            )
            return

        if np.min(well_amnts) != np.max(well_amnts):
            QMessageBox.critical(
                self,
                "Error",
                "Not all experiments have the same number of wells.\n"
                "Please remove the exceptions from the folder.",
            )
            return

        if np.min(electrode_amnts) != np.max(electrode_amnts):
            QMessageBox.critical(
                self,
                "Error",
                "Not all experiments have the same number of electrodes per well.\n"
                "Please remove the exceptions from the folder.",
            )
            return

        new_well_amnt = int(np.min(well_amnts))
        new_electrode_amnt = int(np.min(electrode_amnts))

        if self._config_selected:
            layout_unchanged = (
                new_well_amnt == self._well_amnt
                and new_electrode_amnt == self._electrode_amnt
            )
            if layout_unchanged:
                pass
            else:
                reply = QMessageBox.warning(
                    self,
                    "Configuration Incompatible",
                    f"The new folder has {new_well_amnt} wells *"
                    f"{new_electrode_amnt} electrodes, but the current "
                    f"configuration was made for {self._well_amnt} wells *"
                    f"{self._electrode_amnt} electrodes.\n\n"
                    "The configuration will be cleared.\n"
                    "Do you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

                self._configuration = None
                self._config_selected = False
                self._config_status.setText("No configuration loaded")
                self._config_status.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px;"
                )
                self._thumbnail.setVisible(False)

        self._well_amnt = new_well_amnt
        self._electrode_amnt = new_electrode_amnt
        self._display_files(file_paths)

    def _display_files(self, file_paths: list[str]):
        for entry in self._file_buttons.values():
            entry["button"].deleteLater()
        self._file_buttons.clear()

        for path in file_paths:
            btn = QPushButton(path)
            btn.setStyleSheet(_FILE_SELECTED_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setMinimumHeight(34)
            btn.clicked.connect(partial(self._toggle_file, path))
            self._files_layout.insertWidget(self._files_layout.count() - 1, btn)
            self._file_buttons[path] = {"button": btn, "state": True}

        n = len(file_paths)
        self._file_count_lbl.setText(f"{n} file{'s' if n != 1 else ''}")
        self._file_count_lbl.setVisible(True)

    def _toggle_file(self, path: str):
        entry = self._file_buttons[path]
        entry["state"] = not entry["state"]
        entry["button"].setStyleSheet(
            _FILE_SELECTED_STYLE if entry["state"] else _FILE_DESELECTED_STYLE
        )

    def _edit_configuration(self):
        if not self._file_buttons:
            QMessageBox.warning(
                self,
                "No Folder Loaded",
                "Please load a folder first. The electrode layout is determined by the selected files.",
            )
            return

        dlg = EditConfigurationDialog(
            wells=self._well_amnt,
            electrodes=self._electrode_amnt,
            existing_config=self._configuration,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            config = dlg.get_config()
            if config is not None:
                self._configuration = config
                self._config_selected = True
                n_excluded = int(np.sum(~config))
                self._config_status.setText(
                    f"{n_excluded} electrode{'s' if n_excluded != 1 else ''} excluded"
                )
                self._config_status.setStyleSheet(
                    f"color: {WARNING if n_excluded > 0 else SUCCESS}; font-size: 11px;"
                )
                self._thumbnail.set_config(
                    config, self._well_amnt, self._electrode_amnt
                )
                self._thumbnail.setVisible(True)

    def _recalculate_features_btn(self):
        if not self._config_selected:
            QMessageBox.warning(
                self,
                "No Configuration",
                "No configuration selected. Please create one using 'Edit / New Configuration'.",
            )
            return

        selected_files = [p for p, e in self._file_buttons.items() if e["state"]]
        if not selected_files:
            QMessageBox.warning(
                self, "No Files Selected", "No files are selected for recalculation."
            )
            return

        self._progress_bar.setMaximum(len(selected_files))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._progress_label.setText("Recalculating features…")
        self._progress_label.setVisible(True)

        thread = threading.Thread(
            target=self._recalculate_features_thread,
            args=(selected_files,),
            daemon=True,
        )
        thread.start()

    def _recalculate_features_thread(self, selected_files: list[str]):
        finished: list[str] = []
        failed: list[str] = []
        errors: list[Exception] = []

        for i, file in enumerate(selected_files):
            filepath = Path(file)
            try:
                with open(filepath.parent / "parameters.json") as jf:
                    params = json.load(jf)

                recalculate_features(
                    outputfolder=filepath.parent,
                    well_amnt=self._well_amnt,
                    electrode_amnt=self._electrode_amnt,
                    electrodes=self._configuration,
                    sampling_rate=params["sampling rate"],
                    measurements=params["measurements"],
                )
                finished.append(filepath.stem)
            except Exception as e:
                failed.append(filepath.stem)
                errors.append(e)

            self._progress_bar.setValue(i + 1)
            self._progress_label.setText(f"Processing {i + 1} / {len(selected_files)}…")

        self._recalc_done.emit(finished, failed, errors)

    def _on_recalculation_done(
        self,
        finished: list[str],
        failed: list[str],
        errors: list[Exception],
    ):
        self._progress_bar.setVisible(False)
        self._progress_label.setVisible(False)

        lines: list[str] = []
        if finished:
            lines.append(f"Finished ({len(finished)}):")
            lines.extend(f"   {f}" for f in finished)
        else:
            lines.append("Did not finish any files.")

        if failed:
            lines.append(f"\nFailed ({len(failed)}):")
            for f, e in zip(failed, errors):
                lines.append(f"   {f}: {e}")

        QMessageBox.information(self, "Recalculation Complete", "\n".join(lines))
