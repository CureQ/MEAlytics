import copy
import json
import os
import traceback
import webbrowser
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from MEAlytics.core._plotting import (
    combined_feature_boxplots,
    features_over_time,
    get_defaultcolors,
)
from MEAlytics.GUI._helpers import _adjust_color, _well_grid
from MEAlytics.GUI._theme import (
    _BTN_STYLE_DEFAULT,
    BORDER_COLOR,
    STYLESHEET,
    SURFACE_2,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARN_LAYOUT_BUTTON_STYLESHEET,
    make_divider,
    make_label,
)

_BTN_SIZE = 56


def _colored_btn_style(fg: str) -> str:
    hover = _adjust_color(fg, 0.7)
    return f"""
        QPushButton {{
            background-color: {fg};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_COLOR};
            border-radius: 0px;
            font-size: 14px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {hover};
        }}
    """


class PlottingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MEAlytics — Plotting")
        self.resize(1100, 720)
        self.setMinimumSize(860, 560)
        self.setStyleSheet(STYLESHEET)

        self._selected_folder: str = ""
        self._well_buttons: list[QPushButton] = []
        self._label_buttons: list[QPushButton] = []
        self._assigned_labels: dict[str, list[int]] = {}
        self._selected_label: str = ""
        self._default_colors: list[str] = get_defaultcolors()
        self._well_amnt: int | None = None
        self._well_placeholder: QLabel | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(self._build_top_bar())

        main_area = QHBoxLayout()
        main_area.setSpacing(12)
        main_area.addWidget(self._build_left_sidebar(), 0)
        main_area.addWidget(self._build_well_panel(), 1)
        main_area.addWidget(self._build_right_sidebar(), 0)
        root.addLayout(main_area, 1)

        root.addWidget(self._build_bottom_bar())

    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("Card")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        self._folder_btn = QPushButton("Select Folder")
        self._folder_btn.setObjectName("PrimaryBtn")
        self._folder_btn.setMinimumHeight(36)
        self._folder_btn.setFixedWidth(160)
        self._folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folder_btn.clicked.connect(self._load_folder)
        layout.addWidget(self._folder_btn)

        self._folder_path_lbl = QLabel("No folder selected")
        self._folder_path_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; background: transparent"
        )
        self._folder_path_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self._folder_path_lbl, 1)

        self._file_count_lbl = QLabel("")
        self._file_count_lbl.setObjectName("StatusBadge")
        self._file_count_lbl.setVisible(False)
        layout.addWidget(self._file_count_lbl)

        return bar

    def _build_left_sidebar(self) -> QWidget:
        col = QWidget()
        col.setFixedWidth(220)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        fot_card = QFrame()
        fot_card.setObjectName("Card")
        fot = QVBoxLayout(fot_card)
        fot.setContentsMargins(16, 14, 16, 14)
        fot.setSpacing(8)

        fot.addWidget(make_label("Features Over Time", "SectionLabel"))
        fot.addWidget(make_divider())

        prefix_label = QLabel("DIV Prefix:")
        prefix_label.setStyleSheet("background: transparent")
        fot.addWidget(prefix_label)
        self._prefix_entry = QLineEdit()
        self._prefix_entry.setPlaceholderText("e.g.  DIV")
        fot.addWidget(self._prefix_entry)

        self._fot_datapoints_cb = QCheckBox("Show datapoints")
        self._fot_datapoints_cb.setStyleSheet("background: transparent")
        fot.addWidget(self._fot_datapoints_cb)

        fot_btn = QPushButton("Plot Features over Time")
        fot_btn.setObjectName("PrimaryBtn")
        fot_btn.setMinimumHeight(36)
        fot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fot_btn.clicked.connect(self._create_plots)
        fot.addWidget(fot_btn)

        layout.addWidget(fot_card)

        bp_card = QFrame()
        bp_card.setObjectName("Card")
        bp = QVBoxLayout(bp_card)
        bp.setContentsMargins(16, 14, 16, 14)
        bp.setSpacing(8)

        bp.addWidget(make_label("Boxplots", "SectionLabel"))
        bp.addWidget(make_divider())

        self._bp_datapoints_cb = QCheckBox("Show datapoints")
        self._bp_datapoints_cb.setStyleSheet("background: transparent")
        bp.addWidget(self._bp_datapoints_cb)

        self._discern_wells_cb = QCheckBox("Color wells")
        self._discern_wells_cb.setStyleSheet("background: transparent")
        bp.addWidget(self._discern_wells_cb)

        bp_btn = QPushButton("Create Boxplots")
        bp_btn.setObjectName("PrimaryBtn")
        bp_btn.setMinimumHeight(36)
        bp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bp_btn.clicked.connect(self._create_boxplots)
        bp.addWidget(bp_btn)

        layout.addWidget(bp_card)
        layout.addStretch()

        return col

    def _build_well_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Card")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(make_label("Assign Wells", "SectionLabel"))
        header.addStretch()
        warn_btn = QPushButton(
            "The well/electrode layout is auto-generated and may not match the physical plate exactly. Click here for details."
        )
        warn_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        warn_btn.setStyleSheet(WARN_LAYOUT_BUTTON_STYLESHEET)
        warn_btn.clicked.connect(
            lambda: webbrowser.open(
                "https://cureq.github.io/MEAlytics/supported_plates"
            )
        )
        header.addWidget(warn_btn)
        outer.addLayout(header)
        outer.addWidget(make_divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._well_grid_widget = QWidget()
        self._well_grid_layout = QGridLayout(self._well_grid_widget)
        self._well_grid_layout.setSpacing(0)
        self._well_grid_layout.setContentsMargins(0, 0, 0, 0)

        self._well_placeholder = QLabel("Load a folder to assign wells to labels.")
        self._well_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._well_placeholder.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; background: transparent"
        )
        self._well_grid_layout.addWidget(self._well_placeholder, 0, 0)
        self._well_grid_widget.setFixedSize(300, 60)

        scroll.setWidget(self._well_grid_widget)
        outer.addWidget(scroll, 1)

        return panel

    def _build_right_sidebar(self) -> QWidget:
        col = QWidget()
        col.setFixedWidth(200)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        create_card = QFrame()
        create_card.setObjectName("Card")
        cc = QVBoxLayout(create_card)
        cc.setContentsMargins(16, 14, 16, 14)
        cc.setSpacing(8)

        cc.addWidget(make_label("Create Label", "SectionLabel"))

        self._new_label_entry = QLineEdit()
        self._new_label_entry.setPlaceholderText("e.g. control")
        self._new_label_entry.returnPressed.connect(self._new_label)
        cc.addWidget(self._new_label_entry)

        add_btn = QPushButton("Add Label")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.setMinimumHeight(34)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._new_label)
        cc.addWidget(add_btn)

        layout.addWidget(create_card)

        actions_card = QFrame()
        actions_card.setObjectName("Card")
        ac = QVBoxLayout(actions_card)
        ac.setContentsMargins(16, 14, 16, 14)
        ac.setSpacing(6)

        ac.addWidget(make_label("Actions", "SectionLabel"))

        for text, slot in [
            ("Save Labels", self._save_labels),
            ("Import Labels", self._import_labels),
            ("Reset Labels", self._reset_labels),
        ]:
            btn = QPushButton(text)
            btn.setObjectName("SecondaryBtn")
            btn.setMinimumHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            ac.addWidget(btn)

        layout.addWidget(actions_card)

        labels_card = QFrame()
        labels_card.setObjectName("Card")
        lc = QVBoxLayout(labels_card)
        lc.setContentsMargins(16, 14, 16, 14)
        lc.setSpacing(8)

        lc.addWidget(make_label("Labels", "SectionLabel"))
        lc.addWidget(make_divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._labels_container = QWidget()
        self._labels_layout = QVBoxLayout(self._labels_container)
        self._labels_layout.setContentsMargins(0, 0, 0, 0)
        self._labels_layout.setSpacing(6)
        self._labels_layout.addStretch()

        scroll.setWidget(self._labels_container)
        lc.addWidget(scroll, 1)

        layout.addWidget(labels_card, 1)

        return col

    def _build_bottom_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("Card")
        bar.setFixedHeight(90)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(6)

        layout.addWidget(make_label("Loaded Experiments", "SectionLabel"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._file_list_container = QWidget()
        self._file_list_layout = QHBoxLayout(self._file_list_container)
        self._file_list_layout.setContentsMargins(0, 0, 0, 0)
        self._file_list_layout.setSpacing(8)
        self._file_list_layout.addStretch()

        scroll.setWidget(self._file_list_container)
        layout.addWidget(scroll, 1)

        return bar

    def _load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Experiments Folder")
        if not folder:
            return

        well_amnts: list[int] = []
        file_names: list[str] = []
        for root, _, files in os.walk(folder):
            for file in files:
                if file.endswith("Features.csv") and "Electrode" not in file:
                    data = pd.read_csv(os.path.join(root, file))
                    well_amnts.append(len(data))
                    file_names.append(Path(os.path.join(root, file)).stem)

        if len(well_amnts) < 1:
            QMessageBox.critical(
                self,
                "Error",
                "No features files found in this folder. Minimum required: 1.",
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

        new_well_amnt = int(np.mean(well_amnts))

        # If a folder was already loaded, warn when well count changes
        if self._well_amnt is not None and new_well_amnt != self._well_amnt:
            reply = QMessageBox.warning(
                self,
                "Well Count Mismatch",
                f"The new folder has {new_well_amnt} wells, but the current "
                f"session has {self._well_amnt}.\n\n"
                "Loading this folder will clear all current label assignments.\n"
                "Do you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._reset_labels()

        self._well_amnt = new_well_amnt
        self._selected_folder = folder

        self._folder_path_lbl.setText(Path(folder).name)
        self._folder_path_lbl.setToolTip(folder)
        self._folder_path_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 12px; background: transparent"
        )
        n = len(file_names)
        self._file_count_lbl.setText(f"{n} experiment{'s' if n != 1 else ''}")
        self._file_count_lbl.setVisible(True)

        self._build_well_buttons(new_well_amnt)
        self._populate_file_list(file_names)

    def _build_well_buttons(self, n_wells: int):
        if self._well_placeholder is not None:
            self._well_placeholder.deleteLater()
            self._well_placeholder = None

        for btn in self._well_buttons:
            btn.deleteLater()
        self._well_buttons.clear()

        cols, rows = _well_grid(n_wells)
        i = 1
        for r in range(rows):
            for c in range(cols):
                btn = QPushButton(str(i))
                btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(_BTN_STYLE_DEFAULT)
                btn.clicked.connect(partial(self._well_button_func, i))
                self._well_grid_layout.addWidget(btn, r, c)
                self._well_buttons.append(btn)
                i += 1

        self._well_grid_widget.setFixedSize(cols * _BTN_SIZE, rows * _BTN_SIZE)

    def _populate_file_list(self, file_names: list[str]):
        while self._file_list_layout.count() > 1:
            item = self._file_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for name in file_names:
            pill = QLabel(name)
            pill.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 11px; "
                f"background: {SURFACE_2}; border: 1px solid {BORDER_COLOR}; "
                f"border-radius: 6px; padding: 2px 8px;"
            )
            self._file_list_layout.insertWidget(
                self._file_list_layout.count() - 1, pill
            )

    def _well_button_func(self, well: int):
        if not self._selected_label:
            QMessageBox.warning(
                self,
                "No Label Selected",
                "Please select a label before assigning wells.",
            )
            return

        if well in self._assigned_labels.get(self._selected_label, []):
            self._assigned_labels[self._selected_label].remove(well)
        else:
            for key in self._assigned_labels:
                if well in self._assigned_labels[key]:
                    self._assigned_labels[key].remove(well)
            self._assigned_labels[self._selected_label].append(well)

        self._update_well_colors()

    def _update_well_colors(self):
        for btn in self._well_buttons:
            btn.setStyleSheet(_BTN_STYLE_DEFAULT)
        for idx, (label, wells) in enumerate(self._assigned_labels.items()):
            color = self._default_colors[idx % len(self._default_colors)]
            for well in wells:
                self._well_buttons[well - 1].setStyleSheet(_colored_btn_style(color))

    def _new_label(self):
        label = self._new_label_entry.text().strip()
        if not label or label in self._assigned_labels:
            return
        self._create_label_button(label)
        self._new_label_entry.clear()

    def _create_label_button(self, label: str):
        idx = len(self._label_buttons)
        color = self._default_colors[idx % len(self._default_colors)]
        hover = _adjust_color(color, 0.7)

        btn = QPushButton(label)
        btn.setMinimumHeight(34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """)
        btn.clicked.connect(partial(self._set_selected_label, label))
        self._labels_layout.insertWidget(self._labels_layout.count() - 1, btn)
        self._label_buttons.append(btn)
        self._assigned_labels[label] = []

    def _set_selected_label(self, label: str):
        self._selected_label = label
        for idx, btn in enumerate(self._label_buttons):
            lbl_name = list(self._assigned_labels.keys())[idx]
            color = self._default_colors[idx % len(self._default_colors)]
            hover = _adjust_color(color, 0.7)
            border = f"2px solid {TEXT_PRIMARY}" if lbl_name == label else "none"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: {TEXT_PRIMARY};
                    border: {border};
                    border-radius: 8px;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{ background-color: {hover}; }}
            """)

    def _set_labels(self, labels: dict[str, list[int]]):
        for btn in self._label_buttons:
            btn.deleteLater()
        self._label_buttons.clear()
        self._assigned_labels = {}
        for label in labels:
            self._create_label_button(label)
        self._assigned_labels = labels
        self._update_well_colors()

    def _reset_labels(self):
        self._set_labels({})
        self._selected_label = ""

    def _save_labels(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Labels", "", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        with open(path, "w") as f:
            json.dump(self._assigned_labels, f, indent=4)
        QMessageBox.information(self, "Saved", f"Labels saved to:\n{path}")

    def _import_labels(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Labels", "", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        with open(path) as f:
            labels = json.load(f)
        self._set_labels(labels)

    def _validate_groups(self) -> bool:
        return any(len(wells) > 0 for wells in self._assigned_labels.values())

    def _create_plots(self):
        if not self._validate_groups():
            QMessageBox.warning(
                self,
                "No Groups",
                "Please create at least one label and assign at least one well to it.",
            )
            return
        prefix = self._prefix_entry.text().strip()
        if not prefix:
            QMessageBox.warning(
                self,
                "No Prefix",
                "Please define the prefix used to indicate neuron age (e.g. DIV, t, day).",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if not path:
            return
        try:
            pdf_path = features_over_time(
                folder=self._selected_folder,
                labels=copy.deepcopy(self._assigned_labels),
                div_prefix=prefix,
                output_fileadress=path,
                colors=self._default_colors,
                show_datapoints=self._fot_datapoints_cb.isChecked(),
            )
            QMessageBox.information(self, "Saved", f"Figures saved to:\n{path}")
            webbrowser.open(f"file://{pdf_path}")
        except Exception:
            traceback.print_exc()
            QMessageBox.critical(
                self, "Error", "Something went wrong while creating the plots."
            )

    def _create_boxplots(self):
        if not self._validate_groups():
            QMessageBox.warning(
                self,
                "No Groups",
                "Please create at least one label and assign at least one well to it.",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if not path:
            return
        try:
            pdf_path = combined_feature_boxplots(
                folder=self._selected_folder,
                labels=copy.deepcopy(self._assigned_labels),
                output_fileadress=path,
                colors=self._default_colors,
                show_datapoints=self._bp_datapoints_cb.isChecked(),
                discern_wells=self._discern_wells_cb.isChecked(),
                well_amnt=self._well_amnt,
            )
            webbrowser.open(f"file://{pdf_path}")
            QMessageBox.information(self, "Saved", f"Figures saved to:\n{path}")
        except Exception:
            traceback.print_exc()
            QMessageBox.critical(
                self, "Error", "Something went wrong while creating the boxplots."
            )
