import h5py
import numpy as np

from MEAlytics.core._utilities import rechunk_dataset


class MCSFile:
    def __init__(self, filepath):
        self.filepath = filepath
        self.DATA_PATH = "Data/Recording_0/AnalogStream/Stream_0/ChannelData"
        self.INFO_PATH = "Data/Recording_0/AnalogStream/Stream_0/InfoChannel"

        with h5py.File(self.filepath, "r") as hdf_file:
            # Check if we need to rechunk the data. Rechunking the data allows us to
            # read 1 electrode at a time, instead of having to read the entire dataset
            # at once
            rechunk_data = False
            dataset_chunks = hdf_file[self.DATA_PATH].chunks

            # Check if dataset_chunks is not None
            if dataset_chunks:
                if dataset_chunks[0] != 1:
                    rechunk_data = True
                else:
                    rechunk_data = False
            else:
                rechunk_data = True

            if rechunk_data:
                print(
                    "Data is not correctly chunked yet.\nRechunking the data will allow the tool to quickly analyze large files on limited amount of RAM"
                )
                self.filepath = rechunk_dataset(
                    fileadress=self.filepath, compression_method="lzf"
                )

        with h5py.File(self.filepath, "r") as hdf_file:
            channeldata = hdf_file[self.DATA_PATH]

            infochannel = hdf_file[self.INFO_PATH]
            self.sampling_rate = 1000000 / infochannel[0][9]

            groupIDs = []
            for row in infochannel[:][:]:
                groupIDs.append(row[2])

            self.shape = channeldata.shape
            self.num_wells = len(np.unique(groupIDs))
            self.num_electrodes = int(self.shape[0] / self.num_wells)
            self.nbytes = channeldata[: self.num_electrodes].nbytes
            self.type = channeldata.dtype

    def get_voltage_trace(self, well_index, electrode_index=None):
        """Retrieve the raw voltage trace of a single electrode
        If electrode_index is not specified, returns the raw traces of the entire well
        NOTE: This function uses 1-based indexing"""
        with h5py.File(self.filepath, "r") as hdf_file:
            data = hdf_file[self.DATA_PATH]

            well_start = (well_index - 1) * self.num_electrodes

            if electrode_index is None:
                well_end = well_start + self.num_electrodes
                voltage_trace = data[well_start:well_end, :]
            else:
                elec_idx = well_start + (electrode_index - 1)
                voltage_trace = data[elec_idx, :]

        return voltage_trace
