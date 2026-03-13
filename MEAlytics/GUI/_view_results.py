import json
import webbrowser
from functools import partial
from pathlib import Path

import h5py
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from MEAlytics.GUI._heatmap import HeatmapFrame
from MEAlytics.GUI._helpers import _electrode_grid, _well_grid
from MEAlytics.GUI._single_electrode_view import SingleElectrodeView

# GUI Imports
from MEAlytics.GUI._theme import (
    _BTN_STYLE_DEFAULT,
    _BTN_STYLE_SELECTED,
    ACCENT,
    ACCENT_MUTED,
    BORDER_COLOR,
    SURFACE_2,
    SURFACE_3,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARN_LAYOUT_BUTTON_STYLESHEET,
    make_divider,
    make_label,
)
from MEAlytics.GUI._whole_well_view import WholeWellView


def _grid_button(label: str, size: int = 56) -> QPushButton:
    btn = QPushButton(str(label))
    btn.setFixedSize(size, size)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)

    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {SURFACE_3};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_COLOR};
            border-radius: 0px;
            font-size: 14px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {ACCENT_MUTED};
            border-color: {ACCENT};
            color: {ACCENT};
        }}
    """)

    return btn


class _WellGrid(QWidget):
    well_clicked = pyqtSignal(int)

    def __init__(self, n_wells: int):
        super().__init__()
        self._n = n_wells
        self._buttons: list[QPushButton] = []
        self._selected_btn: QPushButton | None = None
        cols, rows = _well_grid(n_wells)

        layout = QGridLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        i = 1
        for r in range(rows):
            for c in range(cols):
                btn = _grid_button(i)
                btn.clicked.connect(partial(self._clicked, i))
                layout.addWidget(btn, r, c)
                self._buttons.append(btn)
                i += 1

        self.setFixedSize(cols * 56, rows * 56)

    def _clicked(self, well: int):
        self.well_clicked.emit(well)

    def highlight(self, well: int):
        if self._selected_btn is not None:
            self._selected_btn.setStyleSheet(_BTN_STYLE_DEFAULT)
        new_btn = self._buttons[well - 1]
        new_btn.setStyleSheet(_BTN_STYLE_SELECTED)
        self._selected_btn = new_btn


class _ElectrodeGrid(QWidget):
    electrode_clicked = pyqtSignal(int)

    def __init__(self, n_electrodes: int):
        super().__init__()
        mask = _electrode_grid(n_electrodes)

        layout = QGridLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        i = 1
        for row in range(mask.shape[0]):
            for col in range(mask.shape[1]):
                if mask[row, col]:
                    btn = _grid_button(i)
                    btn.clicked.connect(partial(self._clicked, i))
                    layout.addWidget(btn, row, col)
                    i += 1

        self.setFixedSize(mask.shape[1] * 56, mask.shape[0] * 56)

    def _clicked(self, electrode: int):
        self.electrode_clicked.emit(electrode)


class _ElidedPathLabel(QLabel):
    def __init__(self, prefix: str = ""):
        super().__init__()
        self._prefix = prefix
        self._full_text = ""
        self.setToolTip("")

    def set_path(self, path: str):
        self._full_text = path
        self.setToolTip(path)
        self._update_elided()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self):
        if not self._full_text:
            return
        fm = self.fontMetrics()
        available = self.width() - 4
        elided = fm.elidedText(
            self._prefix + self._full_text,
            Qt.TextElideMode.ElideMiddle,
            max(available, 40),
        )

        if elided != self.text():
            self.blockSignals(True)
            self.setText(elided)
            self.blockSignals(False)


class _WindowRegistry:
    def __init__(self):
        self._windows: list[QDialog] = []

    def register(self, dlg: QDialog):
        self._windows.append(dlg)
        dlg.destroyed.connect(
            lambda: self._windows.remove(dlg) if dlg in self._windows else None
        )

    def close_all(self):
        for w in list(self._windows):
            w.close()
        self._windows.clear()

    def count(self) -> int:
        return len(self._windows)


class ViewResultsView(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.app_state = app_state
        self._registry = _WindowRegistry()

        self._folder: str | None = None
        self._rawfile: str | None = None
        self._parameters: dict = {}
        self._n_wells: int = 0
        self._n_electrodes: int = 0
        self._selected_well: int = 1

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        header_row = QHBoxLayout()
        header_row.addWidget(make_label("View Results", "PageTitle"))

        self._close_all_btn = QPushButton("✕  Close All Windows")
        self._close_all_btn.setObjectName("DangerBtn")
        self._close_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_all_btn.setVisible(False)
        self._close_all_btn.clicked.connect(self._close_all_windows)
        header_row.addWidget(self._close_all_btn)

        root.addLayout(header_row)
        root.addWidget(make_divider())

        self._load_panel = self._build_load_panel()
        root.addWidget(self._load_panel)

        self._results_area = self._build_results_area()
        self._results_area.setVisible(False)
        root.addWidget(self._results_area, 1)

    def _build_load_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        title = QLabel("Load Analysis Results")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {TEXT_PRIMARY}; background: transparent"
        )
        layout.addWidget(title)

        desc = QLabel(
            "Select the output folder produced by MEAlytics and the original raw HDF5 file to explore your analysis results."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; background: transparent"
        )
        layout.addWidget(desc)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)
        self._folder_label = QLabel("No folder selected")
        self._folder_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; background: {SURFACE_2}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 7px; padding: 7px 12px;"
        )
        self._folder_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        folder_browse = QPushButton("Browse Output Folder")
        folder_browse.setObjectName("SecondaryBtn")
        folder_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_browse.clicked.connect(self._browse_folder)
        folder_label = QLabel("Output folder:")
        folder_label.setStyleSheet("background: transparent")
        folder_row.addWidget(folder_label)
        folder_row.addWidget(self._folder_label, 1)
        folder_row.addWidget(folder_browse)
        layout.addLayout(folder_row)

        raw_row = QHBoxLayout()
        raw_row.setSpacing(10)
        self._rawfile_label = QLabel("No file selected")
        self._rawfile_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; background: {SURFACE_2}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 7px; padding: 7px 12px;"
        )
        self._rawfile_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        raw_browse = QPushButton("Browse Raw File")
        raw_browse.setObjectName("SecondaryBtn")
        raw_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        raw_browse.clicked.connect(self._browse_rawfile)
        raw_label = QLabel("Raw HDF5 file:")
        raw_label.setStyleSheet("background: transparent")
        raw_row.addWidget(raw_label)
        raw_row.addWidget(self._rawfile_label, 1)
        raw_row.addWidget(raw_browse)
        layout.addLayout(raw_row)

        load_btn = QPushButton("Load Results")
        load_btn.setObjectName("PrimaryBtn")
        load_btn.setFixedWidth(180)
        load_btn.setMinimumHeight(40)
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.clicked.connect(self._load_results)
        layout.addWidget(load_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        return panel

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self._folder = path
            self._folder_label.setText(path)
            self._folder_label.setStyleSheet(
                self._folder_label.styleSheet().replace(TEXT_MUTED, TEXT_PRIMARY)
            )

    def _browse_rawfile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Raw HDF5 File", "", "HDF5 Files (*.h5 *.hdf5);;All Files (*)"
        )
        if path:
            self._rawfile = path
            self._rawfile_label.setText(path)
            self._rawfile_label.setStyleSheet(
                self._rawfile_label.styleSheet().replace(TEXT_MUTED, TEXT_PRIMARY)
            )

    def _load_results(self):
        if not self._folder or not self._rawfile:
            QMessageBox.warning(
                self,
                "Missing Paths",
                "Please select both an output folder and a raw file.",
            )
            return
        self.load_from_paths(self._folder, self._rawfile)

    def load_from_paths(self, folder: str, rawfile: str):
        try:
            params_path = Path(folder) / "parameters.json"
            with open(params_path) as f:
                self._parameters = json.load(f)

            with h5py.File(rawfile, "r") as hdf:
                self.datashape = hdf[
                    "Data/Recording_0/AnalogStream/Stream_0/ChannelData"
                ].shape

            self._folder = folder
            self._rawfile = rawfile
            self._n_electrodes = self._parameters["electrode amount"]
            self._n_wells = int(self.datashape[0] / self._n_electrodes)

            self._registry.close_all()

            self._populate_results()

            self._load_panel.setVisible(False)
            self._results_area.setVisible(True)
            self._close_all_btn.setVisible(False)

        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Could not load results:\n{exc}")

    def _build_results_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # File info bar
        self._info_bar = QFrame()
        self._info_bar.setObjectName("Card")
        info_layout = QHBoxLayout(self._info_bar)
        info_layout.setContentsMargins(16, 10, 16, 10)
        info_layout.setSpacing(24)

        self._folder_info = _ElidedPathLabel("")
        self._folder_info.setStyleSheet(
            f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent"
        )
        self._folder_info.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._rawfile_info = _ElidedPathLabel("")
        self._rawfile_info.setStyleSheet(
            f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent"
        )
        self._rawfile_info.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        info_layout.addWidget(self._folder_info, 1)
        info_layout.addWidget(self._rawfile_info, 1)

        reload_btn = QPushButton("⟳  Load Different File")
        reload_btn.setObjectName("SecondaryBtn")
        reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_btn.clicked.connect(self._show_load_panel)
        info_layout.addWidget(reload_btn)

        layout.addWidget(self._info_bar)

        # Layout warning
        warn_btn = QPushButton(
            "The well/electrode layout is auto-generated and may not match the physical plate exactly. Click here for details."
        )
        warn_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        warn_btn.setStyleSheet(WARN_LAYOUT_BUTTON_STYLESHEET)
        warn_btn.clicked.connect(
            lambda: webbrowser.open(
                "https://cureq.github.io/MEAlytics/supported_plates/"
            )
        )
        layout.addWidget(warn_btn)

        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, 1)

        return container

    def _populate_results(self):
        self._tabs.clear()

        # Update info bar
        self._folder_info.set_path(self._folder)
        self._rawfile_info.set_path(self._rawfile)

        self._tabs.addTab(self._build_sev_tab(), "Single Electrode View")
        self._tabs.addTab(self._build_wwv_tab(), "Whole Well View")
        self._tabs.addTab(self._build_heatmap_tab(), "Heatmap")

    def _build_sev_tab(self) -> QWidget:
        tab = QWidget()
        outer = QHBoxLayout(tab)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(20)

        left_panel = QFrame()
        left_panel.setObjectName("Card")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        select_well_label = make_label("Select Well", "SectionLabel")
        select_well_label.setStyleSheet("background: transparent")
        left_layout.addWidget(select_well_label)

        self._sev_well_grid = _WellGrid(self._n_wells)
        self._sev_well_grid.well_clicked.connect(self._sev_select_well)
        scroll_wells = QScrollArea()
        scroll_wells.setWidgetResizable(True)
        scroll_wells.setFrameShape(QFrame.Shape.NoFrame)
        scroll_wells.setWidget(self._sev_well_grid)
        left_layout.addWidget(scroll_wells)

        self._sev_well_label = QLabel("Well 1 selected")
        self._sev_well_label.setObjectName("StatusBadge")
        left_layout.addWidget(
            self._sev_well_label, alignment=Qt.AlignmentFlag.AlignLeft
        )

        outer.addWidget(left_panel)

        right_panel = QFrame()
        right_panel.setObjectName("Card")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        select_electrode_label = make_label("Select Electrode", "SectionLabel")
        select_electrode_label.setStyleSheet("background: transparent")
        right_layout.addWidget(select_electrode_label)

        self._sev_electrode_grid = _ElectrodeGrid(self._n_electrodes)
        self._sev_electrode_grid.electrode_clicked.connect(
            self._open_single_electrode_window
        )
        scroll_elec = QScrollArea()
        scroll_elec.setWidgetResizable(True)
        scroll_elec.setFrameShape(QFrame.Shape.NoFrame)
        scroll_elec.setWidget(self._sev_electrode_grid)
        right_layout.addWidget(scroll_elec)

        hint = QLabel("Click an electrode to open its visualisation.")
        hint.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent"
        )
        right_layout.addWidget(hint)

        outer.addWidget(right_panel)

        # Initialise well selection to 1
        self._selected_well = 1
        return tab

    def _sev_select_well(self, well: int):
        self._selected_well = well
        self._sev_well_grid.highlight(well)
        self._sev_well_label.setText(f"Well {well} selected")

    def _open_single_electrode_window(self, electrode: int):
        dlg = SingleElectrodeView(
            self._folder, self._rawfile, self._selected_well, electrode
        )
        self._registry.register(dlg)
        self._close_all_btn.setVisible(True)
        dlg.show()

    def _build_wwv_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(make_label("Select Well", "SectionLabel"))

        hint = QLabel("Click a well to open its visualisation.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(hint)

        well_grid = _WellGrid(self._n_wells)
        well_grid.well_clicked.connect(self._open_whole_well_window)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(well_grid)
        layout.addWidget(scroll, 1)

        return tab

    def _open_whole_well_window(self, well: int):
        dlg = WholeWellView(self._folder, well)
        self._registry.register(dlg)
        self._close_all_btn.setVisible(True)
        dlg.show()

    def _build_heatmap_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        layout.addWidget(make_label("Heatmap", "SectionLabel"))

        desc = QLabel(
            "Generate a heatmap of network-wide activity across all wells for the full recording."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(desc)

        gen_btn = QPushButton("Generate Heatmap")
        gen_btn.setObjectName("PrimaryBtn")
        gen_btn.setFixedWidth(220)
        gen_btn.setMinimumHeight(44)
        gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gen_btn.clicked.connect(self._open_heatmap_window)
        layout.addWidget(gen_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

        return tab

    def _open_heatmap_window(self):
        xwells, ywells = _well_grid(self._n_wells)
        dlg = HeatmapFrame(
            self.datashape,
            self._parameters,
            xwells,
            ywells,
            self._folder,
            _electrode_grid,
        )
        self._registry.register(dlg)
        self._close_all_btn.setVisible(True)
        dlg.show()

    def _close_all_windows(self):
        self._registry.close_all()
        self._close_all_btn.setVisible(False)

    def _show_load_panel(self):
        self._registry.close_all()
        self._close_all_btn.setVisible(False)
        self._results_area.setVisible(False)
        self._load_panel.setVisible(True)
