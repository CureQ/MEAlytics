import json
import traceback

# PyQt Imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox, QPushButton, QFrame,
    QScrollArea, QGroupBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

class ParameterFrame(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.inputs: dict[str, QLineEdit] = {}

        self._build_ui()
        self.load_parameters(self.parent.app_state.parameters)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)

        header_row = QHBoxLayout()
        title = QLabel("Analysis Parameters")
        title.setObjectName("PageTitle")
        header_row.addWidget(title)
        header_row.addStretch()

        root.addLayout(header_row)

        subtitle = QLabel(
            "These parameters control every stage of the analysis pipeline. Default values should work well for most recordings."
        )
        subtitle.setStyleSheet("background: transparent")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("MetaLabel")
        root.addWidget(subtitle)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(divider)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self.grid = QGridLayout(container) 
        self.grid.setSpacing(16)
        self.grid.setContentsMargins(0, 4, 8, 4)

        self._populate_grid()

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        bar = QFrame()
        bar.setObjectName("Card")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 12, 16, 12)
        bar_layout.setSpacing(10)

        save_btn = QPushButton("✓  Save and Return")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setMinimumHeight(38)
        save_btn.setMinimumWidth(160)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.save_parameters)

        import_btn = QPushButton("Import Parameters")
        import_btn.setObjectName("SecondaryBtn")
        import_btn.setMinimumHeight(38)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self.import_parameters)

        reset_btn = QPushButton("↺  Restore Defaults")
        reset_btn.setObjectName("SecondaryBtn")
        reset_btn.setMinimumHeight(38)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def _reset():
            self.load_parameters(self.parent.app_state.default_parameters)

        reset_btn.clicked.connect(_reset)

        bar_layout.addWidget(save_btn)
        bar_layout.addWidget(import_btn)
        bar_layout.addWidget(reset_btn)
        bar_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("DangerBtn")
        cancel_btn.setMinimumHeight(38)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(lambda: self.parent.show_frame("start_analysis"))
        bar_layout.addWidget(cancel_btn)

        root.addWidget(bar)

    def _populate_grid(self):
        # Filter
        f_group = self._make_group("Filter Parameters")
        self._add_input(f_group, "Low cutoff (Hz):", "low cutoff", 1, "e.g. 200", "Low-pass cutoff in Hz")
        self._add_input(f_group, "High cutoff (Hz):", "high cutoff", 2, "e.g. 3500", "High-pass cutoff in Hz")
        self._add_input(f_group, "Filter order:", "order", 3, "e.g. 2", "Butterworth filter order")
        self.grid.addWidget(f_group, 0, 0)

        # Spike Detection
        s_group = self._make_group("Spike Detection")
        self._add_input(s_group, "Threshold portion:", "threshold portion", 1, "0–1", "Fraction of recording used for threshold estimation")
        self._add_input(s_group, "Std Dev multiplier:", "standard deviation multiplier", 2, "e.g. 5.0")
        self._add_input(s_group, "RMS multiplier:", "rms multiplier", 3, "e.g. 5.0")
        self._add_input(s_group, "Refractory period (s):", "refractory period", 4, "e.g. 0.001")

        s_group.layout().addWidget(self._field_label("Validation method:"), 5, 0)
        self.val_method = QComboBox()
        self.val_method.addItems(["Noisebased", "none"])
        self.val_method.currentTextChanged.connect(self._toggle_validation_fields)
        s_group.layout().addWidget(self.val_method, 5, 1)

        self._add_input(s_group, "Exit time:", "exit time", 6)
        self._add_input(s_group, "Drop amplitude:", "drop amplitude", 7)
        self._add_input(s_group, "Max drop:", "max drop", 8)
        self.grid.addWidget(s_group, 0, 1, 2, 1)

        # Burst Detection
        b_group = self._make_group("Burst Detection")
        self._add_input(b_group, "Min spikes:", "minimal amount of spikes", 1)
        self._add_input(b_group, "Default interval (ms):", "default interval threshold", 2)
        self._add_input(b_group, "Max interval (ms):", "max interval threshold", 3)
        self._add_input(b_group, "ISI KDE bandwidth:", "burst detection kde bandwidth", 4)
        self.grid.addWidget(b_group, 0, 2)

        # Network Burst Detection
        n_group = self._make_group("Network Burst")
        self._add_input(n_group, "Min channels (0–1):", "min channels", 1)
        n_group.layout().addWidget(self._field_label("Threshold method:"), 2, 0)
        self.nw_method = QComboBox()
        self.nw_method.addItems(["Yen", "Otsu", "Li", "Isodata", "Mean", "Minimum", "Triangle"])
        n_group.layout().addWidget(self.nw_method, 2, 1)
        self._add_input(n_group, "NBD KDE bandwidth:", "nbd kde bandwidth", 3)
        self.grid.addWidget(n_group, 1, 2)

        # Other 
        o_group = self._make_group("Other")
        self.multi_check = QCheckBox("Use multiprocessing")
        self.multi_check.setStyleSheet("background: transparent")
        o_group.layout().addWidget(self.multi_check, 1, 0, 1, 2)

        o_group.layout().addWidget(self._field_label("Synchronicity method:"), 2, 0)
        self.sync_method = QComboBox()
        self.sync_method.addItems(["ISI-distance", "Adaptive ISI-distance", "SPIKE-distance", "Adaptive SPIKE-distance"])
        o_group.layout().addWidget(self.sync_method, 2, 1)

        self.remove_inactive = QCheckBox("Remove inactive electrodes")
        self.remove_inactive.toggled.connect(
            lambda checked: self.inputs["activity threshold"].setEnabled(checked)
        )
        self.remove_inactive.setStyleSheet("background: transparent")
        o_group.layout().addWidget(self.remove_inactive, 3, 0, 1, 2)
        self._add_input(o_group, "Activity threshold (Hz):", "activity threshold", 4)
        self.grid.addWidget(o_group, 1, 0)

    def _make_group(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        layout.setSpacing(8)
        g.setLayout(layout)
        return g

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #8b95a8; font-size: 12px; background: transparent")
        return lbl

    def _add_input(self, group: QGroupBox, label_text: str, key: str,
                   row: int, placeholder: str = "", tooltip: str = ""):
        lbl = self._field_label(label_text)
        entry = QLineEdit()
        entry.setPlaceholderText(placeholder)
        if tooltip:
            lbl.setToolTip(tooltip)
            entry.setToolTip(tooltip)
        group.layout().addWidget(lbl, row, 0)
        group.layout().addWidget(entry, row, 1)
        self.inputs[key] = entry

    def _toggle_validation_fields(self, choice: str):
        is_noise = (choice == "Noisebased")
        for k in ("exit time", "drop amplitude", "max drop"):
            self.inputs[k].setEnabled(is_noise)

    def load_parameters(self, params: dict):
        """
        Populate all widgets from a parameter dictionary.
        """
        # Text inputs
        for key, widget in self.inputs.items():
            if key in params:
                widget.setText(str(params[key]))

        # ComboBoxes
        if "spike validation method" in params:
            self.val_method.setCurrentText(params["spike validation method"])
        if "thresholding method" in params:
            self.nw_method.setCurrentText(params["thresholding method"])
        if "synchronicity method" in params:
            self.sync_method.setCurrentText(params["synchronicity method"])

        # CheckBoxes
        if "use multiprocessing" in params:
            self.multi_check.setChecked(bool(params["use multiprocessing"]))
        if "remove inactive electrodes" in params:
            self.remove_inactive.setChecked(bool(params["remove inactive electrodes"]))

        self._toggle_validation_fields(self.val_method.currentText())

    def import_parameters(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Parameter File", "", "JSON Files (*.json)"
        )
        if path:
            with open(path, "r") as f:
                data = json.load(f)
            self.load_parameters(data)

    def save_parameters(self):
        try:
            p = self.parent.app_state.parameters

            # Integers
            for key in ("low cutoff", "high cutoff", "order", "minimal amount of spikes"):
                p[key] = int(float(self.inputs[key].text()))

            # Floats
            for key in (
                "refractory period", "exit time", "burst detection kde bandwidth",
                "max interval threshold", "default interval threshold",
                "max drop", "drop amplitude", "standard deviation multiplier",
                "rms multiplier", "min channels", "nbd kde bandwidth",
                "activity threshold", "threshold portion",
            ):
                p[key] = float(self.inputs[key].text())

            # Other
            p["thresholding method"]      = self.nw_method.currentText()
            p["spike validation method"]  = self.val_method.currentText()
            p["synchronicity method"]     = self.sync_method.currentText()
            p["remove inactive electrodes"] = self.remove_inactive.isChecked()
            p["use multiprocessing"]      = self.multi_check.isChecked()

            self.parent.show_frame("start_analysis")

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(
                self, "Validation Error",
                f"Parameter conversion failed. Ensure all fields contain valid numbers.\n\nError: {e}"
            )