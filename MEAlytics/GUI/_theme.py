from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy

# Default
DARK_BG = "#0f1117"
SURFACE_1 = "#161b27"
SURFACE_2 = "#1c2333"
SURFACE_3 = "#232b3e"
BORDER_COLOR = "#2a3450"
ACCENT = "#3d8ef0"
ACCENT_HOVER = "#5aa3f7"
ACCENT_MUTED = "#1e3a6e"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
DANGER = "#ef4444"
TEXT_PRIMARY = "#e8edf5"
TEXT_SECONDARY = "#9da5b4"
TEXT_MUTED = "#4a5568"

# Dark orange
# DARK_BG = "#0e0e0e"
# SURFACE_1 = "#161616"
# SURFACE_2 = "#1c1c1c"
# SURFACE_3 = "#222222"
# BORDER_COLOR = "#242424"
# ACCENT = "#ff4500"
# ACCENT_HOVER = "#ff8c00"
# ACCENT_MUTED = "#3a1a00"
# SUCCESS = "#39d353"
# WARNING = "#ffd60a"
# DANGER = "#ff2d55"
# TEXT_PRIMARY = "#f5f5f5"
# TEXT_SECONDARY= "#707070"
# TEXT_MUTED = "#333333"

# Light mode
# DARK_BG       = "#f0f2f5"
# SURFACE_1     = "#ffffff"
# SURFACE_2     = "#e8ecf2"
# SURFACE_3     = "#dce1eb"
# BORDER_COLOR  = "#c5cdd9"
# ACCENT        = "#2563eb"
# ACCENT_HOVER  = "#1d4ed8"
# ACCENT_MUTED  = "#dbeafe"
# SUCCESS       = "#16a34a"
# WARNING       = "#d97706"
# DANGER        = "#dc2626"
# TEXT_PRIMARY  = "#0f172a"
# TEXT_SECONDARY= "#475569"
# TEXT_MUTED    = "#94a3b8"

STYLESHEET = f"""
/* ── Global ── */
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "SF Pro Display", system-ui;
    font-size: 13px;
}}

/* ── Sidebar ── */
#Sidebar {{
    background-color: {SURFACE_1};
    border-right: 1px solid {BORDER_COLOR};
}}

#AppTitle {{
    color: {TEXT_PRIMARY};
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 1px;
}}

#AppSubtitle {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
}}

/* ── Sidebar nav buttons ── */
#NavBtn {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}}
#NavBtn:hover {{
    background-color: {SURFACE_3};
    color: {TEXT_PRIMARY};
}}
#NavBtn[active="true"] {{
    background-color: {ACCENT_MUTED};
    color: {ACCENT};
    border-left: 3px solid {ACCENT};
}}

/* ── Section dividers ── */
#SidebarSection {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 4px 16px;
    text-transform: uppercase;
}}

/* ── External link buttons ── */
#LinkBtn {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    text-align: left;
    font-size: 12px;
}}
#LinkBtn:hover {{
    color: {ACCENT};
    background-color: {SURFACE_2};
}}

/* ── Primary action button ── */
#PrimaryBtn {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 600;
}}
#PrimaryBtn:hover {{
    background-color: {ACCENT_HOVER};
}}
#PrimaryBtn:disabled {{
    background-color: {ACCENT_MUTED};
    color: {TEXT_MUTED};
}}

/* ── Secondary button ── */
#SecondaryBtn {{
    background-color: {SURFACE_3};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 500;
}}
#SecondaryBtn:hover {{
    background-color: {SURFACE_2};
    border-color: {ACCENT};
    color: {ACCENT};
}}

/* ── Danger button ── */
#DangerBtn {{
    background-color: transparent;
    color: {DANGER};
    border: 1px solid {DANGER};
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
}}
#DangerBtn:hover {{
    background-color: {DANGER};
    color: white;
}}

/* ── Cards ── */
#Card {{
    background-color: {SURFACE_1};
    border: 1px solid {BORDER_COLOR};
    border-radius: 12px;
}}
#CardHover {{
    background-color: {SURFACE_1};
    border: 1px solid {BORDER_COLOR};
    border-radius: 12px;
}}
#CardHover:hover {{
    border-color: {ACCENT};
    background-color: {SURFACE_2};
}}

/* ── File entry card ── */
#FileCard {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER_COLOR};
    border-radius: 10px;
}}

/* ── Drop zone ── */
#DropZone {{
    background-color: {SURFACE_1};
    border: 2px dashed {BORDER_COLOR};
    border-radius: 12px;
    color: {TEXT_MUTED};
}}
#DropZone:hover {{
    border-color: {ACCENT};
    background-color: {SURFACE_2};
    color: {ACCENT};
}}

/* ── Input fields ── */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER_COLOR};
    border-radius: 7px;
    padding: 7px 12px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER_COLOR};
    selection-background-color: {ACCENT};
    color: {TEXT_PRIMARY};
    border-radius: 8px;
}}

/* ── ScrollArea ── */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QAbstractScrollArea::corner {{ background: {DARK_BG}; border: none; }}

QScrollBar:vertical {{
    background: {DARK_BG};
    width: 6px;
    border-radius: 3px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_COLOR};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: {DARK_BG};
    height: 6px;
    border-radius: 3px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_COLOR};
    border-radius: 3px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

/* ── Progress bar ── */
QProgressBar {{
    background-color: {SURFACE_3};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {SUCCESS};
    border-radius: 4px;
}}

/* ── Console / log ── */
#Console {{
    background-color: {SURFACE_1};
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
    color: #a0c8ff;
    font-family: "Cascadia Code", "Fira Code", "Consolas", monospace;
    font-size: 12px;
    padding: 8px;
}}

/* ── GroupBox (used in parameters) ── */
QGroupBox {{
    background-color: {SURFACE_1};
    border: 1px solid {BORDER_COLOR};
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 6px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    color: {ACCENT};
    font-size: 12px;
    letter-spacing: 0.5px;
}}

/* ── CheckBox ── */
QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER_COLOR};
    background: {SURFACE_2};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Labels ── */
#PageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
#SectionLabel {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    letter-spacing: 1px;
    text-transform: uppercase;
}}
#MetaLabel {{
    background-color: {SURFACE_1};
    font-size: 12px;
    color: {TEXT_SECONDARY};
}}
#StatusBadge {{
    background-color: {ACCENT_MUTED};
    color: {ACCENT};
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}
#SuccessBadge {{
    background-color: #14532d;
    color: {SUCCESS};
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}
#WarningBadge {{
    background-color: #78350f;
    color: {WARNING};
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}
#Divider {{
    background-color: {BORDER_COLOR};
    max-height: 1px;
    min-height: 1px;
}}

/* ── Settings drawer ── */
#SettingsDrawer {{
    background-color: {SURFACE_1};
    border-right: 1px solid {BORDER_COLOR};
}}
QTabWidget::pane {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
    background-color: {SURFACE_1};
}}
QTabBar::tab {{
    background-color: {SURFACE_2};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_COLOR};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 8px 20px;
    margin-right: 2px;
    font-size: 13px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background-color: {SURFACE_1};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background-color: {SURFACE_3};
    color: {TEXT_PRIMARY};
}}
"""

TOOLBAR_STYLESHEET = f"""
QToolBar {{
    background-color: {SURFACE_2};
    border-top: 1px solid {BORDER_COLOR};
    border-bottom: none;
    border-left: none;
    border-right: none;
    spacing: 2px;
    padding: 2px 4px;
}}
QToolButton {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 3px;
}}
QToolButton:hover {{
    background-color: {SURFACE_3};
    border-color: {BORDER_COLOR};
}}
QToolButton:checked {{
    background-color: {ACCENT_MUTED};
    border-color: {ACCENT};
}}
QLabel {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {SURFACE_3};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    border: none;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
"""

_BTN_STYLE_DEFAULT = f"""
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
"""

_BTN_STYLE_SELECTED = f"""
    QPushButton {{
        background-color: {ACCENT_MUTED};
        color: {ACCENT};
        border: 2px solid {ACCENT};
        border-radius: 0px;
        font-size: 14px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        background-color: {ACCENT_MUTED};
        border-color: {ACCENT};
        color: {ACCENT};
    }}
"""

SIDEBAR_WIDTH = 220


# Helper functions
def make_label(text, object_name="", parent=None):
    lbl = QLabel(text, parent)
    if object_name:
        lbl.setObjectName(object_name)
    return lbl


def make_divider():
    d = QFrame()
    d.setObjectName("Divider")
    d.setFrameShape(QFrame.Shape.HLine)
    return d


def icon_text_btn(icon_char, label, object_name="NavBtn"):
    """Return a sidebar button with icon + text."""
    btn = QPushButton(f"  {icon_char}  {label}")
    btn.setObjectName(object_name)
    btn.setCheckable(False)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    btn.setMinimumHeight(40)
    return btn


def make_primary_btn(label: str, parent=None) -> QPushButton:
    btn = QPushButton(label, parent)
    btn.setObjectName("PrimaryBtn")
    btn.setMinimumHeight(38)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def make_secondary_btn(label: str, parent=None) -> QPushButton:
    btn = QPushButton(label, parent)
    btn.setObjectName("SecondaryBtn")
    btn.setMinimumHeight(38)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn
