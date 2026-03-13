import copy
import json
import os

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
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

from MEAlytics.core._network_burst_detection import network_burst_detection
from MEAlytics.core._plotting import well_electrodes_kde
from MEAlytics.GUI._helpers import _get_float, _set_entry, _show_error
from MEAlytics.GUI._theme import (
    DARK_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TOOLBAR_STYLESHEET,
    make_divider,
    make_primary_btn,
    make_secondary_btn,
)


class WholeWellView(QDialog):
    _DEFAULT_BW = 0.1
    _TH_METHODS = ["Yen", "Otsu", "Li", "Isodata", "Mean", "Minimum", "Triangle"]

    def __init__(self, folder: str, well: int):
        super().__init__()
        self.setWindowTitle(f"Well: {well}")
        self.resize(1280, 860)
        self.setMinimumSize(900, 600)

        with open(os.path.join(folder, "parameters.json")) as fh:
            self.parameters = json.load(fh)
        self.parameters["output hdf file"] = os.path.join(folder, "output_values.h5")
        self.folder = folder
        self.well = well

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(0)

        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)

        self._build_nbd_tab()
        self._build_activity_tab()

        self._reset_nbd()
        self._reset_activity()

    def _build_nbd_tab(self) -> None:
        nbd_tab = QWidget()
        tab_layout = QVBoxLayout(nbd_tab)
        tab_layout.setContentsMargins(16, 16, 16, 16)
        tab_layout.setSpacing(12)

        self._nbd_plot_container = QFrame()
        self._nbd_plot_container.setObjectName("Card")
        self._nbd_plot_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._nbd_plot_layout = QVBoxLayout(self._nbd_plot_container)
        self._nbd_plot_layout.setContentsMargins(0, 0, 0, 0)
        self._nbd_plot_layout.setSpacing(0)
        tab_layout.addWidget(self._nbd_plot_container, stretch=1)

        tab_layout.addWidget(make_divider())

        nbd_group = QGroupBox("Network Burst Detection Parameters")
        nbd_layout = QGridLayout()
        nbd_layout.setSpacing(8)
        nbd_layout.setContentsMargins(16, 18, 16, 12)
        nbd_group.setLayout(nbd_layout)

        def _lbl(text):
            label = QLabel(text)
            label.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 12px; background: transparent"
            )
            return label

        nbd_layout.addWidget(_lbl("Min channels:"), 0, 0)
        self._min_channels_entry = QLineEdit()
        nbd_layout.addWidget(self._min_channels_entry, 0, 1)

        nbd_layout.addWidget(_lbl("Thresholding method:"), 1, 0)
        self._th_method_combo = QComboBox()
        self._th_method_combo.addItems(self._TH_METHODS)
        nbd_layout.addWidget(self._th_method_combo, 1, 1)

        nbd_layout.addWidget(_lbl("KDE bandwidth:"), 2, 0)
        self._nbd_kde_bw_entry = QLineEdit()
        nbd_layout.addWidget(self._nbd_kde_bw_entry, 2, 1)

        tab_layout.addWidget(nbd_group)

        action_bar = QFrame()
        action_bar.setObjectName("Card")
        bar_layout = QHBoxLayout(action_bar)
        bar_layout.setContentsMargins(16, 10, 16, 10)
        bar_layout.setSpacing(10)

        update_btn = make_primary_btn("▶  Update Plot")
        update_btn.setToolTip(
            "These settings are for visualisation purposes only, they will not affect "
            "the current analysis outcomes or further steps such as feature calculation."
        )
        update_btn.clicked.connect(self._update_nbd_plot)
        bar_layout.addWidget(update_btn)

        reset_btn = make_secondary_btn("↺  Reset")
        reset_btn.clicked.connect(self._reset_nbd)
        bar_layout.addWidget(reset_btn)
        bar_layout.addStretch()

        tab_layout.addWidget(action_bar)
        self.tabs.addTab(nbd_tab, "Network Burst Detection")

    def _build_activity_tab(self) -> None:
        activity_tab = QWidget()
        tab_layout = QVBoxLayout(activity_tab)
        tab_layout.setContentsMargins(16, 16, 16, 16)
        tab_layout.setSpacing(12)

        self._activity_plot_container = QFrame()
        self._activity_plot_container.setObjectName("Card")
        self._activity_plot_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._activity_plot_layout = QVBoxLayout(self._activity_plot_container)
        self._activity_plot_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_plot_layout.setSpacing(0)
        tab_layout.addWidget(self._activity_plot_container, stretch=1)

        tab_layout.addWidget(make_divider())

        act_group = QGroupBox("Well Activity Parameters")
        act_layout = QGridLayout()
        act_layout.setSpacing(8)
        act_layout.setContentsMargins(16, 18, 16, 12)
        act_group.setLayout(act_layout)

        bw_lbl = QLabel("KDE bandwidth:")
        bw_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; background: transparent"
        )
        act_layout.addWidget(bw_lbl, 0, 0)

        self._act_bw_entry = QLineEdit()
        act_layout.addWidget(self._act_bw_entry, 0, 1)

        tab_layout.addWidget(act_group)

        action_bar = QFrame()
        action_bar.setObjectName("Card")
        bar_layout = QHBoxLayout(action_bar)
        bar_layout.setContentsMargins(16, 10, 16, 10)
        bar_layout.setSpacing(10)

        update_btn = make_primary_btn("▶  Update Plot")
        update_btn.clicked.connect(self._update_activity_plot)
        bar_layout.addWidget(update_btn)

        reset_btn = make_secondary_btn("↺  Reset")
        reset_btn.clicked.connect(self._reset_activity)
        bar_layout.addWidget(reset_btn)
        bar_layout.addStretch()

        tab_layout.addWidget(action_bar)
        self.tabs.addTab(activity_tab, "Well Activity")

    def _default_nbd_values(self) -> None:
        p = self.parameters
        idx = self._th_method_combo.findText(p["thresholding method"])
        if idx >= 0:
            self._th_method_combo.setCurrentIndex(idx)
        _set_entry(self._min_channels_entry, p["min channels"])
        _set_entry(self._nbd_kde_bw_entry, p["nbd kde bandwidth"])

    def _reset_nbd(self) -> None:
        self._default_nbd_values()
        self._update_nbd_plot()

    def _update_nbd_plot(self) -> None:
        temp = copy.deepcopy(self.parameters)

        try:
            temp["min channels"] = _get_float(self._min_channels_entry)
            temp["thresholding method"] = self._th_method_combo.currentText()
            temp["nbd kde bandwidth"] = _get_float(self._nbd_kde_bw_entry)
        except Exception as e:
            _show_error(
                self,
                f"Parameter conversion failed. Ensure all fields contain valid numbers.\n\nError: {e}",
            )

        temp["output path"] = self.folder

        try:
            self._plot_network_bursts(temp)
        except Exception as e:
            _show_error(
                self,
                f"Something went wrong while creating the plot.\n\nError: {e}",
            )

    def _plot_network_bursts(self, parameters: dict) -> None:
        fig = network_burst_detection(
            wells=[self.well],
            parameters=parameters,
            plot_electrodes=True,
            savedata=False,
            save_figures=False,
        )
        self._apply_dark_theme(fig)
        self._replace_canvas(
            self._nbd_plot_layout, self._nbd_plot_container, fig, toolbar=True
        )

    def _reset_activity(self) -> None:
        _set_entry(self._act_bw_entry, self._DEFAULT_BW)
        self._update_activity_plot()

    def _update_activity_plot(self) -> None:
        try:
            self._plot_well_activity()
        except Exception as e:
            _show_error(
                self,
                f"Something went wrong while creating the plot.\n\nError: {e}",
            )

    def _plot_well_activity(self) -> None:
        fig = well_electrodes_kde(
            outputpath=self.folder,
            well=self.well,
            parameters=self.parameters,
            bandwidth=_get_float(self._act_bw_entry),
        )

        self._apply_dark_theme(fig, axis_colour="#586d97")
        self._replace_canvas(
            self._activity_plot_layout, self._activity_plot_container, fig, toolbar=True
        )

    @staticmethod
    def _apply_dark_theme(fig, axis_colour: str = None) -> None:
        bg = DARK_BG
        fg = axis_colour if axis_colour else TEXT_PRIMARY

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

    def _replace_canvas(self, layout, container, fig, toolbar: bool = False) -> None:
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
