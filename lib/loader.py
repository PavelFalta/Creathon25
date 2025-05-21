"""
v2.4c

Developed by The Laboratory of Data Analysis and Simulations.

More information at odas.ujep.cz

"""


import datetime
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Union, Optional, Set, Tuple, Any, TypeVar, Iterable, Iterator, Callable, TypedDict
import csv
import json
import h5py
import numpy as np
import hashlib
from abc import ABC, abstractmethod
from collections import defaultdict
import pandas as pd
import tqdm


def unix_from_dt(dt_string: str) -> int:
    """
    Converts a datetime string to a Unix timestamp in microseconds.
    
    Args:
        dt_string: A string representation of datetime in format 'dd/mm/yyyy HH:MM:SS.fff'
        
    Returns:
        An integer representing the Unix timestamp in microseconds
    """
    return int(datetime.datetime.strptime(dt_string, "%d/%m/%Y %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).timestamp() * 1_000_000)

def dt_from_unix(unix: int) -> str:
    """
    Converts a Unix timestamp in microseconds to a datetime string.
    
    Args:
        unix: An integer representing the Unix timestamp in microseconds
        
    Returns:
        A string representation of datetime in format 'dd/mm/yyyy HH:MM:SS.fff'
    """
    return datetime.datetime.fromtimestamp(unix / 1_000_000, tz=datetime.timezone.utc).strftime("%d/%m/%Y %H:%M:%S.%f")[:-4]

class IExtractor(ABC):
    """
    Interface defining the common operations for data extractors.
    """
    
    @abstractmethod
    def get_raw_data(self, signal_name: str) -> Union[np.ndarray, Dict[str, np.ndarray]]:
        """
        Get raw data for a specific signal.
        
        Args:
            signal_name: Name of the signal to retrieve data for
            
        Returns:
            Raw data as a numpy array or a dictionary of arrays
        """
        pass

    @abstractmethod
    def get_signal_names(self) -> Union[List[str], Dict[str, Any]]:
        """
        Get all available signal names.
        
        Returns:
            List of signal names or dictionary with signal information
        """
        pass

    @abstractmethod
    def get_annotations(self, signal_name: str) -> Union[Dict[str, 'Annotation'], List[Dict[str, 'Annotation']]]:
        """
        Get annotations for a specific signal.
        
        Args:
            signal_name: Name of the signal to retrieve annotations for
            
        Returns:
            Dictionary or list of dictionaries containing annotation information
        """
        pass

    @abstractmethod
    def describe(self) -> str:
        """
        Get a human-readable description of the extracted data.
        
        Returns:
            String description of the extracted data
        """
        pass

    @abstractmethod
    def auto_annotate(self, optional_folder_path: Optional[str] = None) -> None:
        """
        Automatically annotate signals using available annotation files.
        
        Args:
            optional_folder_path: Optional path to look for annotation files
        """
        pass

    @abstractmethod
    def extract(self, signal_name: str) -> Tuple[List['Segment'], List['Segment']]:
        """
        Extract good and anomalous segments for a given signal.
        
        Args:
            signal_name: Name of the signal to extract segments for
            
        Returns:
            Tuple containing lists of good segments and anomalous segments
        """
        pass
    
    @abstractmethod
    def load_data(self, *segments: List['Segment']) -> None:
        """
        Load data for the given segments.
        
        Args:
            *segments: Variable number of segment lists to load data for
        """
        pass

    @abstractmethod
    def export_to_csv(self, optional_folder_path: Optional[str] = None) -> None:
        """
        Export segments in CSV format.
        
        Args:
            optional_folder_path: Optional path to save the CSV files. 
            If not provided, the current working directory will be used.
        """
        pass

@dataclass
class Segment:
    """
    Represents a segment of signal data that may be annotated as normal or anomalous.
    
    Attributes:
        signal_name: Name of the signal this segment belongs to
        anomalous: Boolean indicating if this segment contains an anomaly
        start_timestamp: Start time of the segment in microseconds (Unix timestamp)
        end_timestamp: End time of the segment in microseconds (Unix timestamp)
        data_file: Path to the file containing the segment data
        patient_id: Identifier of the patient this segment belongs to
        annotators: List of annotators who have annotated this segment
        frequency: Sampling frequency of the signal in Hz
        data: Array of signal values. Empty until `load_data` is called.
        id: Unique identifier for the segment
        weight: Weight value representing annotator consensus (0.0-1.0)
        anomalies_annotations: List of annotators who marked this segment as anomalous
    """
    signal_name: str
    anomalous: bool
    start_timestamp: int
    end_timestamp: int
    data_file: str
    patient_id: str
    annotators: List[str]
    frequency: float
    data: np.ndarray
    id: str
    weight: float
    anomalies_annotations: List[str]


    def describe(self) -> str:
        """
        Generate a detailed description of the segment.
        
        Returns:
            A formatted string describing the segment's properties and data statistics
        """
        data = self.data
        data_loaded = len(data) > 0
        description = {
            "Signal Name": self.signal_name,
            "Patient ID": self.patient_id,
            "Annotators": ", ".join(self.annotators),
            "Frequency (Hz)": self.frequency,
            "Start Time": dt_from_unix(self.start_timestamp),
            "End Time": dt_from_unix(self.end_timestamp),
            "Duration (s)": (self.end_timestamp - self.start_timestamp) / 1_000_000,
            "Anomalous": self.anomalous,
            "Data Loaded": data_loaded
        }
        
        description_str = "\n".join([f"{key}: {value}" for key, value in description.items()])
        if data_loaded:
            description["Data Summary"] = {
                "Count": len(data),
                "NaN Count": np.sum(np.isnan(data)),
                "Mean": np.nanmean(data),
                "Standard Deviation": np.nanstd(data),
                "Min": np.nanmin(data),
                "25th Percentile": np.nanpercentile(data, 25),
                "Median": np.nanpercentile(data, 50),
                "75th Percentile": np.nanpercentile(data, 75),
                "Max": np.nanmax(data)
            }
            data_summary = description["Data Summary"]
            description_str += f"\n\nData Summary:\n"
            description_str += "\n".join([f"   {key}: {value}" for key, value in data_summary.items()])
        
        return description_str

@dataclass
class Annotation:
    """
    Represents an annotation set for a signal, containing good and anomalous segments.
    
    Attributes:
        good_segments: List of segments marked as normal/good
        anomalies: List of segments marked as anomalous
        annotator: Name of the annotator who created this annotation
    """
    good_segments: List[Segment]
    anomalies: List[Segment]
    annotator: str

class Signal:
    """
    Represents a signal from a data file, containing raw data and potential annotations.
    
    Attributes:
        _file_path: Path to the source file
        _startidx: Starting index in the source data
        _starttime: Start time in microseconds (Unix timestamp)
        _length: Number of data points in the signal
        _frequency: Sampling frequency in Hz
        _signal_name: Name of the signal
        _raw_data: Raw signal data
        _annotations: Dictionary of annotations for this signal
    """
    def __init__(
        self, 
        file_path: str, 
        signal_name: str, 
        startidx: int, 
        starttime: int, 
        length: int, 
        frequency: float, 
        raw_data: np.ndarray
    ) -> None:
        """
        Initialize a Signal object.
        
        Args:
            file_path: Path to the source file
            signal_name: Name of the signal
            startidx: Starting index in the source data
            starttime: Start time in microseconds (Unix timestamp)
            length: Number of data points in the signal
            frequency: Sampling frequency in Hz
            raw_data: Raw signal data array
        """
        self._file_path = file_path
        self._startidx = startidx
        self._starttime = starttime
        self._length = length
        self._frequency = frequency
        self._signal_name = signal_name
        self._raw_data = raw_data
        self._annotations: Dict[str, Annotation] = {}

    
    def add_annotation(self, annotation_times_list: List[Tuple[int, int]], annotator: Optional[str]) -> None:
        """
        Add an annotation to the signal.
        
        Args:
            annotation_times_list: List of (start_time, end_time) tuples for anomalies
            annotator: Name of the annotator
        """
        length_in_seconds = 10
        segment_length = int(self._frequency * length_in_seconds)
        num_segments = len(self._raw_data) // segment_length

        segment_start_times = self._starttime + np.arange(num_segments) * length_in_seconds * 1_000_000
        segment_end_times = segment_start_times + length_in_seconds * 1_000_000

        patient_id_match = re.search(r"_(\d{3})", self._file_path)
        patient_id = patient_id_match.group(1) if patient_id_match else "Unknown"

        annotator_base = annotator if annotator else "Unknown"
        annotator = annotator_base
        annotator_index = 0

        while any(annotation.annotator == annotator for annotation in self._annotations.values()):
            annotator = f"{annotator_base}_{annotator_index}"
            annotator_index += 1


        good_segments: List[Segment] = []
        anomalous_segments: List[Segment] = []

        if annotation_times_list:
            annotation_times_list = np.array(annotation_times_list)
            signal_end_time = self._starttime + int(self._length * 1_000_000 / self._frequency)

            valid_annotations = annotation_times_list[(annotation_times_list[:, 0] >= self._starttime) & (annotation_times_list[:, 1] <= signal_end_time)]

            for i in range(num_segments):
                segment_start_time = segment_start_times[i]
                segment_end_time = segment_end_times[i]

                is_anomalous = np.any(
                    (valid_annotations[:, 0] <= segment_start_time) & (valid_annotations[:, 1] > segment_start_time) |
                    (valid_annotations[:, 0] < segment_end_time) & (valid_annotations[:, 1] >= segment_end_time)
                )
                
                input_str = f"{segment_start_time}{segment_end_time}{self._file_path}".encode()
                id = hashlib.sha256(input_str).hexdigest()

                segment_obj = Segment(
                    signal_name=self._signal_name,
                    anomalous=is_anomalous,
                    start_timestamp=segment_start_time,
                    end_timestamp=segment_end_time,
                    data_file=self._file_path,
                    patient_id=patient_id,
                    annotators=[annotator],
                    frequency=self._frequency,
                    data=np.array([]),
                    id=id,
                    weight=0.0,
                    anomalies_annotations=[]
                )

                if is_anomalous:
                    anomalous_segments.append(segment_obj)
                else:
                    good_segments.append(segment_obj)
        else:
            is_anomalous = False
            for i in range(num_segments):
                segment_start_time = segment_start_times[i]
                segment_end_time = segment_end_times[i]

                input_str = f"{segment_start_time}{segment_end_time}{self._file_path}".encode()
                id = hashlib.sha256(input_str).hexdigest()

                segment_obj = Segment(
                    signal_name=self._signal_name,
                    anomalous=is_anomalous,
                    start_timestamp=segment_start_time,
                    end_timestamp=segment_end_time,
                    data_file=self._file_path,
                    patient_id=patient_id,
                    annotators=[annotator],
                    frequency=self._frequency,
                    data=np.array([]),
                    id=id,
                    weight=0.0,
                    anomalies_annotations=[]
                )

                good_segments.append(segment_obj)

        annotation_idx = f"Annotation n. {len(self._annotations)}"

        self._annotations[annotation_idx] = Annotation(good_segments=good_segments, anomalies=anomalous_segments, annotator=annotator)
    
    def load_data(self, segments: List[Segment]) -> None:
        """
        Load actual data values for the given segments.
        
        Args:
            segments: List of segments to load data for
        """
        for segment in segments:
            segment_start_idx = int((segment.start_timestamp - self._starttime) // 1_000_000 * self._frequency)
            segment_end_idx = int((segment.end_timestamp - self._starttime) // 1_000_000 * self._frequency)
            segment.data = self._raw_data[segment_start_idx:segment_end_idx]
    
    @property
    def frequency(self) -> float:
        """Get the sampling frequency of the signal."""
        return self._frequency
    
    @property
    def signal_name(self) -> str:
        """Get the name of the signal."""
        return self._signal_name
    
    @property
    def length(self) -> int:
        """Get the length of the signal data."""
        return self._length
    
    @property
    def starttime(self) -> int:
        """Get the start time of the signal in microseconds."""
        return self._starttime
    
    @property
    def raw_data(self) -> np.ndarray:
        """Get the raw signal data."""
        return self._raw_data
    
    @property
    def annotations(self) -> Dict[str, Annotation]:
        """
        Get all annotations for this signal.
        
        Raises:
            ValueError: If the signal has not been annotated yet
        
        Returns:
            Dictionary mapping annotation keys to Annotation objects
        """
        if not self._annotations:
            raise ValueError("This signal has yet to be annotated.")
        return self._annotations
    
    @property
    def annotated(self) -> bool:
        """Check if the signal has been annotated."""
        if not self._annotations:
            return False
        return True

class SingleFileExtractor(IExtractor):
    """
    Extractor for processing a single HDF5 file with signals and annotations.
    
    This class handles loading, annotating, and extracting data from a single HDF5 file,
    which may contain multiple signals.
    
    Attributes:
        _signals: List of Signal objects extracted from the file
        _hdf5_file_path: Path to the HDF5 file
        _hdf5_file_name: Filename of the HDF5 file
        _hdf5_file_stem: Base name of the HDF5 file without extension
    """
    def __init__(self, hdf5_file_path: str) -> None:
        """
        Initialize a SingleFileExtractor for the specified HDF5 file.
        
        Args:
            hdf5_file_path: Path to the HDF5 file to extract data from
        """
        self._signals: List[Signal] = []
        self._hdf5_file_path = hdf5_file_path
        self._hdf5_file_name = Path(hdf5_file_path).name
        self._hdf5_file_stem = Path(hdf5_file_path).stem

        self._load_signals(hdf5_file_path)

    
    def _load_signals(self, file_path: str) -> None:
        """
        Load all signals from the HDF5 file.
        
        Args:
            file_path: Path to the HDF5 file
            
        Raises:
            FileNotFoundError: If the file doesn't exist or has no extension
        """
        try:
            with h5py.File(file_path, "r") as hdf:

                file_path = self._hdf5_file_path
                all_waves = hdf.get(f"waves")

                for wave in all_waves:
                    if not re.search(r"\.", wave):

                        index_data = hdf.get(f"waves/{wave}.index")
                        raw_data = np.array(hdf.get(f"waves/{wave}"))

                        raw_data[raw_data == -99999] = np.nan
                        

                        if index_data is None:
                            index_data = hdf[f"waves/{wave}"].attrs["index"]

                        for i,item in enumerate(index_data):
                            if i:
                                wave = f"{wave}_{i-1}"
                            self._signals.append(Signal(file_path, wave, 
                                                       item[0], item[1], item[2], 
                                                       item[3], raw_data))

        except FileNotFoundError:
            raise FileNotFoundError("No such file or the file is missing an extension.")
    
    def load_data(self, *segments: List[Segment]) -> None:
        """
        Load data for the given segments.
        
        Args:
            *segments: Variable number of segment lists to load data for
        """
        segments = [segment for sublist in segments for segment in sublist]
        segments_by_signal = defaultdict(list)
        for segment in segments:
            segments_by_signal[segment.signal_name].append(segment)

        for signal_name, segments in segments_by_signal.items():
            signal = next(signal for signal in self._signals if signal.signal_name == signal_name)
            signal.load_data(segments)
        
    @property
    def hdf5_file_stem(self) -> str:
        """Get the base name of the HDF5 file without extension."""
        return self._hdf5_file_stem
    
    def get_signal_names(self) -> List[str]:
        """
        Get the names of all signals in the file.
        
        Returns:
            List of signal names
        """
        return [signal.signal_name for signal in self._signals]
    
    
    def annotate(self, artf_file_path: str) -> None:
        """
        Annotate signals using an ARTF file.
        
        Args:
            artf_file_path: Path to the ARTF annotation file
            
        Raises:
            FileNotFoundError: If the ARTF file doesn't exist
            ValueError: If the ARTF file is not associated with the provided HDF5 file
        """
        try:
            with open(artf_file_path, "r", encoding="cp1250") as xml_file:
                tree = ET.parse(xml_file)
        except FileNotFoundError:
            raise FileNotFoundError("No such ARTF file found.")
        
        root = tree.getroot()

        annotator = root.find(".//Info").get("UserID")
        associated_hdf5 = root.find(".//Info").get("HDF5Filename")

        if not Path(associated_hdf5).name == self._hdf5_file_name:
            raise ValueError("The ARTF file is not associated with the provided HDF5 file.")

        for signal in self._signals:

            annotation_times = []

            for element in root.findall(".//Global/Artefact"):
                start_time_unix = unix_from_dt(element.get("StartTime"))
                end_time_unix = unix_from_dt(element.get("EndTime"))
                annotation_times.append((start_time_unix, end_time_unix))

            for element in root.findall(f".//SignalGroup[@Name='{signal.signal_name}']/Artefact"):
                start_time_unix = unix_from_dt(element.get("StartTime"))
                end_time_unix = unix_from_dt(element.get("EndTime"))
                annotation_times.append((start_time_unix, end_time_unix))
            
            signal.add_annotation(annotation_times, annotator)
    
    def auto_annotate(self, optional_folder_path: Optional[str] = None) -> None:
        """
        Automatically annotate signals using available ARTF files.
        
        Args:
            optional_folder_path: Optional path to look for ARTF files. If not provided,
                                  uses the directory containing the HDF5 file.
        """
        if not optional_folder_path:
            hdf5_dir = Path(self._hdf5_file_path).parent
        else:
            hdf5_dir = Path(optional_folder_path)

        artf_files = [file for file in hdf5_dir.rglob("*.artf")]

        for artf_file_path in artf_files:
            if any(part.startswith("__") for part in Path(artf_file_path).parts):
                continue

            with open(artf_file_path, "r", encoding="cp1250") as xml_file:
                tree = ET.parse(xml_file)
            root = tree.getroot()

            associated_hdf5 = root.find(".//Info").get("HDF5Filename")

            if Path(associated_hdf5).name == self._hdf5_file_name:
                self.annotate(artf_file_path)
    
    def get_raw_data(self, signal_name: str) -> np.ndarray:
        """
        Get raw data for a specific signal.
        
        Args:
            signal_name: Name of the signal to retrieve data for
            
        Raises:
            ValueError: If the signal name is not found in the signals
            
        Returns:
            Raw signal data as a numpy array
        """
        signal_name = str(signal_name).lower()
        if signal_name not in [signal.signal_name for signal in self._signals]:
            raise ValueError(f"Signal {signal_name} not present in the signals")

        data = {signal.signal_name: signal.raw_data for signal in self._signals}

        return data.get(signal_name)
    
    def get_annotations(self, signal_name: str) -> Dict[str, Annotation]:
        """
        Get annotations for a specific signal.
        
        Args:
            signal_name: Name of the signal to retrieve annotations for
            
        Raises:
            ValueError: If the signal name is not found in the signals
            
        Returns:
            Dictionary mapping annotation keys to Annotation objects
        """
        signal_name = str(signal_name).lower()
        if signal_name not in [signal.signal_name for signal in self._signals]:
            raise ValueError(f"Signal {signal_name} not present in the signals")
        
        annotations = {signal.signal_name: signal.annotations for signal in self._signals}
        signal_annotations = annotations.get(signal_name)
        
        return signal_annotations
    
    def get_annotators(self, signal_name: str) -> Set[str]:
        """
        Get all annotators for a specific signal.
        
        Args:
            signal_name: Name of the signal
            
        Raises:
            ValueError: If the signal name is not found in the signals
            
        Returns:
            Set of annotator names
        """
        signal_name = str(signal_name).lower()
        if signal_name not in [signal.signal_name for signal in self._signals]:
            raise ValueError(f"Signal {signal_name} not present in the signals")
        
        signal_annotations = next(signal.annotations for signal in self._signals if signal.signal_name == signal_name)
        annotators = {segment.annotators[0] for annotation in signal_annotations.values() for segment in annotation.good_segments + annotation.anomalies}
        
        return annotators
    
    def extract(self, signal_name: str) -> Tuple[List[Segment], List[Segment]]:
        """
        Extract good and anomalous segments for a given signal.

        If you wish to work with the data of the segments, call load_data() first.
        This ensures that you don't load any data into memory unless you need it.
        
        Args:
            signal_name: Name of the signal to extract segments for
            
        Raises:
            ValueError: If the signal name is not found in the signals
            
        Returns:
            Tuple containing lists of good segments and anomalous segments
        """
        signal_name = str(signal_name).lower()
        if signal_name not in [signal.signal_name for signal in self._signals]:
            raise ValueError(f"Signal {signal_name} not present in the signals")
        
        signal_annotations = next(signal.annotations for signal in self._signals if signal.signal_name == signal_name)
        
        segment_dict: Dict[str, Segment] = {}

        for annotation in signal_annotations.values():
            for segment in annotation.good_segments + annotation.anomalies:
                if segment.id in segment_dict:
                    segment_dict[segment.id].annotators.extend(segment.annotators)
                else:
                    segment_dict[segment.id] = Segment(
                        signal_name=segment.signal_name,
                        anomalous=segment.anomalous,
                        start_timestamp=segment.start_timestamp,
                        end_timestamp=segment.end_timestamp,
                        data_file=segment.data_file,
                        patient_id=segment.patient_id,
                        annotators=segment.annotators[:],
                        frequency=segment.frequency,
                        data=segment.data.copy(),
                        id=segment.id,
                        weight=segment.weight,
                        anomalies_annotations=segment.anomalies_annotations
                    )

        for segment in segment_dict.values():
            total_annotations = len(segment.annotators)
            anomalous_count = 0

            for annotation in signal_annotations.values():
                for seg in annotation.anomalies:
                    if segment.id == seg.id:
                        anomalous_count += 1
                        segment.anomalies_annotations.append(annotation.annotator)

            if total_annotations > 0:
                segment.weight = round(anomalous_count / total_annotations, 2)
                segment.anomalous = anomalous_count > 0
            
            if not segment.anomalous:
                segment.weight = 0.0

        good_segments = [segment for segment in segment_dict.values() if not segment.anomalous]
        anomalous_segments = [segment for segment in segment_dict.values() if segment.anomalous]
        return good_segments, anomalous_segments
    
    def describe(self) -> str:
        """
        Generate a detailed description of the file and its signals.
        
        Returns:
            A formatted string with information about the file and its signals
        """
        description = [f"\n~~Signal File Description~~\n"]
        description.append(f" File Name: {self._hdf5_file_stem}\n")

        for signal in self._signals:
            signal_info = f" Signal Name: {signal.signal_name}\n"
            signal_info += f"   Frequency: {signal.frequency} Hz\n"
            signal_info += f"   Start Time: {dt_from_unix(signal.starttime)}\n"
            signal_info += f"   End Time: {dt_from_unix(signal.starttime + int(signal.length * 1_000_000 / signal.frequency))}\n"
            signal_info += f"   Length: {(signal.length / signal.frequency / 3600):.2f}h ({signal.length} samples)\n"
            signal_info += f"   Annotated: {'Yes' if signal.annotated else 'No'}\n"


            if signal.annotated:
                annotations = signal.annotations
                for annotation_name, annotation in annotations.items():
                    signal_info += f"\n     {annotation_name} by {annotation.annotator} - Good Segments: {len(annotation.good_segments)}, Anomalies: {len(annotation.anomalies)}\n"

                    annotators, consensus_matrix = self.consensus_matrix(signal.signal_name)
                    annotator_index = annotators.index(annotation.annotator)
                    
                    for other_annotation_name, other_annotation in annotations.items():
                        if annotation_name != other_annotation_name:
                            other_annotator_index = annotators.index(other_annotation.annotator)
                            consensus_percentage = consensus_matrix[annotator_index, other_annotator_index] * 100
                            signal_info += f"       Consensus with {other_annotation_name}: {consensus_percentage:.2f}%\n"

            description.append(signal_info)

        return "\n".join(description)
    
    def consensus_matrix(self, signal_name: str, include_good: bool = True) -> Tuple[List[str], np.ndarray]:
        """
        Compute a consensus matrix between annotators for a signal.
        
        Args:
            signal_name: Name of the signal
            include_good: Whether to include good segments in the consensus calculation
            
        Returns:
            Tuple containing a list of annotator names and a consensus matrix
        """
        signal_annotations = self.get_annotations(signal_name)
        annotators = sorted({segment.annotators[0] for annotation in signal_annotations.values()
                            for segment in annotation.good_segments + annotation.anomalies})

        annotator_segments = {annotator: [] for annotator in annotators}
        for annotation in signal_annotations.values():
            annotator_segments[annotation.annotator].extend(annotation.good_segments + annotation.anomalies)

        consensus_matrix = np.zeros((len(annotators), len(annotators)))

        for i, annotator_i in enumerate(annotators):
            annotation_i = next(annotation for annotation in sorted(signal_annotations.values(), key=lambda a: a.annotator)
                                if annotation.annotator == annotator_i)
            
            for j, annotator_j in enumerate(annotators):
                annotation_j = next(annotation for annotation in sorted(signal_annotations.values(), key=lambda a: a.annotator)
                                    if annotation.annotator == annotator_j)

                if i == j:
                    consensus_matrix[i, j] = 1.0
                else:
                    consensus_segments = []

                    for segment in sorted(annotation_i.anomalies, key=lambda s: s.id):
                        for other_segment in sorted(annotation_j.anomalies, key=lambda s: s.id):
                            if segment.id == other_segment.id:
                                consensus_segments.append(segment)
                                break

                    if include_good:
                        other_segment_ids = {other_segment.id for other_segment in sorted(annotation_j.good_segments, key=lambda s: s.id)}
                        for segment in sorted(annotation_i.good_segments, key=lambda s: s.id):
                            if segment.id in other_segment_ids:
                                consensus_segments.append(segment)

                    total_segments_i = len(annotation_i.anomalies)
                    total_segments_j = len(annotation_j.anomalies)
                    if include_good:
                        total_segments_i += len(annotation_i.good_segments)
                        total_segments_j += len(annotation_j.good_segments)

                    intersection = len(consensus_segments)
                    union = total_segments_i + total_segments_j - intersection

                    if union == 0:
                        consensus_percentage = 1.0
                    else:
                        consensus_percentage = intersection / union

                    consensus_matrix[i, j] = consensus_percentage

        return annotators, consensus_matrix

    
    def annotated_anomalies(self, signal_name: str) -> Dict[str, int]:
        """
        Get the count of anomalies annotated by each annotator for a signal.
        
        Args:
            signal_name: Name of the signal
            
        Returns:
            Dictionary mapping annotator names to their anomaly counts
        """
        signal_annotations = self.get_annotations(signal_name)
        annotator_anomalies_count = defaultdict(int)
        for annotation in signal_annotations.values():
            for segment in annotation.anomalies:
                for annotator in segment.annotators:
                    annotator_anomalies_count[annotator] += 1
        return dict(annotator_anomalies_count)    
    
    def export_to_csv(self, optional_folder_path: Optional[str] = None) -> None:
        """
        Export data to CSV format.

        If the optional_folder_path is not provided, the current working directory will be used.
        If the optional_folder_path does not exist, it will be created.

        The name of the CSV files follows the format:
        <signal_name>_<weight>_<id>.csv

        Args:
            optional_folder_path: Optional path to save the file. If not provided,
                                  uses the current working directory.
        """
        if not optional_folder_path:
            working_dir = os.getcwd()
            optional_folder_path = working_dir
        else:
            if not os.path.exists(optional_folder_path):
                os.makedirs(optional_folder_path)
        
        for signal in self._signals:
            if not signal.annotated:
                print(f"Signal {signal.signal_name} is not annotated. If you wish to export it, call auto_annotate() first. Skipping...")
                continue
            
            good_segments, anomalous_segments = self.extract(signal.signal_name)

            self.load_data(good_segments, anomalous_segments)

            segments = good_segments + anomalous_segments
            for segment in segments:
                with open(os.path.join(optional_folder_path, f"{segment.signal_name}_{segment.weight}_{segment.id}.csv"), "w") as f:
                    timestamps = np.linspace(segment.start_timestamp, segment.end_timestamp, len(segment.data))
                    for timestamp, value in zip(timestamps, segment.data):
                        f.write(f"{int(timestamp)},{value}\n")

class FolderExtractor(IExtractor):
    """
    Extractor for processing a folder of HDF5 files with signals and annotations.
    
    This class handles loading, annotating, and extracting data from multiple HDF5 files
    in a specified folder path.
    
    Attributes:
        _folder_path: Path to the folder containing HDF5 files
        _extractors: List of SingleFileExtractor objects for each HDF5 file
    """
    def __init__(self, folder_path: str) -> None:
        """
        Initialize a FolderExtractor for the specified folder.
        
        Args:
            folder_path: Path to the folder containing HDF5 files
            
        Raises:
            ValueError: If the path is to a single HDF5 file instead of a folder
        """
        if folder_path.endswith(".hdf5"):
            raise ValueError("Please use SingleFileExtractor for single HDF5 files.")

        self._folder_path = folder_path
        self._extractors: List[SingleFileExtractor] = []

        self._load_files()
    
    def _load_files(self) -> None:
        """
        Load all HDF5 files in the folder and create extractors for each of them.
        """
        self._extractors = [
            SingleFileExtractor(os.path.join(root, file))
            for root, _, files in os.walk(self._folder_path)
            for file in files if file.endswith(".hdf5")
        ]
    
    def load_data(self, *segments: List[Segment]) -> None:
        """
        Load data for the given segments from their respective files.
        
        Args:
            *segments: Variable number of segment lists to load data for
        """
        segments = [segment for sublist in segments for segment in sublist]
        segments_by_file = defaultdict(list)
        for segment in segments:
            segments_by_file[segment.data_file].append(segment)

        for data_file, segments in segments_by_file.items():
            extractor = next(extractor for extractor in self._extractors if extractor._hdf5_file_path == data_file)
            extractor.load_data(segments)
    
    def auto_annotate(self, optional_folder_path: Optional[str] = None) -> None:
        """
        Automatically annotate signals in all files using available annotation files.
        
        Args:
            optional_folder_path: Optional path to look for annotation files. If not provided,
                                  uses the folder containing the HDF5 files.
        """
        if not optional_folder_path:
            optional_folder_path = self._folder_path

        for extractor in self._extractors:
            extractor.auto_annotate(optional_folder_path)
    
    def get_raw_data(self, signal_name: str) -> Dict[str, np.ndarray]:
        """
        Get raw data for a specific signal from all files.
        
        Args:
            signal_name: Name of the signal to retrieve data for
            
        Returns:
            Dictionary mapping file names to raw signal data arrays
        """
        data = {extractor.hdf5_file_stem: extractor.get_raw_data(signal_name) for extractor in self._extractors}

        return data
    
    def get_signal_names(self) -> Dict[str, Any]:
        """
        Get the names of all signals in all files, categorized as consistent and outliers.
        
        Returns:
            Dictionary with 'consistent' signals (present in all files) and 'outliers'
        """
        signals_dict = {extractor.hdf5_file_stem: extractor.get_signal_names() for extractor in self._extractors}
        consistent_signals = set.intersection(*[set(signals) for signals in signals_dict.values()])
        outliers = {extractor: list(set(signals_dict[extractor]) - consistent_signals) for extractor in signals_dict.keys() if set(signals_dict[extractor]) - consistent_signals}
        
        signals = {
            "consistent": list(consistent_signals),
            "outliers": outliers
        }
        return signals
    
    def get_files(self) -> List[str]:
        """
        Get the base names of all HDF5 files in the folder.
        
        Returns:
            List of file names without extensions
        """
        return [extractor.hdf5_file_stem for extractor in self._extractors]
    
    def get_annotations(self, signal_name: str) -> List[Dict[str, Annotation]]:
        """
        Get annotations for a specific signal from all files.
        
        Args:
            signal_name: Name of the signal to retrieve annotations for
            
        Returns:
            List of annotation dictionaries, one per file
        """
        annotations = [extractor.get_annotations(signal_name) for extractor in self._extractors]
        
        return annotations
    
    def get_annotators(self, signal_name: str) -> Dict[str, Any]:
        """
        Get all annotators for a specific signal, categorized as consistent and outliers.
        
        Args:
            signal_name: Name of the signal
            
        Returns:
            Dictionary with 'consistent' annotators (present in all files) and 'outliers'
        """
        annotators_dict = {extractor.hdf5_file_stem: extractor.get_annotators(signal_name) for extractor in self._extractors}
        consistent_annotators = set.intersection(*[set(annotators) for annotators in annotators_dict.values()])
        outliers = {extractor: list(set(annotators_dict[extractor]) - consistent_annotators) for extractor in annotators_dict.keys() if set(annotators_dict[extractor]) - consistent_annotators}
        
        annotators = {
            "consistent": list(consistent_annotators),
            "outliers": outliers
        }

        return annotators
    
    def extract(self, signal_name: str) -> Tuple[List[Segment], List[Segment]]:
        """
        Extract good and anomalous segments for a given signal from all files.
        
        Args:
            signal_name: Name of the signal to extract segments for
            
        Returns:
            Tuple containing lists of good segments and anomalous segments
        """
        good_segments: List[Segment] = []
        anomalous_segments: List[Segment] = []
        for extractor in self._extractors:
            try:
                good, an = extractor.extract(signal_name)
                good_segments.extend(good)
                anomalous_segments.extend(an)
            except ValueError as e:
                print(f"Skipping signal {signal_name} of {extractor.hdf5_file_stem}: {e}")
        
        segment_ids = set()
        duplicate_segments = []

        for segment in good_segments + anomalous_segments:
            if segment.id in segment_ids:
                duplicate_segments.append(segment)
            else:
                segment_ids.add(segment.id)

        if duplicate_segments:
            print(f"Found {len(duplicate_segments)} duplicate segments with the same ID.")
        
        return good_segments, anomalous_segments
    
    def describe(self, output_file: Optional[str] = None) -> str:
        """
        Generate a detailed description of all files and their signals.
        
        Args:
            output_file: Optional path to save the description to a file
            
        Returns:
            A formatted string with information about all files and their signals
        """
        description = []
        for extractor in self._extractors:
            description.append(extractor.describe())
        
        description_str = "\n".join(description)
        
        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            with open(output_file, mode="w", encoding="cp1250") as f:
                f.write(description_str)
        
        return description_str
    
    def consensus_matrix(self, signal_name: str, include_good: bool = True) -> Tuple[List[str], np.ndarray]:
        """
        Compute an average consensus matrix between annotators across all files.
        
        Args:
            signal_name: Name of the signal
            include_good: Whether to include good segments in the consensus calculation
            
        Returns:
            Tuple containing a list of annotator names and a consensus matrix
        """
        consensus_dict = defaultdict(list)
        
        for extractor in self._extractors:
            annotators, consensus_matrix = extractor.consensus_matrix(signal_name, include_good)
            for i, annotator_i in enumerate(annotators):
                for j, annotator_j in enumerate(annotators):
                    consensus_dict[(annotator_i, annotator_j)].append(consensus_matrix[i, j])
        
        mean_consensus_dict = {}
        for key, values in consensus_dict.items():
            mean_consensus_dict[key] = np.mean(values)
        
        unique_annotators = list(set([key[0] for key in mean_consensus_dict.keys()] + [key[1] for key in mean_consensus_dict.keys()]))
        unique_annotators.sort()
        
        consensus_matrix = np.full((len(unique_annotators), len(unique_annotators)), -1.0)
        
        for (annotator_i, annotator_j), mean_value in mean_consensus_dict.items():
            i = unique_annotators.index(annotator_i)
            j = unique_annotators.index(annotator_j)
            consensus_matrix[i, j] = mean_value
        
        return unique_annotators, consensus_matrix
    
    def annotated_anomalies(self, signal_name: str) -> Dict[str, int]:
        """
        Get the total count of anomalies annotated by each annotator across all files.
        
        Args:
            signal_name: Name of the signal
            
        Returns:
            Dictionary mapping annotator names to their total anomaly counts
        """
        final_count = defaultdict(int)
        for extractor in self._extractors:
            extractor_anomalies = extractor.annotated_anomalies(signal_name)
            for annotator, count in extractor_anomalies.items():
                final_count[annotator] += count
        return dict(final_count)
    
    def export_to_csv(self, folder_path: str) -> None:
        """
        Export data from all files to separate CSV files.
        
        Args:
            optional_folder_path: Optional path to save the CSV files. If not provided,
                                  uses the folder containing the HDF5 files.
        """
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        for extractor in tqdm.tqdm(self._extractors, desc="Exporting segments to CSV"):
            extractor.export_to_csv(folder_path)


if __name__ == "__main__":
    """
    Main execution block for testing the loader functionality.
    
    This section demonstrates how to use the FolderExtractor to:
    1. Load a dataset from a folder
    2. Auto-annotate signals using annotation files
    3. Extract and load segments
    4. Access segment weights and descriptions
    """
    # Example usage of the FolderExtractor
    dataset_path: str = "/media/DATA/data/DATASETS/2024-05-10/dataset_0/TBI_011_v2_2_1_22.hdf5"
    annotations_path: str = "/media/DATA/revised_annotations"
    
    # Create a FolderExtractor for the dataset
    ex: IExtractor = SingleFileExtractor(dataset_path)
    
    # Auto-annotate using annotation files from a specific path
    ex.auto_annotate(annotations_path)
    
    # Extract good and anomalous segments for the 'icp' signal
    good_segments, anomalous_segments = ex.extract(signal_name="icp")

    ex.load_data(anomalous_segments, good_segments)

    print(f"Found {len(good_segments)} good segments and {len(anomalous_segments)} anomalous segments")

    ex.export_to_csv("output23")

    # Display segment weights sorted in descending order
    print(f"Segment weights (sorted): {sorted([seg.weight for seg in anomalous_segments], reverse=True)}")
    
    # Print a detailed description of the third-to-last anomalous segment
    print(anomalous_segments[-5].describe())

