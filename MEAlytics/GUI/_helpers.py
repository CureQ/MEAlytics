import math
import sys
import os

import numpy as np

from PyQt6.QtWidgets import QLineEdit

def _well_grid(num_items: int) -> tuple[int, int]:
    if num_items == 24:
        return 6, 4
    best = (num_items, 1)
    for w in range(1, int(math.sqrt(num_items)) + 1):
        if num_items % w == 0:
            h = num_items // w
            if abs(w - h) < abs(best[0] - best[1]):
                best = (w, h)
    cols, rows = max(best), min(best)
    return int(cols), int(rows)

def _electrode_grid(num_items: int) -> np.ndarray:
    if num_items == 12:
        return np.array([
            [False, True,  True,  False],
            [True,  True,  True,  True ],
            [True,  True,  True,  True ],
            [False, True,  True,  False],
        ])
    if num_items == 16:
        return np.ones((4, 4), dtype=bool)
    cols, rows = _well_grid(num_items)
    return np.ones((rows, cols), dtype=bool)

def _set_entry(line_edit: QLineEdit, value) -> None:
    line_edit.setText(str(value))

def _get_float(line_edit: QLineEdit) -> float:
    return float(line_edit.text())

def _get_int(line_edit: QLineEdit) -> int:
    return int(line_edit.text())

def _adjust_color(hex_color: str, factor: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f"#{min(255,int(r*factor)):02x}{min(255,int(g*factor)):02x}{min(255,int(b*factor)):02x}"

def resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)