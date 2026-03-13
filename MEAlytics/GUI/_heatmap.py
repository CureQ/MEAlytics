import os
import webbrowser

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QWidget, QSizePolicy,
    QSlider, QFileDialog, QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPalette, QColor

from MEAlytics.GUI._theme import (
    SURFACE_1, SURFACE_2, SURFACE_3, BORDER_COLOR,
    ACCENT, ACCENT_MUTED, ACCENT_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    DARK_BG, WARNING, DANGER,
    make_primary_btn, make_secondary_btn, make_label,
)

from MEAlytics.core._heatmap import (
    cmap_creation, create_placeholder_figure,
    data_prepper, make_hm, make_hm_img,
)

class DataPrepWorker(QThread):
    finished = pyqtSignal(object)
    error    = pyqtSignal(str)

    def __init__(self, h5_file: str, parameters: dict, hm_vars: dict,
                 electrode_grid_fn):
        super().__init__()
        self._h5_file = h5_file
        self._parameters = parameters
        self._hm_vars = hm_vars
        self._electrode_grid_fn = electrode_grid_fn

    def run(self) -> None:
        try:
            result = data_prepper(
                self._h5_file,
                self._parameters,
                self._hm_vars,
                self._electrode_grid_fn,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class FullHeatmapWorker(QThread):
    finished = pyqtSignal(object)
    error    = pyqtSignal(str)

    def __init__(self, hm_vars: dict, classes: dict, colour_classes: dict):
        super().__init__()
        self._hm_vars        = hm_vars
        self._classes        = classes
        self._colour_classes = colour_classes

    def run(self) -> None:
        try:
            fig = make_hm_img(self._hm_vars, self._classes, self._colour_classes)
            self.finished.emit(fig)
        except Exception as exc:
            self.error.emit(str(exc))

class ProgressDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Preparing data")
        self.setFixedSize(400, 70)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        lbl = QLabel("Preparing data, please wait…")
        lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 14px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

class HeatmapFrame(QDialog):
    def __init__(self, datashape, parameters: dict, xwells: int, ywells: int, folder: str, electrode_grid_fn):
        super().__init__()
        self.setWindowTitle("Heatmap")
        self.resize(1100, 720)
        self.setMinimumSize(800, 500)

        self._parameters       = parameters
        self._folder           = folder
        self._h5_file          = os.path.join(folder, "output_values.h5")
        self._electrode_grid_fn = electrode_grid_fn

        self._hm_vars: dict = {
            "fps":              10,
            "Num frames":       int(parameters['measurements'] / parameters['sampling rate'] * 10),
            "df":               None,
            "n_Wells":          None,
            "n_Electrodes":     None,
            "v_max":            None,
            "Size":             None,
            "Precomputed Max":  None,
            "Rows":             ywells,
            "Cols":             xwells,
            "cmap":             None,
            "max_df":           None,
            "last_hm":          None,
            "background_color": '#1a1a1a',
        }

        self._classes: dict = {
            "Unknown": list(range(0, int(datashape[0] / parameters["electrode amount"]) + 1))
        }
        self._colour_classes: dict = {"Unknown": "grey"}

        self._anim        = None
        self._canvas      = None
        self._is_dragging = False
        self._worker      = None

        self._hm_vars["cmap"] = cmap_creation()

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        plot_col = QVBoxLayout()
        plot_col.setSpacing(8)

        self._plot_frame = QFrame()
        self._plot_frame.setObjectName("Card")
        self._plot_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._plot_layout = QVBoxLayout(self._plot_frame)
        self._plot_layout.setContentsMargins(0, 0, 0, 0)
        self._plot_layout.setSpacing(0)
        plot_col.addWidget(self._plot_frame, stretch=1)

        self._slider_row = QWidget()
        slider_row_layout = QHBoxLayout(self._slider_row)
        slider_row_layout.setContentsMargins(4, 0, 4, 0)
        slider_row_layout.setSpacing(8)

        self._from_label = QLabel("0.0s")
        self._from_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        slider_row_layout.addWidget(self._from_label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, max(0, self._hm_vars["Num frames"] - 1))

        self._slider.sliderPressed.connect(self._on_slider_press)
        self._slider.sliderReleased.connect(self._on_slider_release)
        self._slider.valueChanged.connect(self._on_slider_change)
        slider_row_layout.addWidget(self._slider, stretch=1)

        self._to_label = QLabel(f"{self._hm_vars['Num frames'] / 10:.1f}s")
        self._to_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        slider_row_layout.addWidget(self._to_label)

        self._slider_row.setVisible(False)
        plot_col.addWidget(self._slider_row)

        warn_btn = QPushButton(
            "Warning: The well/electrode layout is auto-generated and may not match "
            "the physical plate exactly. Click here for details."
        )
        warn_btn.setObjectName("SecondaryBtn")
        warn_btn.setStyleSheet(
            f"background-color: {SURFACE_2}; color: {WARNING}; "
            f"border: 1px solid {WARNING}; border-radius: 8px; "
            f"padding: 7px 12px; font-size: 12px; text-align: left;"
        )
        warn_btn.clicked.connect(
            lambda: webbrowser.open_new("https://cureq.github.io/MEAlytics/supported_plates/")
        )
        plot_col.addWidget(warn_btn)

        root.addLayout(plot_col, stretch=1)

        ctrl_panel = QFrame()
        ctrl_panel.setObjectName("Card")
        ctrl_panel.setFixedWidth(200)
        ctrl_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        ctrl_layout = QVBoxLayout(ctrl_panel)
        ctrl_layout.setContentsMargins(14, 18, 14, 18)
        ctrl_layout.setSpacing(12)

        section_lbl = QLabel("HEATMAP")
        section_lbl.setObjectName("SidebarSection")
        ctrl_layout.addWidget(section_lbl)

        self._btn_process = make_primary_btn("Process Data")
        self._btn_process.clicked.connect(self._generate_data_handler)
        ctrl_layout.addWidget(self._btn_process)

        self._btn_animate = make_secondary_btn("Show Heatmap")
        self._btn_animate.setEnabled(False)
        self._btn_animate.clicked.connect(
            lambda: self._start_animation(self._hm_vars, self._classes, self._colour_classes)
        )
        ctrl_layout.addWidget(self._btn_animate)

        self._btn_total = make_secondary_btn("Total Activity")
        self._btn_total.setEnabled(False)
        self._btn_total.clicked.connect(self._show_full_heatmap_handler)
        ctrl_layout.addWidget(self._btn_total)

        ctrl_layout.addStretch()
        root.addWidget(ctrl_panel)

        self._show_placeholder()

    def closeEvent(self, event) -> None:
        """Ensure all processes are terminated as to not slow down the main GUI"""
        if self._anim is not None:
            try:
                self._anim.event_source.stop()
            except Exception:
                pass
            self._anim = None

        plt.close("all")

        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            if not self._worker.wait(3000):
                self._worker.terminate()
                self._worker.wait()
        self._worker = None

        super().closeEvent(event)

    def _show_placeholder(self) -> None:
        placeholder_fig = create_placeholder_figure(self._hm_vars)
        self._replace_canvas(placeholder_fig)

    def _replace_canvas(self, fig) -> None:
        self._clear_layout(self._plot_layout)
        canvas = FigureCanvasQTAgg(fig)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._plot_layout.addWidget(canvas, stretch=1)
        canvas.draw()
        self._canvas = canvas

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _generate_data_handler(self) -> None:
        self._progress_dlg = ProgressDialog()
        self._progress_dlg.show()

        self._btn_process.setEnabled(False)

        self._worker = DataPrepWorker(
            self._h5_file, self._parameters, self._hm_vars, self._electrode_grid_fn
        )
        self._worker.finished.connect(self._on_data_ready)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_data_ready(self, result) -> None:
        (
            self._hm_vars["df"],
            self._hm_vars["n_Wells"],
            self._hm_vars["n_Electrodes"],
            self._hm_vars["v_max"],
            self._hm_vars["Size"],
            self._hm_vars["Precomputed Max"],
            self._hm_vars["max_df"],
        ) = result

        self._btn_animate.setEnabled(True)
        self._btn_total.setEnabled(True)
        self._btn_process.setEnabled(False)

        self._progress_dlg.accept()
        self._progress_dlg = None

    def _on_worker_error(self, message: str) -> None:
        print(f"Worker error: {message}")
        self._btn_process.setEnabled(True)
        if hasattr(self, '_progress_dlg') and self._progress_dlg:
            self._progress_dlg.accept()
            self._progress_dlg = None

    def _start_animation(self, vars_: dict, classes: dict, colour_classes: dict) -> None:
        if self._anim is not None:
            self._anim.event_source.stop()
            self._anim = None

        fig, update_func = make_hm(vars_, classes, colour_classes)
        self._update_func = update_func
        self._replace_canvas(fig)

        n = vars_["Num frames"]
        self._slider.setRange(0, max(0, n - 1))
        self._to_label.setText(f"{n / 10:.1f}s")
        self._from_label.setText("0.0s")
        self._slider_row.setVisible(True)
        self._slider.setValue(0)

        def animation_update_wrapper(frame: int):
            if not self._is_dragging:
                self._slider.blockSignals(True)
                self._slider.setValue(frame)
                self._slider.blockSignals(False)
            return update_func(frame)

        self._anim = animation.FuncAnimation(
            fig,
            animation_update_wrapper,
            frames=n,
            interval=100,
            blit=False,
            repeat=True,
        )

        vars_["last_hm"] = "animation_hm"
        self._canvas.draw()

    def _on_slider_press(self) -> None:
        self._is_dragging = True
        if self._anim is not None:
            self._anim.event_source.stop()

    def _on_slider_release(self) -> None:
        self._is_dragging = False
        if self._anim is not None:
            current = self._slider.value()
            n = self._hm_vars["Num frames"]
            self._anim.frame_seq = iter(range(current, n))
            self._anim.event_source.start()

    def _on_slider_change(self, value: int) -> None:
        if self._is_dragging and hasattr(self, '_update_func'):
            self._update_func(value)
            self._canvas.draw_idle()

    def _show_full_heatmap_handler(self) -> None:
        if self._anim is not None:
            self._anim.event_source.stop()
            self._anim = None

        self._progress_dlg = ProgressDialog()
        self._progress_dlg.show()

        self._btn_animate.setEnabled(False)
        self._btn_total.setEnabled(False)

        self._worker = FullHeatmapWorker(
            self._hm_vars, self._classes, self._colour_classes
        )
        self._worker.finished.connect(self._on_full_heatmap_ready)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_full_heatmap_ready(self, fig) -> None:
        self._replace_canvas(fig)
        self._slider_row.setVisible(False)

        self._hm_vars["last_hm"] = "total_hm"

        self._btn_animate.setEnabled(True)
        self._btn_total.setEnabled(True)

        self._progress_dlg.accept()
        self._progress_dlg = None