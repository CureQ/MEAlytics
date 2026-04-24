"""
Python reader for Axion Biosystems .raw files.
Adapted from AxionFileLoader (MATLAB) by Axion Biosystems, Inc.
Original source: https://github.com/axionbio/AxionFileLoader
Original license: MIT
This file is licensed under the GNU General Public License v3.0.
"""

import os
import struct

import numpy as np


class AxionFile:
    SAMPLE_TYPES = {0: np.int16, 1: np.int32, 2: np.float32, 3: np.float64}

    def __init__(self, filepath):
        self.filepath = filepath
        self.datasets = []
        self.channel_array = []

        self._parse_file()

        ds = self._get_raw_voltage_dataset()
        if not ds:
            raise ValueError("Raw voltage dataset not found in this file.")

        self.sampling_rate = ds["samp_freq"]
        self.voltage_scale = ds["volt_scale"]

        dtype = self.SAMPLE_TYPES.get(ds["sample_type"], np.int16)
        itemsize = np.dtype(dtype).itemsize

        n_chans = ds["n_chans"]
        num_samples = ds["data_len"] // (n_chans * itemsize)

        self._data = np.memmap(
            self.filepath,
            dtype=dtype,
            mode="r",
            offset=ds["data_start"],
            shape=(num_samples, n_chans),
        ).T

        self.shape = self._data.shape
        self.type = self._data.dtype

        unique_wells = set(
            (ch["well_col"], ch["well_row"]) for ch in self.channel_array
        )
        self.num_wells = len(unique_wells)
        self.num_electrodes = n_chans // self.num_wells if self.num_wells > 0 else 0

        self.nbytes = self._data[: self.num_electrodes, :].nbytes

        self.num_well_cols = (
            max(ch["well_col"] for ch in self.channel_array)
            if self.channel_array
            else 0
        )
        self.num_elec_cols = (
            max(ch["elec_col"] for ch in self.channel_array)
            if self.channel_array
            else 0
        )

        self.num_elec_rows = (
            max(ch["elec_row"] for ch in self.channel_array)
            if self.channel_array
            else 0
        )

        self._channel_lookup = {
            (ch["well_col"], ch["well_row"], ch["elec_col"], ch["elec_row"]): idx
            for idx, ch in enumerate(self.channel_array)
        }

    def _parse_file(self):
        file_size = os.path.getsize(self.filepath)

        with open(self.filepath, "rb") as f:
            magic = f.read(8)
            if magic != b"AxionBio":
                raise ValueError(f"Not a valid Axion file. Magic found: {magic}")

            f.read(6)
            f.read(12)

            (entries_start,) = struct.unpack("<q", f.read(8))

            slots = [struct.unpack("<Q", f.read(8))[0] for _ in range(123)]
            f.seek(entries_start)

            terminated = False
            older_headers = {}

            while not terminated:
                for slot in slots:
                    type_id = (slot >> 56) & 0xFF
                    length = slot & 0x00FFFFFFFFFFFFFF

                    if type_id == 0:
                        terminated = True
                        break
                    if type_id == 255:
                        continue

                    pos = f.tell()
                    actual_length = (
                        length if length != 0x00FFFFFFFFFFFFFF else file_size - pos
                    )

                    if type_id == 2:
                        plate_type, n_chans = struct.unpack("<2I", f.read(8))
                        for _ in range(n_chans):
                            w_col, w_row, e_col, e_row, achk, idx, aux = struct.unpack(
                                "<6BH", f.read(8)
                            )
                            self.channel_array.append(
                                {
                                    "well_col": w_col,
                                    "well_row": w_row,
                                    "elec_col": e_col,
                                    "elec_row": e_row,
                                    "channel_achk": achk,
                                    "channel_idx": idx,
                                }
                            )

                    elif type_id == 3:
                        samp_freq, volt_scale = struct.unpack("<2d", f.read(16))
                        f.read(28)
                        first_block, n_chans, n_samples, b_hdr_size = struct.unpack(
                            "<q3I", f.read(20)
                        )
                        older_headers[first_block] = {
                            "samp_freq": samp_freq,
                            "volt_scale": volt_scale,
                            "n_chans": n_chans,
                            "data_type": 0,
                            "sample_type": 0,
                            "name": "Legacy Raw",
                        }

                    elif type_id == 4:
                        if pos in older_headers:
                            hdr = older_headers[pos]
                            self.datasets.append(
                                {
                                    "data_start": pos,
                                    "data_len": actual_length,
                                    "samp_freq": hdr["samp_freq"],
                                    "volt_scale": hdr["volt_scale"],
                                    "n_chans": hdr["n_chans"],
                                    "data_type": hdr["data_type"],
                                    "sample_type": hdr["sample_type"],
                                    "name": hdr["name"],
                                }
                            )

                    elif type_id == 7:
                        (
                            v_maj,
                            v_min,
                            data_type,
                            sample_type,
                            samp_freq,
                            volt_scale,
                            n_chans,
                            n_datasets,
                            n_samples,
                            v_hdr_size,
                            b_hdr_size,
                        ) = struct.unpack("<4H2d5I", f.read(44))

                        f.read(56)

                        if v_maj > 1 or (v_maj == 1 and v_min >= 1):
                            f.read(8)

                        (name_len,) = struct.unpack("<i", f.read(4))
                        name = f.read(name_len).decode("utf-8", errors="ignore")

                        (desc_len,) = struct.unpack("<i", f.read(4))
                        desc = f.read(desc_len).decode("utf-8", errors="ignore")

                        data_start, data_len = struct.unpack("<2q", f.read(16))

                        self.datasets.append(
                            {
                                "data_start": data_start,
                                "data_len": data_len,
                                "samp_freq": samp_freq,
                                "volt_scale": volt_scale,
                                "n_chans": n_chans,
                                "data_type": data_type,
                                "sample_type": sample_type,
                                "name": name,
                            }
                        )

                    f.seek(pos + actual_length)

                if not terminated:
                    magic = f.read(8)
                    if magic != b"AxionBio":
                        raise ValueError("Bad sub-header magic sequence encountered.")
                    slots = [struct.unpack("<Q", f.read(8))[0] for _ in range(126)]
                    f.seek(8, 1)

    def _get_raw_voltage_dataset(self):
        for ds in self.datasets:
            dt = ds["data_type"]
            name = ds["name"]
            if dt == 0 or (dt == 2 and "Voltage" in name):
                return ds
        return None

    def get_voltage_trace(self, well_index, electrode_index=None, apply_scale=False):
        """
        Retrieve the raw voltage trace.
        If electrode_index is not specified, returns the raw traces of the entire well
        as shape (electrodes, measurements).

        NOTE: This function uses 1-based indexing
        """
        well_idx_0 = well_index - 1

        # Wells map top left to bottom right
        well_row = (well_idx_0 // self.num_well_cols) + 1
        well_col = (well_idx_0 % self.num_well_cols) + 1

        if electrode_index is None:
            indices = []
            for e_idx in range(self.num_electrodes):
                # Electrode columns are left to right
                elec_col = (e_idx % self.num_elec_cols) + 1

                # Electrode rows are bottom to top - matching the AxIS Navigator GUI
                gui_row_0 = e_idx // self.num_elec_cols
                elec_row = self.num_elec_rows - gui_row_0

                idx = self._channel_lookup.get((well_col, well_row, elec_col, elec_row))
                if idx is None:
                    raise ValueError(
                        f"Electrode {e_idx + 1} not found in Well {well_index}."
                    )
                indices.append(idx)

            trace = self._data[indices, :]

        else:
            e_idx_0 = electrode_index - 1
            elec_col = (e_idx_0 % self.num_elec_cols) + 1

            gui_row_0 = e_idx_0 // self.num_elec_cols
            elec_row = self.num_elec_rows - gui_row_0

            idx = self._channel_lookup.get((well_col, well_row, elec_col, elec_row))
            if idx is None:
                raise ValueError(
                    f"Trace for Well {well_index}, Electrode {electrode_index} not found."
                )

            trace = self._data[idx, :]

        if apply_scale:
            return trace * self.voltage_scale
        return trace
