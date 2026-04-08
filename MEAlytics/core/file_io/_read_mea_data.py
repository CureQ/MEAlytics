from pathlib import Path

from MEAlytics.core.file_io._read_axion_raw import AxionFile
from MEAlytics.core.file_io._read_mcs_h5 import MCSFile


def get_mea_file_reader(filepath: str):
    if filepath.endswith(".h5"):
        return MCSFile(filepath)
    elif filepath.endswith(".raw"):
        return AxionFile(filepath)
    else:
        raise ValueError(
            f"Filetype '{Path(filepath).suffix}' not supported in MEAlytics"
        )
