import os
import sys
import json
import webbrowser
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QFileDialog,
    QProgressBar, QTextEdit, QScrollArea, QSizePolicy, QSpacerItem,
    QMessageBox, QLineEdit, QGridLayout, QSplitter
)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette, QFontDatabase, QPixmap, QPainter, QBrush

# Core Imports
from MEAlytics.mea import get_default_parameters, AnalysisWorker

# GUI Imports
from MEAlytics.GUI._parameters import ParameterFrame
from MEAlytics.GUI._theme import STYLESHEET, DARK_BG, SURFACE_1, SURFACE_2, SURFACE_3, BORDER_COLOR, ACCENT, ACCENT_HOVER, ACCENT_MUTED, SUCCESS, WARNING, DANGER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, SIDEBAR_WIDTH
from MEAlytics.GUI._theme import make_label, make_divider, icon_text_btn


# Main window classes
class DropZone(QFrame):
    """Drag-and-drop target that also allows browsing"""
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(130)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        hint = QLabel("Drop HDF5 files here  ·  or")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent; border: none; font-size: 13px;")
        layout.addWidget(hint)

        browse = QPushButton("Browse Files")
        browse.setObjectName("SecondaryBtn")
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.setFixedWidth(140)
        browse.clicked.connect(self.browse)
        layout.addWidget(browse, alignment=Qt.AlignmentFlag.AlignCenter)

    def browse(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select HDF5 Files", "", "HDF5 Files (*.h5 *.hdf5);;All Files (*)"
        )
        if paths:
            self.files_dropped.emit(paths)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile().endswith(('.h5', '.hdf5'))]
        if paths:
            self.files_dropped.emit(paths)


class FileJobCard(QFrame):
    """A single file analysis job card with live progress"""

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.setObjectName("FileCard")
        self.filepath = filepath
        self.filename = Path(filepath).name

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)

        # Filename
        row1 = QHBoxLayout()
        name_lbl = QLabel(self.filename)
        name_lbl.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {TEXT_PRIMARY}; background: transparent")
        row1.addWidget(name_lbl)
        row1.addStretch()

        self.status_badge = QLabel("Queued")
        self.status_badge.setObjectName("StatusBadge")
        self.status_badge.setStyleSheet(f"background: {SURFACE_2}")
        row1.addWidget(self.status_badge)
        outer.addLayout(row1)

        # File path
        path_lbl = QLabel(str(Path(filepath).parent))
        path_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; background: transparent")
        outer.addWidget(path_lbl)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        outer.addWidget(self.progress)

        # Console log
        self.console = QTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setFixedHeight(90)
        self.console.setVisible(False)
        outer.addWidget(self.console)

        # Action buttons
        btn_row = QHBoxLayout()
        self.toggle_log_btn = QPushButton("Show Log")
        self.toggle_log_btn.setObjectName("SecondaryBtn")
        self.toggle_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_log_btn.clicked.connect(self.toggle_log)

        self.view_results_btn = QPushButton("View Results  →")
        self.view_results_btn.setObjectName("PrimaryBtn")
        self.view_results_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_results_btn.setEnabled(False)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("DangerBtn")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setVisible(False)   # only shown while running

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setObjectName("DangerBtn")
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_row.addWidget(self.toggle_log_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.view_results_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.remove_btn)
        outer.addLayout(btn_row)

    def toggle_log(self):
        visible = self.console.isVisible()
        self.console.setVisible(not visible)
        self.toggle_log_btn.setText("Hide Log" if not visible else "Show Log")

    def log(self, message: str):
        self.console.append(message)

    def set_running(self):
        self.status_badge.setText("Running")
        self.status_badge.setObjectName("StatusBadge")
        self.status_badge.setStyle(self.status_badge.style())
        self.cancel_btn.setVisible(True)
        self.remove_btn.setVisible(False)

    def set_complete(self):
        self.progress.setValue(100)
        self.status_badge.setText("Complete")
        self.status_badge.setObjectName("SuccessBadge")
        self.status_badge.setStyle(self.status_badge.style())
        self.cancel_btn.setVisible(False)
        self.remove_btn.setVisible(True)
        self.view_results_btn.setEnabled(True)

    def set_failed(self, aborted: bool = False):
        self.status_badge.setText("Cancelled" if aborted else "Failed")
        self.status_badge.setObjectName("DangerBadge")
        self.status_badge.setStyle(self.status_badge.style())
        self.cancel_btn.setVisible(False)
        self.remove_btn.setVisible(True)

class WorkbenchView(QWidget):

    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.job_cards: list[FileJobCard] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(32, 28, 32, 28)
        content_layout.setSpacing(20)

        header_row = QHBoxLayout()
        title = make_label("Workbench", "PageTitle")
        header_row.addWidget(title)
        header_row.addStretch()

        self.start_btn = QPushButton("▶  Start Analysis")
        self.start_btn.setObjectName("PrimaryBtn")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setMinimumWidth(160)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_analysis)
        self.cancel_all_btn = QPushButton("✕  Remove All")
        self.cancel_all_btn.setObjectName("DangerBtn")
        self.cancel_all_btn.setMinimumHeight(40)
        self.cancel_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_all_btn.clicked.connect(self._cancel_all)
        header_row.addWidget(self.cancel_all_btn)
        header_row.addWidget(self.start_btn)
        content_layout.addLayout(header_row)

        # Critical parameters card
        params_card = QFrame()
        params_card.setObjectName("Card")
        params_card_layout = QVBoxLayout(params_card)
        params_card_layout.setContentsMargins(20, 16, 20, 16)
        params_card_layout.setSpacing(12)

        cp_header = QHBoxLayout()
        cp_title = make_label("Required Parameters", "SectionLabel")
        cp_header.addWidget(cp_title)
        cp_header.addStretch()

        self.params_status = QLabel("Required before analysis")
        self.params_status.setObjectName("WarningBadge")
        cp_header.addWidget(self.params_status)
        params_card_layout.addLayout(cp_header)

        fields_row = QHBoxLayout()
        fields_row.setSpacing(24)

        # Electrodes per well
        e_col = QVBoxLayout()
        e_col.setSpacing(4)
        e_col.addWidget(make_label("Electrodes per Well", "MetaLabel"))
        self.electrodes_input = QLineEdit()
        self.electrodes_input.setPlaceholderText("e.g.  12")
        self.electrodes_input.setFixedWidth(140)
        self.electrodes_input.textChanged.connect(self._check_critical_params)
        e_col.addWidget(self.electrodes_input)
        fields_row.addLayout(e_col)

        # Measuring frequency
        f_col = QVBoxLayout()
        f_col.setSpacing(4)
        f_col.addWidget(make_label("Measuring Frequency (Hz)", "MetaLabel"))
        self.frequency_input = QLineEdit()
        self.frequency_input.setPlaceholderText("e.g.  20000")
        self.frequency_input.setFixedWidth(160)
        self.frequency_input.textChanged.connect(self._check_critical_params)
        f_col.addWidget(self.frequency_input)
        fields_row.addLayout(f_col)

        fields_row.addStretch()
        params_card_layout.addLayout(fields_row)
        content_layout.addWidget(params_card)

        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self.add_files)
        content_layout.addWidget(self.drop_zone)

        # Scrollable job list
        self.jobs_scroll = QScrollArea()
        self.jobs_scroll.setWidgetResizable(True)
        self.jobs_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.jobs_container = QWidget()
        self.jobs_layout = QVBoxLayout(self.jobs_container)
        self.jobs_layout.setContentsMargins(0, 0, 0, 0)
        self.jobs_layout.setSpacing(10)
        self.jobs_layout.addStretch()

        self.jobs_scroll.setWidget(self.jobs_container)
        content_layout.addWidget(self.jobs_scroll, 1)

        root.addWidget(content_widget, 1)
        self._init_queue()
        self._check_critical_params()

    def _check_critical_params(self):
        e = self.electrodes_input.text().strip()
        f = self.frequency_input.text().strip()
        ok = e.isdigit() and f.isdigit()
        self.start_btn.setEnabled(ok and len(self.job_cards) > 0)
        if ok:
            self.params_status.setText("Parameters set")
            self.params_status.setObjectName("SuccessBadge")
        else:
            self.params_status.setText("Required before analysis")
            self.params_status.setObjectName("WarningBadge")
        self.params_status.setStyle(self.params_status.style())

    def _init_queue(self):
        """Call once from __init__ after building the UI."""
        self._queue: list[FileJobCard] = []   # cards waiting to run
        self._active_card: FileJobCard | None = None
        self._active_worker: AnalysisWorker | None = None
        self._active_thread: QThread | None = None

    # File management
    def add_files(self, paths: list):
        existing = {c.filepath for c in self.job_cards}
        for path in paths:
            if path not in existing:
                card = FileJobCard(path)
                card.remove_btn.clicked.connect(lambda _, c=card: self.remove_card(c))
                card.cancel_btn.clicked.connect(lambda _, c=card: self._cancel_card(c))
                self.jobs_layout.insertWidget(self.jobs_layout.count() - 1, card)
                self.job_cards.append(card)
                self._queue.append(card)
        self._check_critical_params()

    def remove_card(self, card: FileJobCard):
        """Remove a queued or finished card."""
        if card is self._active_card:
            self._cancel_card(card)
            return
        if card in self._queue:
            self._queue.remove(card)
        self.jobs_layout.removeWidget(card)
        card.deleteLater()
        self.job_cards.remove(card)
        self._check_critical_params()

    def _cancel_card(self, card: FileJobCard):
        """Cancel the currently running job."""
        if card is self._active_card and self._active_worker is not None:
            self._active_worker.request_stop()
            card.log("Cancellation requested…")

    # Analysis queue
    def start_analysis(self):
        e = int(self.electrodes_input.text().strip())
        f = int(self.frequency_input.text().strip())

        self._queue = [c for c in self.job_cards if c.status_badge.text() == "Queued"]

        if not self._queue:
            return

        self.start_btn.setEnabled(False)
        self._run_next(e, f)

    def _run_next(self, electrodes: int, frequency: int):
        if not self._queue:
            self._check_critical_params()
            return

        card = self._queue.pop(0)
        self._active_card = card
        card.set_running()

        params = dict(self.app_state.parameters)

        worker = AnalysisWorker(
            filepath       = card.filepath,
            sampling_rate  = frequency,
            electrode_amnt = electrodes,
            parameters     = params,
        )
        thread = QThread(self)

        worker.moveToThread(thread)

        # Wire signals
        thread.started.connect(worker.run)
        worker.log_message.connect(card.log)
        worker.progress_updated.connect(
            lambda cur, tot, c=card: c.progress.setValue(int(cur / tot * 100)) if tot > 0 else None
        )
        worker.finished.connect(lambda success, c=card, e=electrodes, f=frequency:
                                self._on_job_finished(c, success, e, f))

        # Clean up thread after worker is done
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._active_worker = worker
        self._active_thread = thread
        thread.start()

    def _on_job_finished(self, card: FileJobCard, success: bool, electrodes: int, frequency: int):
        if success:
            card.set_complete()
        else:
            card.set_failed(aborted=not success)

        self._active_card   = None
        self._active_worker = None
        self._active_thread = None

        self._run_next(electrodes, frequency)

    def _cancel_all(self):
        if self._active_worker is not None:
            self._active_worker.request_stop()

        self._queue.clear()

        for card in list(self.job_cards):
            if card is not self._active_card:
                self.jobs_layout.removeWidget(card)
                card.deleteLater()
                self.job_cards.remove(card)

        self._check_critical_params()

# View Results
class ObservatoryView(QWidget):
    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        layout.addWidget(make_label("View Results", "PageTitle"))
        layout.addWidget(make_divider())

        load_card = QFrame()
        load_card.setObjectName("Card")
        load_layout = QVBoxLayout(load_card)
        load_layout.setContentsMargins(28, 24, 28, 24)
        load_layout.setSpacing(12)

        load_layout.addWidget(make_label("Load Analysis Output", "SectionLabel"))
        desc = QLabel(
            "Select the output folder generated by the analysis to explore results.\n"
            "Wells and electrode drill-down open in interactive windows."
        )
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; background-color: {SURFACE_1};")
        desc.setWordWrap(True)
        load_layout.addWidget(desc)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton("Select Output Folder")
        browse_btn.setObjectName("PrimaryBtn")
        browse_btn.setMinimumHeight(40)
        browse_btn.setMinimumWidth(220)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(browse_btn)
        btn_row.addStretch()
        load_layout.addLayout(btn_row)

        layout.addWidget(load_card)
        layout.addStretch()

# Utilities
class UtilitiesView(QWidget):
    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        layout.addWidget(make_label("Utilities", "PageTitle"))
        layout.addWidget(make_divider())

        cards_grid = QGridLayout()
        cards_grid.setSpacing(16)

        utilities = [
            ("Plotting",
             "Extract output features from multiple experiments and visualise changes over time.",
             "Open Plotting"),
            ("Rechunk / Compress",
             "Rechunk and compress HDF5 files for faster access and reduced storage.",
             "Open Tool"),
            ("Exclude Electrodes",
             "Exclude specific electrodes and re-run only the feature extraction step.",
             "Open Tool"),
        ]

        for i, (title, desc, btn_label) in enumerate(utilities):
            card = QFrame()
            card.setObjectName("Card")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(22, 20, 22, 20)
            cl.setSpacing(10)

            t = QLabel(title)
            t.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {TEXT_PRIMARY}; background-color: {SURFACE_1};")
            cl.addWidget(t)

            d = QLabel(desc)
            d.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; background-color: {SURFACE_1};")
            d.setWordWrap(True)
            cl.addWidget(d)
            cl.addStretch()

            btn = QPushButton(btn_label)
            btn.setObjectName("SecondaryBtn")
            btn.setMinimumHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cl.addWidget(btn)

            cards_grid.addWidget(card, 0, i)

        layout.addLayout(cards_grid)
        layout.addStretch()


# Sidebar
class Sidebar(QFrame):
    nav_requested = pyqtSignal(str)
    settings_requested = pyqtSignal()

    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.app_state = app_state
        self._active_page = "workbench"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(2)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)

        basedir = os.path.dirname(__file__)
        logo_path = os.path.join(basedir, "MEAlytics_logo.png")
        logo_icon = QLabel()
        logo_icon.setStyleSheet(f"background-color: {SURFACE_1};")
        pixmap = QPixmap(logo_path)
        scaled_pixmap = pixmap.scaledToHeight(30, Qt.TransformationMode.SmoothTransformation)
        logo_icon.setPixmap(scaled_pixmap)
        logo_row.addWidget(logo_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_label = make_label("MEAlytics", "AppTitle")
        title_label.setStyleSheet(f"background-color: {SURFACE_1};")
        title_col.addWidget(title_label)
        logo_row.addLayout(title_col)
        logo_row.addStretch()
        layout.addLayout(logo_row)

        layout.addSpacing(20)
        layout.addWidget(make_divider())
        layout.addSpacing(10)

        layout.addWidget(make_label("ANALYSIS", "SidebarSection"))
        layout.addSpacing(4)

        self.nav_btns: dict[str, QPushButton] = {}

        nav_items = [
            ("workbench", "", "Workbench"),
            ("observatory", "", "Observatory"),
        ]
        for page_id, icon, label in nav_items:
            btn = icon_text_btn(icon, label, "NavBtn")
            btn.clicked.connect(lambda _, pid=page_id: self._on_nav(pid))
            layout.addWidget(btn)
            self.nav_btns[page_id] = btn

        layout.addSpacing(12)
        layout.addWidget(make_label("TOOLS", "SidebarSection"))
        layout.addSpacing(4)

        util_btn = icon_text_btn("", "Utilities", "NavBtn")
        util_btn.clicked.connect(lambda: self._on_nav("utilities"))
        layout.addWidget(util_btn)
        self.nav_btns["utilities"] = util_btn

        layout.addSpacing(12)
        layout.addWidget(make_divider())
        layout.addSpacing(8)
        layout.addWidget(make_label("CONFIGURATION", "SidebarSection"))
        layout.addSpacing(4)

        params_btn = icon_text_btn("", "Parameters", "NavBtn")
        params_btn.clicked.connect(lambda: self._on_nav("parameters"))
        layout.addWidget(params_btn)
        self.nav_btns["parameters"] = params_btn

        layout.addStretch()

        # External links
        layout.addWidget(make_divider())
        layout.addSpacing(6)

        links = [
            ("CureQ Project", "https://cureq.nl/"),
            ("PyPI",          "https://pypi.org/project/MEAlytics/"),
            ("GitHub",        "https://github.com/CureQ/MEAlytics"),
            ("User Guide",    "https://cureq.github.io/MEAlytics/"),
        ]
        for text, url in links:
            btn = QPushButton(text)
            btn.setObjectName("LinkBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, u=url: webbrowser.open(u))
            layout.addWidget(btn)

        # Set initial active
        self._set_active("workbench")

    def _on_nav(self, page_id: str):
        self._set_active(page_id)
        self.nav_requested.emit(page_id)

    def _set_active(self, page_id: str):
        self._active_page = page_id
        for pid, btn in self.nav_btns.items():
            btn.setProperty("active", pid == page_id)
            btn.setStyle(btn.style())


# App state
class AppState:
    """Holds global mutable state shared across views."""
    def __init__(self):
        self.parameters = get_default_parameters()
        self.default_parameters = get_default_parameters()


# Main Window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MEAlytics")
        self.resize(1200, 760)
        self.setMinimumSize(900, 600)

        self.app_state = AppState()

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(self.app_state)
        self.sidebar.nav_requested.connect(self.switch_page)
        root_layout.addWidget(self.sidebar)

        # Page stack
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)

        # Build pages
        self.workbench = WorkbenchView(self.app_state)
        self.observatory = ObservatoryView(self.app_state)
        self.utilities = UtilitiesView(self.app_state)

        self.stack.addWidget(self.workbench)
        self.stack.addWidget(self.observatory)
        self.stack.addWidget(self.utilities)

        self.parameters_page = ParameterFrame(self)
        self.home_frame_class = "workbench"

        self.stack.addWidget(self.parameters_page)

        self._page_index = {
            "workbench":   0,
            "observatory": 1,
            "utilities":   2,
            "parameters":  3,
        }

        self.stack.setCurrentIndex(0)

    def show_frame(self, target):
        if target == "workbench" or target == self.home_frame_class:
            self.switch_page("workbench")

    def switch_page(self, page_id: str):
        idx = self._page_index.get(page_id, 0)
        self.stack.setCurrentIndex(idx)
        self.sidebar._set_active(page_id)

# Entry point
def MEA_GUI():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    MEA_GUI()