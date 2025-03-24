from .readers import ARTFReader
from .hdf5_reader_module import SignalClass

import h5py
import numpy as np


WINDOW_SIZE_SEC = 10

def read_artf(filename):
    """
    Read artefacts from file

    Returns:
        global_artefacts: list of global artefacts
        icp_artefacts: list of ICP artefacts
        abp_artefacts: list of ABP artefacts
        metadata: metadata object
    """
    reader = ARTFReader(filename)
    try:
        global_artefacts, icp_artefacts, abp_artefacts, metadata = reader.read(abp_name="abp")
    except Exception:
        global_artefacts, icp_artefacts, abp_artefacts, metadata = reader.read(abp_name="art")

    return {
        "global_artefacts": global_artefacts,
        "icp_artefacts": icp_artefacts,
        "abp_artefacts": abp_artefacts,
        "metadata": metadata
    }

def read_hdf5_signal(hdf5_file, signal="icp"):
    """
    Read HDF5 file

    Returns:
        data: numpy array of data
        sample_rate: sample rate of data
        start_time_s: start time of data in seconds
        end_time_s: end time of data in seconds
    """
    wave_data = SignalClass(hdf5_file, signal)

    start_time = wave_data.get_all_data_start_time()
    start_time_s = start_time / 1e6
    end_time = wave_data.get_all_data_end_time()
    end_time_s = end_time / 1e6
    stream_duration_microsec = end_time - start_time

    stream = wave_data.get_data_stream(start_time, stream_duration_microsec)
    data = np.array(stream.values)

    sample_rate = stream.sampling_frq

    return {
        "signal": data,
        "sample_rate": sample_rate,
        "start_time_s": start_time_s,
        "end_time_s": end_time_s
    }

def read_hdf5(filename):
    with h5py.File(filename, 'r') as f:
        icp_signal = read_hdf5_signal(f, signal="icp")
        try:
            abp_signal = read_hdf5_signal(f, signal="abp")
        except KeyError:
            abp_signal = read_hdf5_signal(f, signal="art")

        return icp_signal, abp_signal

def read_hdf5_with_signals(filename):
    with h5py.File(filename, 'r') as f:

        signals = []
        if 'waves' in f:
            for signal in f['waves']:
                # skip .index .quality
                if '.' in signal:
                    continue

                signals.append(signal)


        icp_signal = read_hdf5_signal(f, signal="icp")
        try:
            abp_signal = read_hdf5_signal(f, signal="abp")
        except KeyError:
            abp_signal = read_hdf5_signal(f, signal="art")

        return icp_signal, abp_signal, signals

def get_hdf5_signal_names(filename: str):
    with h5py.File(filename, 'r') as f:

        signals = []
        if 'waves' in f:
            for signal in f['waves']:
                # skip .index .quality
                if '.' in signal:
                    continue

                signals.append(signal)
        return signals
