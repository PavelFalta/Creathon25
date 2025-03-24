"""
v1.1f

Developed by The Department of Data Analysis and Simulations.

More information at odas.ujep.cz

"""


import datetime
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Set
import json
import csv

import h5py
import numpy as np


class EmptySegment(Exception):
    """Custom exception raised when a segment is found to be empty."""
    pass


class FrequencyMismatchError(Exception):
    """Custom exception raised when frequencies differ across files."""
    pass


@dataclass
class Segment:
    """Represents a segment of data with start and end times, and associated data.

    Attributes:
        start_time (int): Start time of the segment as a Unix timestamp in microseconds.
        end_time (int): End time of the segment as a Unix timestamp in microseconds.
        empty (bool): Whether the segment contains data or not.
        file (str): Full path to the HDF5 file the segment was extracted from.
        patient_id (str): The patient ID associated with the segment.
        frequency (float): Frequency information pulled from the index of the HDF5 file. Default is 0.0.
        data (np.ndarray): Data values associated with the segment. Default is an empty array.
    """
    start_time: int
    end_time: int
    empty: bool
    file: str
    patient_id: str
    frequency: float = field(default=0.0)
    data: np.ndarray = field(default_factory=lambda: np.array([]))


class Signal:
    """Handles the loading and processing of signal data from HDF5 files.

    Attributes:
        file_path (str): Path to the HDF5 file. Must end with ".hdf5".
        artf_path (str): Path to the ARTF file. Must end with ".artf".
        mode (str): The mode to use for extracting data from the HDF5 file. Either "abp" or "icp".
        skip_empty (bool): If true, skips empty segments without raising an EmptySegment exception.
    """

    def __init__(self, file_path: str, artf_path: str, mode: str, skip_empty: bool = False) -> None:
        self._file_path = file_path
        self._artf_path = artf_path
        self._mode = mode.lower()
        self._skip_empty = skip_empty

        if self._mode not in ["abp", "icp"]:
            raise ValueError("Invalid signal mode. Must be either 'abp' or 'icp'.")

        self._index_data = self._load_index_data()
        self._start_times = np.array(
            [item["starttime"] for item in self._index_data], dtype=np.int64)
        self._frequencies = np.array(
            [item["frequency"] for item in self._index_data], dtype=np.float64)
        self._lengths = np.array([item["length"]
                                  for item in self._index_data], dtype=np.int64)
        self._intervals = (1_000_000 / self._frequencies).astype(np.int64)
        self._data: Dict[Tuple[int, int], np.ndarray] = {}

    def _load_index_data(self) -> np.ndarray:
        """Loads the index data from the HDF5 file.

        Returns:
            np.ndarray: The index data loaded from the HDF5 file.
        """
        try:
            with h5py.File(self._file_path, 'r') as hdf:
                if self._mode == "abp" and hdf.get(f"waves/art"):
                    self._mode = "art"

                index_data = hdf.get(f"waves/{self._mode}.index")
                if index_data is None:
                    index_data = hdf[f"waves/{self._mode}"].attrs["index"]
                index_data = np.array(
                    [dict(zip(["startidx", "starttime", "length", "frequency"], item)) for item in index_data]
                )

            return index_data

        except FileNotFoundError:
            raise FileNotFoundError("No such file or the file is missing an extension.")

    def prepare_data_for_segments(self, segments: List[Segment]) -> None:
        """Loads data for the specified segments and assigns frequency to them.

        Args:
            segments (List[Segment]): The list of segments to load data for.
        """
        try:
            with h5py.File(self._file_path, 'r') as hdf:
                all_data = hdf[f"waves/{self._mode}"]
                for segment in segments:
                    start_idx = np.searchsorted(
                        self._start_times, segment.start_time, side="right") - 1
                    end_idx = np.searchsorted(
                        self._start_times, segment.end_time, side="left")

                    for idx in range(start_idx, end_idx):
                        data_range_start = self._start_times[idx]
                        data_range_end = data_range_start + \
                            self._lengths[idx] * self._intervals[idx]

                        if (data_range_start, data_range_end) not in self._data:
                            self._data[(data_range_start, data_range_end)] = all_data[
                                self._index_data[idx]["startidx"]:self._index_data[idx]["startidx"] +
                                self._lengths[idx]
                            ]

                    segment.frequency = self._frequencies[idx]
        except FileNotFoundError:
            raise FileNotFoundError("No such file or the file is missing an extension.")

    def get_data_in_range(self, segment: Segment) -> np.ndarray:
        """Retrieves data within the specified time range for a segment.

        Args:
            segment (Segment): The segment whose data needs to be retrieved.

        Returns:
            np.ndarray: The concatenated data within the specified time range.
        """
        start_time = segment.start_time
        end_time = segment.end_time
        result_data = [
            data_slice[max(0, int((start_time - data_start) / self._intervals[0])):min(
                data_slice.shape[0], int((end_time - data_start) / self._intervals[0]))]
            for (data_start, data_end), data_slice in self._data.items()
            if data_start <= end_time and data_end >= start_time
        ]

        segment.empty = not bool(result_data)
        if segment.empty and not self._skip_empty:
            raise EmptySegment("An empty segment has been detected.")

        return np.nan_to_num(np.concatenate(result_data), nan=-99999) if result_data else np.array([])

    @property
    def artf_path(self) -> str:
        """Returns the path to the ARTF file."""
        return self._artf_path

    @property
    def file_path(self) -> str:
        """Returns the path to the HDF5 file."""
        return self._file_path

    @property
    def mode(self) -> str:
        """Returns the mode."""
        return self._mode




class SingleFileExtractor:
    """Extracts anomalous and normal segments from a single file.

    Attributes:
        file_path (str): Path to the HDF5 file. Always ends with ".hdf5"
        mode (str): The mode to use for extracting data from the HDF5 file. Only use "abp" or "icp".
        matching (bool): Whether to extract matching number of anomalous and normal segments or not.
                         This option DOESN'T guarantee len(normal_segments) == len(anomalies),
                         but rather len(normal_segments) <= len(anomalies).
        matching_multiplier (int): Multiplier for matching anomalies. For example, a multiplier of 2
                                   produces len(normal_segments) <= len(anomalies) * 2.
        skip_empty (bool): If true, skips an empty segment instead of raising an EmptySegment exception.
    
    Example usage:
    >>> extractor = SingleFileExtractor(FILE_PATH, "abp")

    >>> normal_segments = extractor.get_normal()
    >>> anomalous_segments = extractor.get_anomalies()
    """

    def __init__(self, file_path: str, mode: str, matching: bool = False, matching_multiplier: int = 1, skip_empty: bool = True) -> None:
        self._signal = Signal(file_path, self._assign_artf_file_path(file_path), mode, skip_empty)
        self._matching = matching
        self._anomalies: List[Segment] = []
        self._normal: List[Segment] = []
        self._matching_multiplier = matching_multiplier

    def _extract(self):
        if self._matching:
            self._extract_matching()
        else:
            self._extract_all()

    @staticmethod
    def _assign_artf_file_path(file_path: str) -> Path:
        return Path(file_path).with_suffix(".artf")

    def _get_anomaly_normal_segments(self) -> Tuple[List[Segment], List[Segment]]:
        try:
            with open(self._signal.artf_path, 'r', encoding='ISO-8859-1') as xml_file:
                tree = ET.parse(xml_file)
        except FileNotFoundError:
            raise FileNotFoundError("No such ARTF file found.")
        
        root = tree.getroot()
        modes = [f"SignalGroup[@Name='{self._signal.mode}']", "Global"]

        anomalous_segments, normal_segments = [], []

        for mode in modes:
            normal_start_unix = 0
            for element in root.findall(f".//{mode}/Artefact"):
                start_time_unix = self._unix_from_dt(element.get("StartTime"))
                end_time_unix = self._unix_from_dt(element.get("EndTime"))
                from_file = self._signal.file_path
                patient = re.search(r"TBI_(\w+)", from_file).group(1).split('_')[0]

                anomalous_segments.append(Segment(start_time=start_time_unix, end_time=end_time_unix, file=from_file, patient_id=patient, empty=True))

                if normal_start_unix:
                    normal_end_unix = start_time_unix
                    arr = np.linspace(normal_start_unix, normal_end_unix, int((normal_end_unix - normal_start_unix) / 10_000_000) + 1)
                    normal_segments.extend(Segment(start_time=arr[i], end_time=arr[i + 1], file=from_file, patient_id=patient, empty=True) for i in range(len(arr) - 1))
                
                normal_start_unix = end_time_unix

        return anomalous_segments, normal_segments

    def _extract_all(self) -> None:
        """Extracts all anomalous and normal segments."""
        anomalous_segments, normal_segments = self._get_anomaly_normal_segments()

        for i, segments in enumerate([normal_segments, anomalous_segments]):
            self._extract_data_for_segments(segments, anomaly=bool(i))

    def _extract_matching(self) -> None:
        """Extracts anomalies and a matching number of normal segments."""
        anomalous_segments, normal_segments = self._get_anomaly_normal_segments()
        normal_segments = normal_segments[:len(anomalous_segments) * self._matching_multiplier]

        for i, segments in enumerate([normal_segments, anomalous_segments]):
            self._extract_data_for_segments(segments, anomaly=bool(i))

    def _extract_data_for_segments(self, segments: List[Segment], anomaly: bool = False) -> None:
        target = self._anomalies if anomaly else self._normal
        target[:] = segments
        self._signal.prepare_data_for_segments(segments)
        for segment in target:
            segment.data = self._signal.get_data_in_range(segment)

    def export_data(self, output_dir: str, export_format: str = "csv") -> None:
        """Saves anomalous and normal segments as CSV or JSON in the specified output directory."""
        self._extract()
        anomaly_path, normal_path = Path(output_dir) / "anomalies", Path(output_dir) / "normal_segments"
        anomaly_path.mkdir(parents=True, exist_ok=True)
        normal_path.mkdir(parents=True, exist_ok=True)

        base_filename = Path(self._signal.file_path).stem
        anomaly_data = [{**segment.__dict__, 'data': segment.data.tolist()} for segment in self._anomalies]
        normal_data = [{**segment.__dict__, 'data': segment.data.tolist()} for segment in self._normal]

        if export_format.lower() == "json":
            with open(anomaly_path / f"{base_filename}_anomalies.json", 'w') as f:
                json.dump(anomaly_data, f, indent=4)
            with open(normal_path / f"{base_filename}_normal.json", 'w') as f:
                json.dump(normal_data, f, indent=4)
        elif export_format.lower() == "csv":
            if self._anomalies:
                with open(anomaly_path / f"{base_filename}_anomalies.csv", 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self._anomalies[0].__dict__.keys())
                    writer.writeheader()
                    writer.writerows(anomaly_data)
            if self._normal:
                with open(normal_path / f"{base_filename}_normal.csv", 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self._normal[0].__dict__.keys())
                    writer.writeheader()
                    writer.writerows(normal_data)
        else:
            raise ValueError(f"Unsupported format: {export_format}. Please choose 'json' or 'csv'.")

    def get_frequency(self) -> int:
        """Returns the frequency of the first anomalous or normal segment."""
        if self._anomalies:
            return self._anomalies[0].frequency
        if self._normal:
            return self._normal[0].frequency
        return 0

    @staticmethod
    def _unix_from_dt(dt_string: str) -> int:
        """Converts a datetime string to a Unix timestamp in microseconds."""
        return int(datetime.datetime.strptime(dt_string, "%d/%m/%Y %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).timestamp() * 1_000_000)

    def get_anomalies(self) -> List[Segment]:
        """Returns the extracted anomalies."""
        self._extract()
        return [segment for segment in self._anomalies if not segment.empty]

    def get_normal(self) -> List[Segment]:
        """Returns the extracted normal segments."""
        self._extract()
        return [segment for segment in self._normal if not segment.empty]
    
    def return_hdf5_as_array(self) -> np.array:
        """Loads and returns the entire dataset from the HDF5 file as a NumPy array.
        
        Returns:
            np.ndarray: The full dataset from the HDF5 file.
        """
        try:
            with h5py.File(self._signal.file_path, 'r') as hdf:
                dataset = hdf[f"waves/{self._signal.mode}"]
                entire_data = np.nan_to_num(np.array(dataset), nan=-99999)
            return entire_data

        except FileNotFoundError:
            raise FileNotFoundError("No such file or the file is missing an extension.")


class FolderExtractor:
    """Extracts anomalous and normal segments from all files in a folder.

    Attributes:
        folder_path (str): Path to the folder containing the files, also searches subfolders for files.
        mode (str): The mode to use for extracting data from the HDF5 files. Only use "abp" or "icp".
        matching (bool): Whether to extract matching number of anomalous and normal segments or not.
                         This option DOESN'T guarantee len(normal_segments) == len(anomalies),
                         but rather len(normal_segments) <= len(anomalies).
        matching_multiplier (int): Multiplier for matching anomalies. For example, a multiplier of 2
                                   produces len(normal_segments) <= len(anomalies) * 2.
        skip_empty (bool): If true, skips an empty segment instead of raising an EmptySegment exception.
    
    Example usage:
    >>> extractor = FolderExtractor(FOLDER_PATH)
    >>> anomalous_segments, normal_segments = extractor.extract_all()


    >>> extractor = FolderExtractor(FOLDER_PATH)
    >>> anomalous_segments_patient_dictionary, normal_segments_patient_dictionary = extractor.extract_merged()

    """

    def __init__(self, folder_path: str, mode: str, matching: bool = False, matching_multiplier: int = 1, skip_empty: bool = True) -> None:
        self._folder_path = folder_path
        self._mode = mode
        self._matching = matching
        self._matching_multiplier = matching_multiplier
        self._skip_empty = skip_empty

        if not os.path.exists(self._folder_path):
            raise FileNotFoundError("Invalid folder path.")

    def extract_all(self) -> Tuple[List[Segment], List[Segment]]:
        """Extracts anomalous and normal segments from all files in the folder.
        Returns:
            Tuple[List[Segment], List[Segment]]: A tuple containing arrays of anomalous and normal segments.
        """
        anomalies, normal, frequencies = [], [], set()

        for root, _, files in os.walk(self._folder_path):
            hdf5_files = [f for f in files if f.endswith(".hdf5")]
            artf_files = {f.replace(".artf", ""): f for f in files if f.endswith(".artf")}

            for hdf5_file in hdf5_files:
                file_name = hdf5_file.replace(".hdf5", "")
                if file_name in artf_files:
                    extractor = SingleFileExtractor(
                        file_path=os.path.join(root, hdf5_file),
                        mode=self._mode,
                        matching=self._matching,
                        matching_multiplier=self._matching_multiplier,
                        skip_empty=self._skip_empty,
                    )

                    anomalies.extend(extractor.get_anomalies())
                    normal.extend(extractor.get_normal())

                    frequency = extractor.get_frequency()
                    if frequency:
                        frequencies.add(frequency)

        if len(frequencies) > 1:
            raise FrequencyMismatchError(f"More than one frequency found in folder: {frequencies}")

        return anomalies, normal

    def extract_merged(self) -> Tuple[Dict[str, List[Segment]], Dict[str, List[Segment]]]:
        """Extracts and merges anomalies and normal segments for each patient.

        Returns:
            Tuple[Dict[str, List[Segment]], Dict[str, List[Segment]]]: A tuple containing dictionaries of anomalous and normal segments grouped by patient ID.
        """
        patient_data_artf: Dict[str, List[Segment]] = {}
        patient_data_normal: Dict[str, List[Segment]] = {}
        frequencies: Set[float] = set()

        patient_pattern = re.compile(r"TBI_(\w+)")

        for root, dirs, files in os.walk(self._folder_path):
            hdf5_files = [file for file in files if file.endswith(".hdf5")]
            artf_files = {file.replace(".artf", ""): file for file in files if file.endswith(".artf")}

            for hdf5_file in hdf5_files:
                match = patient_pattern.match(hdf5_file)
                if match:
                    patient_id = match.group(1).split('_')[0]

                    file_name = hdf5_file.replace(".hdf5", "")
                    if file_name in artf_files:
                        hdf5_path = os.path.join(root, hdf5_file)

                        extractor = SingleFileExtractor(
                            file_path=hdf5_path,
                            mode=self._mode,
                            matching=self._matching,
                            matching_multiplier=self._matching_multiplier,
                            skip_empty=self._skip_empty
                        )

                        anomalies: List[Segment] = extractor.get_anomalies()
                        normals: List[Segment] = extractor.get_normal()

                        frequency: float = extractor.get_frequency()
                        if frequency:
                            frequencies.add(frequency)

                        if patient_id not in patient_data_artf:
                            patient_data_artf[patient_id] = []
                        if patient_id not in patient_data_normal:
                            patient_data_normal[patient_id] = []

                        patient_data_artf[patient_id].extend(anomalies)
                        patient_data_normal[patient_id].extend(normals)

                    else:
                        print(f"No ARTF file found for {file_name} in {root}")

        if len(frequencies) > 1:
            raise FrequencyMismatchError(f"More than one frequency found in folder: {frequencies}")

        return patient_data_artf, patient_data_normal

    
    
    def export_data(self, output_dir: str, export_format: str = "csv") -> None:
        """Exports the extracted data for each file.

        Args:
            output_dir (str): Path to the output folder where the segments should be saved.
            format (str): Format in which to save the files, either 'csv' or 'json'. Default is 'csv'.
        """
        output_dir_path = Path(fr"{output_dir}/{self._mode}")
        output_dir_path.mkdir(parents=True, exist_ok=True)

        for root, _, files in os.walk(self._folder_path):
            hdf5_files = [f for f in files if f.endswith(".hdf5")]
            artf_files = {f.replace(".artf", ""): f for f in files if f.endswith(".artf")}

            for hdf5_file in hdf5_files:
                file_name = hdf5_file.replace(".hdf5", "")
                if file_name in artf_files:
                    extractor = SingleFileExtractor(
                        file_path=os.path.join(root, hdf5_file),
                        mode=self._mode,
                        matching=self._matching,
                        matching_multiplier=self._matching_multiplier,
                        skip_empty=self._skip_empty,
                    )
                    extractor.export_data(output_dir_path, export_format)

    def return_hdf5_as_array(self) -> Dict[str, np.array]:
        """Extracts anomalous and normal segments from all files in the folder.
        Returns:
            Tuple[List[Segment], List[Segment]]: A tuple containing arrays of anomalous and normal segments.
        """

        data_collector = {}

        for root, _, files in os.walk(self._folder_path):
            hdf5_files = [f for f in files if f.endswith(".hdf5")]

            for hdf5_file in hdf5_files:
                file_name = hdf5_file.replace(".hdf5", "")

                extractor = SingleFileExtractor(
                        file_path=os.path.join(root, hdf5_file),
                        mode=self._mode,
                        matching=self._matching,
                        matching_multiplier=self._matching_multiplier,
                        skip_empty=self._skip_empty,
                    )
                
                hdf5_array = extractor.return_hdf5_as_array()

                if data_collector.get(file_name) is None:
                    data_collector[file_name] = hdf5_array
                elif not np.all(data_collector.get(file_name) == hdf5_array):
                    print(f"A file with the same name as {file_name} was already loaded, skipping the file.")

        return data_collector
