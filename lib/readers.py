import os
from typing import Union
import numpy as np
import datetime
import h5py
import re
import xml.etree.ElementTree as ET
from .exporters import ARTFMetadata
from .hdf5_reader_module import SignalClass
from .artefact import Artefact
from .errors import WrongSignalGroupError


class HDFReader:

    def __init__(self, filename):
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File {filename} not found")
        self.filename = filename


    def read(self):
        """Reads ICP, ABP, Sampling rate, start and end time, ABP dataset name
        from HDF5 file."""
        with h5py.File(self.filename, 'r')  as f:
            # Read ICP
            wave_data_icp = SignalClass(f, 'icp')

            start_time = wave_data_icp.get_all_data_start_time()
            end_time = wave_data_icp.get_all_data_end_time()
            stream_duration_microsec = end_time - start_time
            stream = wave_data_icp.get_data_stream(start_time, stream_duration_microsec)

            sr_icp = int(np.ceil(stream.sampling_frq))
            data = np.array(stream.values)
            icp_data = data

            # Read ABP
            if "abp" in f["waves"].keys(): # type: ignore
                wave_data_abp = SignalClass(f, 'abp')
                abp_name = "abp"
            elif "art" in f["waves"].keys(): # type: ignore
                wave_data_abp = SignalClass(f, 'art')
                abp_name = "art"
            else:
                return None, None, None, (None, None), None

            start_time = wave_data_icp.get_all_data_start_time()
            end_time = wave_data_icp.get_all_data_end_time()
            stream_duration_microsec = end_time - start_time
            stream = wave_data_abp.get_data_stream(start_time, stream_duration_microsec)

            sr_abp = int(np.ceil(stream.sampling_frq))
            data = np.array(stream.values)
            abp_data = data

            assert sr_icp == sr_abp
            sr = sr_icp

            times = (start_time, end_time)
            return icp_data, abp_data, sr, times, abp_name

class ARTFReader:

    DATE_FMT = '%d/%m/%Y %H:%M:%S.%f'

    def __init__(self, filename):
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File {filename} not found")
        self.filename = filename


    def read(self, abp_name="abp") -> tuple[list[Artefact],
                            list[Artefact],
                            list[Artefact],
                            Union[ARTFMetadata, None]]:
        """Reads artefacts from .ARTF file.
        Returns Global, ICP and ABP artefacts in order."""
        tree = ET.parse(self.filename)
        root = tree.getroot()

        global_artefacts = []
        icp_artefacts = []
        abp_artefacts = []
        metadata = None

        for child in root:
            if child.tag == "Global":
                for artefact in child.findall("Artefact"):
                    global_artefacts.append(Artefact.from_artf_dict({
                        "ModifiedBy": artefact.get("ModifiedBy"),
                        "ModifiedDate": artefact.get("ModifiedDate"),
                        "StartTime": artefact.get("StartTime"),
                        "EndTime": artefact.get("EndTime")
                    }, ARTFReader.DATE_FMT))

            if child.tag == "SignalGroup":
                if child.get("Name") == "icp":
                    for artefact in child.findall("Artefact"):
                        icp_artefacts.append(Artefact.from_artf_dict({
                            "ModifiedBy": artefact.get("ModifiedBy"),
                            "ModifiedDate": artefact.get("ModifiedDate"),
                            "StartTime": artefact.get("StartTime"),
                            "EndTime": artefact.get("EndTime")
                        }, ARTFReader.DATE_FMT))
                elif child.get("Name") == abp_name:
                    for artefact in child.findall("Artefact"):
                        abp_artefacts.append(Artefact.from_artf_dict({
                            "ModifiedBy": artefact.get("ModifiedBy"),
                            "ModifiedDate": artefact.get("ModifiedDate"),
                            "StartTime": artefact.get("StartTime"),
                            "EndTime": artefact.get("EndTime")
                        }, ARTFReader.DATE_FMT))
                else:
                    series_name = child.get("Name")
                    raise WrongSignalGroupError(f"Expected SignalGroups icp and {abp_name} but found {series_name}")
            if child.tag == "Info":
                hdf5_filename = child.get("HDF5Filename")
                user_id = child.get("UserID")
                metadata = ARTFMetadata(hdf5_filename, user_id)

        return global_artefacts, icp_artefacts, abp_artefacts, metadata
