import copy
import json
import os

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from MEAlytics.core._bandpass import butter_bandpass_filter
from MEAlytics.core._burst_detection import burst_detection
from MEAlytics.core._spike_validation import spike_validation
from MEAlytics.core._threshold import fast_threshold
from MEAlytics.core.file_io._read_mea_data import get_mea_file_reader
from MEAlytics.GUI._helpers import _get_float, _get_int, _set_entry, _show_error
from MEAlytics.GUI._theme import (
    DARK_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TOOLBAR_STYLESHEET,
    make_divider,
    make_primary_btn,
    make_secondary_btn,
)


def _make_group(title: str, rows: list[tuple]) -> tuple[QGroupBox, dict]:
    group = QGroupBox(title)
    layout = QGridLayout()
    layout.setSpacing(8)
    layout.setContentsMargins(16, 18, 16, 12)
    group.setLayout(layout)

    fields: dict[str, QLineEdit] = {}
    col_pairs = [(0, 1), (2, 3)]

    grid_row = 0
    col_idx = 0
    for label_text, key in rows:
        lbl_col, entry_col = col_pairs[col_idx]

        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; background: transparent"
        )
        layout.addWidget(lbl, grid_row, lbl_col)

        entry = QLineEdit()
        entry.setMinimumWidth(100)
        layout.addWidget(entry, grid_row, entry_col)
        fields[key] = entry

        col_idx += 1
        if col_idx >= len(col_pairs):
            col_idx = 0
            grid_row += 1

    return group, fields


class SingleElectrodeView(QDialog):
    def __init__(self, folder: str, rawfile: str, well: int, electrode: int):
        super().__init__()
        self.setWindowTitle(f"Well: {well} - Electrode: {electrode}")
        self.resize(1280, 860)
        self.setMinimumSize(900, 600)

        with open(os.path.join(folder, "parameters.json")) as f:
            self.parameters = json.load(f)
        self.parameters["output hdf file"] = os.path.join(folder, "output_values.h5")
        self.electrode = electrode
        self.well = well
        self.rawfile = rawfile
        self.folder = folder

        self.MEA_file = get_mea_file_reader(self.rawfile)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(0)

        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)

        self._build_spike_tab()
        self._build_burst_tab()

        self._reset_spike()
        self._burst_reset()

    def _build_spike_tab(self) -> None:
        spike_tab = QWidget()
        tab_layout = QVBoxLayout(spike_tab)
        tab_layout.setContentsMargins(16, 16, 16, 16)
        tab_layout.setSpacing(12)

        self._spike_plot_container = QFrame()
        self._spike_plot_container.setObjectName("Card")
        self._spike_plot_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._spike_plot_layout = QVBoxLayout(self._spike_plot_container)
        self._spike_plot_layout.setContentsMargins(0, 0, 0, 0)
        self._spike_plot_layout.setSpacing(0)
        tab_layout.addWidget(self._spike_plot_container, stretch=1)

        tab_layout.addWidget(make_divider())

        settings_row = QHBoxLayout()
        settings_row.setSpacing(12)

        bp_group, bp_fields = _make_group(
            "Bandpass Parameters",
            [
                ("Low cutoff", "low cutoff"),
                ("High cutoff", "high cutoff"),
                ("Order", "order"),
            ],
        )
        self._lowcut_entry = bp_fields["low cutoff"]
        self._highcut_entry = bp_fields["high cutoff"]
        self._order_entry = bp_fields["order"]
        settings_row.addWidget(bp_group)

        # Threshold group
        th_group, th_fields = _make_group(
            "Threshold Parameters",
            [
                ("Std dev multiplier", "standard deviation multiplier"),
                ("RMS multiplier", "rms multiplier"),
                ("Threshold portion", "threshold portion"),
            ],
        )
        self._stdev_entry = th_fields["standard deviation multiplier"]
        self._rms_entry = th_fields["rms multiplier"]
        self._thpn_entry = th_fields["threshold portion"]
        settings_row.addWidget(th_group)

        val_group = QGroupBox("Spike Detection Parameters")
        val_layout = QGridLayout()
        val_layout.setSpacing(8)
        val_layout.setContentsMargins(16, 18, 16, 12)
        val_group.setLayout(val_layout)

        def _lbl(text):
            label = QLabel(text)
            label.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 12px; background:transparent"
            )
            return label

        val_layout.addWidget(_lbl("Spike validation method:"), 0, 0)
        self._validation_combo = QComboBox()
        self._validation_combo.addItems(["Noisebased", "none"])
        self._validation_combo.currentTextChanged.connect(self._set_states)
        val_layout.addWidget(self._validation_combo, 0, 1)

        val_layout.addWidget(_lbl("Refractory period:"), 1, 0)
        self._rfpd_entry = QLineEdit()
        val_layout.addWidget(self._rfpd_entry, 1, 1)

        val_layout.addWidget(_lbl("Drop amplitude:"), 1, 2)
        self._dropamplitude_entry = QLineEdit()
        val_layout.addWidget(self._dropamplitude_entry, 1, 3)

        val_layout.addWidget(_lbl("Exit time:"), 2, 0)
        self._exittime_entry = QLineEdit()
        val_layout.addWidget(self._exittime_entry, 2, 1)

        val_layout.addWidget(_lbl("Max drop:"), 2, 2)
        self._maxdrop_entry = QLineEdit()
        val_layout.addWidget(self._maxdrop_entry, 2, 3)

        plot_rect_lbl = _lbl("Plot validation rectangles:")
        plot_rect_lbl.setToolTip(
            "Display the rectangles used to validate the spikes.\n"
            "Warning: computationally expensive - may take a while."
        )
        val_layout.addWidget(plot_rect_lbl, 3, 0)
        self._plot_rectangle_cb = QCheckBox()
        val_layout.addWidget(self._plot_rectangle_cb, 3, 1)

        settings_row.addWidget(val_group)
        tab_layout.addLayout(settings_row)

        action_bar = QFrame()
        action_bar.setObjectName("Card")
        bar_layout = QHBoxLayout(action_bar)
        bar_layout.setContentsMargins(16, 10, 16, 10)
        bar_layout.setSpacing(10)

        update_btn = make_primary_btn("▶  Update Plot")
        update_btn.setToolTip(
            "These settings are for visualisation purposes only, they will not affect "
            "the current analysis outcomes or further steps such as burst or network burst "
            "detection. They are solely here to show how parameters could alter the analysis."
        )
        update_btn.clicked.connect(self._update_spike_plot)
        bar_layout.addWidget(update_btn)

        reset_btn = make_secondary_btn("↺  Reset")
        reset_btn.clicked.connect(self._reset_spike)
        bar_layout.addWidget(reset_btn)
        bar_layout.addStretch()

        tab_layout.addWidget(action_bar)
        self.tabs.addTab(spike_tab, "Spike Detection")

    def _build_burst_tab(self) -> None:
        burst_tab = QWidget()
        tab_layout = QVBoxLayout(burst_tab)
        tab_layout.setContentsMargins(16, 16, 16, 16)
        tab_layout.setSpacing(12)

        self._burst_plot_container = QFrame()
        self._burst_plot_container.setObjectName("Card")
        self._burst_plot_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._burst_plot_layout = QHBoxLayout(self._burst_plot_container)
        self._burst_plot_layout.setContentsMargins(0, 0, 0, 0)
        self._burst_plot_layout.setSpacing(0)
        tab_layout.addWidget(self._burst_plot_container, stretch=1)

        tab_layout.addWidget(make_divider())

        burst_group = QGroupBox("Burst Detection Parameters")
        burst_layout = QGridLayout()
        burst_layout.setSpacing(8)
        burst_layout.setContentsMargins(16, 18, 16, 12)
        burst_group.setLayout(burst_layout)

        def _lbl(text):
            label = QLabel(text)
            label.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 12px; background:transparent"
            )
            return label

        burst_layout.addWidget(_lbl("Minimal amount of spikes:"), 0, 0)
        self._minspikes_entry = QLineEdit()
        burst_layout.addWidget(self._minspikes_entry, 0, 1)

        burst_layout.addWidget(_lbl("Max interval threshold:"), 0, 2)
        self._max_iv_entry = QLineEdit()
        burst_layout.addWidget(self._max_iv_entry, 0, 3)

        burst_layout.addWidget(_lbl("Default interval threshold:"), 1, 0)
        self._def_iv_entry = QLineEdit()
        burst_layout.addWidget(self._def_iv_entry, 1, 1)

        burst_layout.addWidget(_lbl("KDE bandwidth:"), 1, 2)
        self._kde_bw_entry = QLineEdit()
        burst_layout.addWidget(self._kde_bw_entry, 1, 3)

        tab_layout.addWidget(burst_group)

        action_bar = QFrame()
        action_bar.setObjectName("Card")
        bar_layout = QHBoxLayout(action_bar)
        bar_layout.setContentsMargins(16, 10, 16, 10)
        bar_layout.setSpacing(10)

        update_btn = make_primary_btn("▶  Update Plot")
        update_btn.setToolTip(
            "These settings are for visualisation purposes only, they will not affect "
            "the current analysis outcomes or further steps such as network burst detection."
        )
        update_btn.clicked.connect(self._update_burst_plot)
        bar_layout.addWidget(update_btn)

        reset_btn = make_secondary_btn("↺  Reset")
        reset_btn.clicked.connect(self._burst_reset)
        bar_layout.addWidget(reset_btn)
        bar_layout.addStretch()

        tab_layout.addWidget(action_bar)
        self.tabs.addTab(burst_tab, "Burst Detection")

    def _set_states(self) -> None:
        noise_based = self._validation_combo.currentText() == "Noisebased"
        for widget in (
            self._exittime_entry,
            self._maxdrop_entry,
            self._dropamplitude_entry,
            self._plot_rectangle_cb,
        ):
            widget.setEnabled(noise_based)
        if not noise_based:
            self._plot_rectangle_cb.setChecked(False)

    def _default_spike_values(self) -> None:
        p = self.parameters
        _set_entry(self._lowcut_entry, p["low cutoff"])
        _set_entry(self._highcut_entry, p["high cutoff"])
        _set_entry(self._order_entry, p["order"])
        _set_entry(self._stdev_entry, p["standard deviation multiplier"])
        _set_entry(self._rms_entry, p["rms multiplier"])
        _set_entry(self._thpn_entry, p["threshold portion"])
        _set_entry(self._rfpd_entry, p["refractory period"])
        _set_entry(self._exittime_entry, p["exit time"])
        _set_entry(self._dropamplitude_entry, p["drop amplitude"])
        _set_entry(self._maxdrop_entry, p["max drop"])
        self._plot_rectangle_cb.setChecked(False)
        idx = self._validation_combo.findText(p["spike validation method"])
        if idx >= 0:
            self._validation_combo.setCurrentIndex(idx)
        self._set_states()

    def _reset_spike(self) -> None:
        for w in (
            self._exittime_entry,
            self._maxdrop_entry,
            self._dropamplitude_entry,
            self._plot_rectangle_cb,
        ):
            w.setEnabled(True)
        self._default_spike_values()
        self._set_states()
        self._update_spike_plot()

    def _update_spike_plot(self) -> None:
        temp = copy.deepcopy(self.parameters)

        try:
            temp["low cutoff"] = _get_int(self._lowcut_entry)
            temp["high cutoff"] = _get_int(self._highcut_entry)
            temp["order"] = _get_int(self._order_entry)
            temp["standard deviation multiplier"] = _get_float(self._stdev_entry)
            temp["rms multiplier"] = _get_float(self._rms_entry)
            temp["threshold portion"] = _get_float(self._thpn_entry)
            temp["refractory period"] = _get_float(self._rfpd_entry)

            if self._validation_combo.currentText() == "none":
                temp["drop amplitude"] = 0
            else:
                temp["exit time"] = _get_float(self._exittime_entry)
                temp["drop amplitude"] = _get_float(self._dropamplitude_entry)
                temp["max drop"] = _get_float(self._maxdrop_entry)
        except Exception as e:
            _show_error(
                self,
                f"Parameter conversion failed. Ensure all fields contain valid numbers.\n\nError: {e}",
            )

        temp["output path"] = self.folder

        try:
            self._plot_single_electrode(temp)
        except Exception as e:
            _show_error(
                self,
                f"Something went wrong while creating the plot.\n\nError: {e}",
            )

    def _plot_single_electrode(self, parameters: dict) -> None:
        raw_data = self.MEA_file.get_voltage_trace(self.well, self.electrode)
        electrode_data = butter_bandpass_filter(raw_data, parameters)
        threshold = fast_threshold(electrode_data, parameters)
        fig = spike_validation(
            data=electrode_data,
            electrode=self.electrode,
            well=self.well,
            threshold=threshold,
            parameters=parameters,
            plot_electrodes=True,
            savedata=False,
            plot_rectangles=self._plot_rectangle_cb.isChecked(),
        )

        self._apply_dark_theme(fig)
        self._replace_canvas(
            self._spike_plot_container, self._spike_plot_layout, fig, toolbar=True
        )

    def _default_burst_values(self) -> None:
        p = self.parameters
        _set_entry(self._minspikes_entry, p["minimal amount of spikes"])
        _set_entry(self._def_iv_entry, p["default interval threshold"])
        _set_entry(self._max_iv_entry, p["max interval threshold"])
        _set_entry(self._kde_bw_entry, p["burst detection kde bandwidth"])

    def _burst_reset(self) -> None:
        self._default_burst_values()
        self._update_burst_plot()

    def _update_burst_plot(self) -> None:
        temp = copy.deepcopy(self.parameters)

        try:
            temp["minimal amount of spikes"] = _get_int(self._minspikes_entry)
            temp["default interval threshold"] = _get_float(self._def_iv_entry)
            temp["max interval threshold"] = _get_float(self._max_iv_entry)
            temp["burst detection kde bandwidth"] = _get_float(self._kde_bw_entry)
        except Exception as e:
            _show_error(
                self,
                f"Parameter conversion failed. Ensure all fields contain valid numbers.\n\nError: {e}",
            )

        temp["output path"] = self.folder

        try:
            self._plot_burst_detection(temp)
        except Exception as e:
            _show_error(
                self,
                f"Something went wrong while creating the plot.\n\nError: {e}",
            )

    def _plot_burst_detection(self, parameters: dict) -> None:
        raw_data = self.MEA_file.get_voltage_trace(self.well, self.electrode)
        electrode_data = butter_bandpass_filter(raw_data, parameters)
        KDE_fig, burst_fig = burst_detection(
            data=electrode_data,
            electrode=self.electrode,
            well=self.well,
            parameters=parameters,
            plot_electrodes=True,
            savedata=False,
        )

        self._apply_dark_theme(KDE_fig)
        self._apply_dark_theme(burst_fig)

        self._clear_layout(self._burst_plot_layout)

        burst_canvas = FigureCanvasQTAgg(burst_fig)
        burst_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        burst_wrapper = QWidget()
        burst_wrapper_layout = QVBoxLayout(burst_wrapper)
        burst_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        burst_wrapper_layout.setSpacing(0)
        burst_wrapper_layout.addWidget(burst_canvas, stretch=1)
        burst_toolbar = NavigationToolbar2QT(burst_canvas, burst_wrapper)
        burst_toolbar.setStyleSheet(TOOLBAR_STYLESHEET)
        burst_wrapper_layout.addWidget(burst_toolbar)
        burst_canvas.draw()

        kde_canvas = FigureCanvasQTAgg(KDE_fig)
        kde_canvas.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        kde_canvas.draw()

        self._burst_plot_layout.addWidget(burst_wrapper, stretch=3)
        self._burst_plot_layout.addWidget(kde_canvas, stretch=1)

    @staticmethod
    def _apply_dark_theme(fig) -> None:
        bg = DARK_BG
        fg = TEXT_PRIMARY

        fig.set_facecolor(bg)
        for ax in fig.axes:
            ax.set_facecolor(bg)
            ax.xaxis.label.set_color(fg)
            ax.yaxis.label.set_color(fg)
            for spine in ax.spines.values():
                spine.set_color(fg)
            ax.tick_params(colors=fg)
            ax.title.set_color(fg)

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _replace_canvas(
        self, container: QFrame, layout: QVBoxLayout, fig, toolbar: bool = False
    ) -> None:
        self._clear_layout(layout)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(canvas, stretch=1)

        if toolbar:
            nav = NavigationToolbar2QT(canvas, container)
            nav.setStyleSheet(TOOLBAR_STYLESHEET)
            palette = nav.palette()
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
            nav.setPalette(palette)
            layout.addWidget(nav)

        canvas.draw()
