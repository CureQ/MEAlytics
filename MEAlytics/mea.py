# Imports
import copy
import datetime
import gc
import json
import multiprocessing
import os
import sys
import threading
import time
from importlib.metadata import version
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path

import h5py

# External libraries
import numpy as np
import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal

# Package imorts
from MEAlytics.core._bandpass import butter_bandpass_filter
from MEAlytics.core._burst_detection import burst_detection
from MEAlytics.core._features import (
    electrode_features,
    electrode_pair_features,
    feature_output,
    well_features,
)
from MEAlytics.core._network_burst_detection import network_burst_detection
from MEAlytics.core._spike_validation import spike_validation
from MEAlytics.core._threshold import fast_threshold
from MEAlytics.core.file_io._read_mea_data import get_mea_file_reader


def get_default_parameters():
    """
    Store and retrieve global parameters

    Returns
    -------
    parameters : dict
        Default parameters for the library.

    """
    parameters = {
        "low cutoff": 200,
        "high cutoff": 3500,
        "order": 2,
        "threshold portion": 0.1,
        "standard deviation multiplier": 5,
        "rms multiplier": 5,
        "refractory period": 0.001,
        "spike validation method": "Noisebased",
        "exit time": 0.001,
        "drop amplitude": 5,
        "max drop": 2,
        "minimal amount of spikes": 5,
        "default interval threshold": 100,
        "max interval threshold": 1000,
        "burst detection kde bandwidth": 1,
        "min channels": 0.5,
        "thresholding method": "Yen",
        "nbd kde bandwidth": 0.05,
        "remove inactive electrodes": True,
        "activity threshold": 0.1,
        "use multiprocessing": False,
        "synchronicity method": "SPIKE-distance",
    }

    return parameters


class QtStream:
    """Redirect sys.stdout so that print() calls inside analyse_wells emit a Qt signal"""

    def __init__(self, signal):
        self._signal = signal

    def write(self, text):
        text = text.strip()
        if text:
            self._signal.emit(text)

    def flush(self):
        pass


class AnalysisWorker(QObject):
    """
    Runs analyse_wells in a worker thread.
    """

    progress_updated = pyqtSignal(int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, filepath, parameters):
        super().__init__()
        self.filepath = filepath
        self.parameters = parameters
        self._stop_event = threading.Event()
        self.output_path = None

    def request_stop(self):
        self._stop_event.set()

    def run(self):
        original_stdout = sys.stdout
        sys.stdout = QtStream(self.log_message)
        success = False
        try:
            self.output_path = analyse_wells(
                fileadress=self.filepath,
                parameters=self.parameters,
                progress_signal=self.progress_updated,
                stop_event=self._stop_event,
            )
            success = not self._stop_event.is_set()
        except Exception as e:
            self.log_message.emit(f"[ERROR] {e}")
            success = False
        finally:
            sys.stdout = original_stdout
            self.finished.emit(success, self.output_path)


def _electrode_subprocess(memory_id, shape, _type, electrode, well, parameters):
    """
    Function that can be called to analyse a single electrode as a subprocess when using multiprocessing.

    Parameters
    ----------
    memory_id : str
        The ID of the shared memory block.
    shape : tuple
        Shape of the shared array.
    _type : type
        Type of the shared array.
    electrode : int
        The electrode to be analysed.
    well : int
        Well number.
    parameters : dict
        Dictionary containing global paramaters. The function will extract the values needed.

    """

    # Load in the data from the shared memory block in the RAM
    existing_shm = SharedMemory(name=memory_id, create=False)
    funcdata = np.ndarray(shape, _type, buffer=existing_shm.buf)

    # From all the data, select the electrode
    data = funcdata[electrode - 1]

    # Filter the data
    data = butter_bandpass_filter(data, parameters)

    # Calculate the threshold
    threshold_value = fast_threshold(data, parameters)

    # Calculate spike values
    if parameters["spike validation method"] == "Noisebased":
        pass
    elif parameters["spike validation method"] == "none":
        parameters["drop amplitude"] = 0
    else:
        raise ValueError(
            f'"{parameters["spike validation method"]}" is not a valid spike validation method'
        )
    spike_validation(data, electrode, well, threshold_value, parameters)

    # Detect the bursts
    burst_detection(data, electrode, well, parameters)

    data = None
    existing_shm.close()
    print(f"Processed electrode: {electrode}")


def analyse_wells(
    fileadress,
    parameters={},
    progress_signal=None,
    stop_event=None,
):
    """
    Analyse an entire MEA experiment, main function of the library.

    Parameters
    ----------
    fileadress : str
        The file location of the file that is to be analyzed.
    parameters : dict, optional
        Parameters that can alter the analysis, if left empty, will use default parameters.

    Returns
    -------
    outputpath : str
        Path to folder containing analysis results

    Notes
    -----
    This function calls all other functions to perform the full analysis on a MEA-dataset.
    Besides this, it also communicates the progress with the GUI.

    Always launch the function with an “if __name__ == ‘__main__’:” guard.

    Examples
    --------
    >>> from MEAlytics.mea import analyse_wells, get_default_parameters
    >>>
    >>> if __name__ == '__main__':
    ...     parameters = get_default_parameters()
    ...     fileadress = 'H:/MEA_data/mea_experiment.h5'
    ...     analyse_wells(
    ...         fileadress=fileadress,
    ...         parameters=parameters
    ...     )

    """

    analysis_time = time.time()

    lib_version = version("MEAlytics")
    print(f"MEAlytics - Version: {lib_version}")
    print(f"Analyzing: {fileadress}")

    path_obj = Path(fileadress)
    parent_dir = path_obj.parent

    # Create a directory which will contain the output
    output_folder = path_obj.stem
    output_folder += "_output"
    output_folder += f"_{datetime.date.today()}"
    output_folder += f"_{datetime.datetime.now().strftime('%H-%M-%S')}"

    outputpath = os.path.join(parent_dir, output_folder)
    os.makedirs(outputpath)

    # Helper functions
    def _emit_progress(current, total):
        if progress_signal is not None:
            progress_signal.emit(int(current), int(total))

    def _should_stop():
        return stop_event is not None and stop_event.is_set()

    # Call the freeze_support function to make sure multiprocessing still works properly if the algorithm is frozen
    multiprocessing.freeze_support()

    # Load the data
    MEA_file = get_mea_file_reader(fileadress)

    # Create figures folder for output
    os.makedirs(f"{outputpath}/figures")

    # Create hdf5 file for output
    output_hdf_file = f"{outputpath}/output_values.h5"
    with h5py.File(output_hdf_file, "w") as f:
        f.create_group("spike_values")
        f.create_group("burst_values")
        f.create_group("network_values")

    # Load default parameters if none were given
    if parameters == {}:
        parameters = get_default_parameters()

    # Create a list of all wells
    wells = list(range(1, MEA_file.num_wells + 1))

    # Save the parameters that have been given in a JSON file
    new_values = {
        "output path": outputpath,
        "output hdf file": output_hdf_file,
        "file adress": fileadress,
        "sampling rate": MEA_file.sampling_rate,
        "electrode amount": MEA_file.num_electrodes,
        "well amount": wells,
        "measurements": MEA_file.shape[1],
        "library version": lib_version,
    }

    parameters.update(new_values)

    with open(f"{outputpath}/parameters.json", "w") as outfile:
        json.dump(parameters, outfile, indent=4)

    # Flag for the first iteration
    first_iteration = True

    # With multiprocessing
    if parameters["use multiprocessing"]:
        # Save the data in shared memory
        print("Loading data into shared memory")
        num_elements = MEA_file.num_electrodes * MEA_file.shape[1]
        exact_size_bytes = num_elements * np.dtype(MEA_file.type).itemsize
        # Create space on the RAM
        sharedmemory = SharedMemory(create=True, size=int(exact_size_bytes))
        # Communicate file size with GUI
        _emit_progress(0, MEA_file.shape[0])
        # Create a np array in the shared memory
        data_shared = np.ndarray(
            (MEA_file.num_electrodes, MEA_file.shape[1]),
            dtype=MEA_file.type,
            buffer=sharedmemory.buf,
        )
        # Get the memory ID
        memory_id = sharedmemory.name
        # Clear up memory
        data = None

        # Start up a process for every single electrode
        print("Initializing processes")
        with multiprocessing.Pool(processes=MEA_file.num_electrodes) as pool:
            # Iterate over all wells
            for well in wells:
                start = time.time()
                # Calculate which electrodes belong to this well
                electrodes = np.arange(1, MEA_file.num_electrodes + 1)
                print(f"Analyzing well: {well}")

                readtime = time.time()
                # Read in the data of the well and put it into the shared memory block
                data_shared[:] = MEA_file.get_voltage_trace(well)
                print(f"Readtime: {time.time() - readtime}")

                # Divide the tasks to the processes
                args = [
                    (
                        memory_id,
                        (MEA_file.num_electrodes, MEA_file.shape[1]),
                        MEA_file.type,
                        electrode,
                        well,
                        parameters,
                    )
                    for electrode in electrodes
                ]
                pool.starmap(_electrode_subprocess, args)

                # Calculate the network bursts
                network_burst_detection([well], parameters)
                print(f"Calculated network bursts well: {well}")

                # Calculate electrode, well and synchronicity features
                electrode_features_df = electrode_features(well, parameters)
                well_features_df = well_features(well, parameters)

                print(f"Calculated features well: {well}")

                # If its the first iteration, create the dataframe
                if first_iteration:
                    first_iteration = False
                    electrode_features_output = copy.deepcopy(electrode_features_df)
                    output = feature_output(electrode_features_df, well_features_df)
                # If its not the first iteration, keep appending to the dataframe
                else:
                    electrode_features_output = pd.concat(
                        [
                            electrode_features_output,
                            copy.deepcopy(electrode_features_df),
                        ],
                        ignore_index=False,
                    )
                    output = pd.concat(
                        [
                            output,
                            feature_output(electrode_features_df, well_features_df),
                        ],
                        axis=0,
                        ignore_index=False,
                    )
                end = time.time()
                print(f"It took {end - start} seconds to analyse well: {well}")

                # Check if the user wants to exit the analysis
                if _should_stop():
                    sharedmemory.close()
                    sharedmemory.unlink()
                    pool.terminate()
                    pool.join()
                    data = None
                    del data
                    gc.collect()
                    print("Analysis aborted by user")
                    return

                _emit_progress(well * MEA_file.num_electrodes, MEA_file.shape[0])

        # Clean up the shared memory
        sharedmemory.close()
        sharedmemory.unlink()

    # Without multiprocessing
    else:
        for well in wells:
            start = time.time()
            print(f"Analyzing well: {well}")

            electrodes = np.arange(1, MEA_file.num_electrodes + 1)

            # Loop through all the electrodes
            for electrode in electrodes:
                data = MEA_file.get_voltage_trace(well, electrode)
                # Filter the data
                data = butter_bandpass_filter(data, parameters)

                # Calculate the threshold
                threshold_value = fast_threshold(data, parameters)

                # Calculate spike values
                if parameters["spike validation method"] == "Noisebased":
                    pass
                elif parameters["spike validation method"] == "none":
                    parameters["drop amplitude"] = 0
                else:
                    raise ValueError(
                        f'"{parameters["spike validation method"]}" is not a valid spike validation method'
                    )
                spike_validation(data, electrode, well, threshold_value, parameters)

                # Detect the bursts
                burst_detection(data, electrode, well, parameters)

                # Check if the user wants to exit the analysis
                if _should_stop():
                    data = None
                    del data
                    gc.collect()
                    print("Analysis aborted by user")
                    return

                _emit_progress(
                    (well - 1) * MEA_file.num_electrodes + electrode, MEA_file.shape[0]
                )
                print(f"Processed electrode: {electrode}")

            # Detect network bursts
            network_burst_detection([well], parameters, save_figures=True)
            print(f"Calculated network bursts well: {well}")

            # Calculate electrode and well features
            electrode_features_df = electrode_features(well, parameters)
            well_features_df = well_features(well, parameters)
            print(f"Calculated features well: {well}")

            # If its the first iteration, create the dataframe
            if first_iteration:
                first_iteration = False
                electrode_features_output = copy.deepcopy(electrode_features_df)
                output = feature_output(electrode_features_df, well_features_df)
            # If its not the first iteration, keep appending to the dataframe
            else:
                electrode_features_output = pd.concat(
                    [electrode_features_output, copy.deepcopy(electrode_features_df)],
                    ignore_index=False,
                )
                output = pd.concat(
                    [output, feature_output(electrode_features_df, well_features_df)],
                    axis=0,
                    ignore_index=False,
                )
            end = time.time()
            print(f"It took {end - start} seconds to analyse well: {well}")

        # Free up RAM
        data = None
        del data
        gc.collect()

    # Calculate synchronicity
    electrode_pair_features_df = electrode_pair_features(parameters)

    # Save the output
    output.to_csv(f"{outputpath}/{output_folder}_Features.csv", index=False)
    electrode_features_output.to_csv(
        f"{outputpath}/{output_folder}_Electrode_Features.csv", index=False
    )
    electrode_pair_features_df.to_csv(
        f"{outputpath}/{output_folder}_Synchronicity.csv", index=False
    )

    # Close the analysis
    print(f"It took {time.time() - analysis_time} seconds to analyse {fileadress}")
    print("Done")
    return outputpath
