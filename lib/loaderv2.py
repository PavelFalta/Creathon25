"""
v2.0

Developed by The Laboratory of Data Analysis and Simulations.

More information at odas.ujep.cz

"""


import datetime
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List
import csv
import h5py
import numpy as np
import hashlib
from abc import ABC, abstractmethod
from collections import defaultdict


def unix_from_dt(dt_string: str) -> int:
    """Converts a datetime string to a Unix timestamp in microseconds."""
    return int(datetime.datetime.strptime(dt_string, "%d/%m/%Y %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).timestamp() * 1_000_000)

def dt_from_unix(unix: int) -> str:
    """Converts a Unix timestamp in microseconds to a datetime string."""
    return datetime.datetime.fromtimestamp(unix / 1_000_000, tz=datetime.timezone.utc).strftime("%d/%m/%Y %H:%M:%S.%f")[:-4]

class IExtractor(ABC):
    @abstractmethod
    def get_raw_data(self, mode):
        pass

    @abstractmethod
    def get_modes(self):
        pass

    @abstractmethod
    def get_annotations(self, mode):
        pass

    @abstractmethod
    def export_to_folder(self, output_dir):
        pass

    @abstractmethod
    def describe(self):
        pass

    @abstractmethod
    def auto_annotate(self, optional_folder_path = None):
        pass

    @abstractmethod
    def extract(self, mode):
        pass
    
    @abstractmethod
    def load_data(self, segments):
        pass

@dataclass
class Segment:
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
    anomalies_annotations: list[str]


    def describe(self):
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
                "Mean": np.mean(data),
                "Standard Deviation": np.std(data),
                "Min": np.min(data),
                "25th Percentile": np.percentile(data, 25),
                "Median": np.percentile(data, 50),
                "75th Percentile": np.percentile(data, 75),
                "Max": np.max(data)
            }
            data_summary = description["Data Summary"]
            description_str += f"\n\nData Summary:\n"
            description_str += "\n".join([f"   {key}: {value}" for key, value in data_summary.items()])
        
        return description_str

@dataclass
class Annotation:
    good_segments: List[Segment]
    anomalies: List[Segment]
    annotator: str

class Signal:
    def __init__(self, file_path, signal_name, startidx, starttime, length, frequency, raw_data):
        self._file_path = file_path
        self._startidx = startidx
        self._starttime = starttime
        self._length = length
        self._frequency = frequency
        self._signal_name = signal_name
        self._raw_data = raw_data
        self._annotations = {}

    
    def add_annotation(self, annotation_times_list, annotator):
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


        good_segments = []
        anomalous_segments = []

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
                    data=[],
                    id=id,
                    weight=0.0,
                    anomalies_annotations = []

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
                    data=[],
                    id=id,
                    weight=0.0,
                    anomalies_annotations=[]
                )

                good_segments.append(segment_obj)

        annotation_idx = f"Annotation n. {len(self._annotations)}"

        self._annotations[annotation_idx] = Annotation(good_segments=good_segments, anomalies=anomalous_segments, annotator=annotator)
    
    def load_data(self, segments):
        for segment in segments:
            segment_start_idx = int((segment.start_timestamp - self._starttime) // 1_000_000 * self._frequency)
            segment_end_idx = int((segment.end_timestamp - self._starttime) // 1_000_000 * self._frequency) + 1
            segment.data = self._raw_data[segment_start_idx:segment_end_idx]
    
    @property
    def frequency(self):
        return self._frequency
    
    @property
    def signal_name(self):
        return self._signal_name
    
    @property
    def length(self):
        return self._length
    
    @property
    def starttime(self):
        return self._starttime
    
    @property
    def raw_data(self):
        return self._raw_data
    
    @property
    def annotations(self):
        if not self._annotations:
            raise ValueError("This signal has yet to be annotated.")
        return self._annotations
    
    @property
    def annotated(self):
        if not self._annotations:
            return False
        return True
    
class SingleFileExtractor(IExtractor):
    def __init__(self, hdf5_file_path):
        self._signals: List[Signal] = []
        self._hdf5_file_path = hdf5_file_path
        self._hdf5_file_name = Path(hdf5_file_path).name
        self._hdf5_file_stem = Path(hdf5_file_path).stem

        self._load_signals(hdf5_file_path)

    
    def _load_signals(self, file_path):
        try:
            with h5py.File(file_path, "r") as hdf:

                file_path = self._hdf5_file_path
                all_waves = hdf.get(f"waves")
                # data = hdf["summaries"]["minutes"]
                # print(data.dtype.names)
                # column_names = data.dtype.names
                # data_dict = {col: data[col] for col in column_names}
                # print(data_dict, data.dtype.names)
                # data = data_dict["PRx"]
                # # Drop NaNs at the start and end of the data

                # #visualize in plotly
                # self.prx = data
                # # fig = px.line(y = data)

                # # fig.show()


                for wave in all_waves:
                    if not re.search(r"\.", wave):

                        index_data = hdf.get(f"waves/{wave}.index")
                        raw_data = np.array(hdf.get(f"waves/{wave}"))
                        #replace all -99999 with nan
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
    
    def load_data(self, *segments):
        segments = [segment for sublist in segments for segment in sublist]
        segments_by_signal = defaultdict(list)
        for segment in segments:
            segments_by_signal[segment.signal_name].append(segment)

        for signal_name, segments in segments_by_signal.items():
            signal = next(signal for signal in self._signals if signal.signal_name == signal_name)
            signal.load_data(segments)
        
    @property
    def hdf5_file_stem(self):
        return self._hdf5_file_stem
    
    def get_modes(self):
        return [signal.signal_name for signal in self._signals]
    
    
    def annotate(self, artf_file_path):
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
    
    def auto_annotate(self, optional_folder_path = None):
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
    
    def get_raw_data(self, mode):
        mode = str(mode).lower()
        if mode not in [signal.signal_name for signal in self._signals]:
            raise ValueError(f"Mode {mode} not present in the signals")

        data = {signal.signal_name: signal.raw_data for signal in self._signals}

        return data.get(mode)
    
    def get_annotations(self, mode):
        mode = str(mode).lower()
        if mode not in [signal.signal_name for signal in self._signals]:
            raise ValueError(f"Mode {mode} not present in the signals")
        
        annotations = {signal.signal_name: signal.annotations for signal in self._signals}
        mode_annotations = annotations.get(mode)
        
        return mode_annotations
    
    def get_annotators(self, mode):
        mode = str(mode).lower()
        if mode not in [signal.signal_name for signal in self._signals]:
            raise ValueError(f"Mode {mode} not present in the signals")
        
        mode_annotations = next(signal.annotations for signal in self._signals if signal.signal_name == mode)
        annotators = {segment.annotators[0] for annotation in mode_annotations.values() for segment in annotation.good_segments + annotation.anomalies}
        
        return annotators
    
    def extract(self, mode):
        mode = str(mode).lower()
        if mode not in [signal.signal_name for signal in self._signals]:
            raise ValueError(f"Mode {mode} not present in the signals")
        
        mode_annotations = next(signal.annotations for signal in self._signals if signal.signal_name == mode)
        
        segment_dict = {}

        for annotation in mode_annotations.values():
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

            for annotation in mode_annotations.values():
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
    
    def describe(self):
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
    
    def export_to_folder(self, output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        first_row_set = set()
        
        for signal in self._signals:
            if signal.annotated:
                annotations = signal.annotations
                for annotation_name, annotation in annotations.items():
                    with open(f"{output_dir}/{annotation_name}.csv", mode="a",encoding="cp1250", newline="") as csvfile:
                        writer = csv.writer(csvfile)
                        if annotation_name not in first_row_set:
                            writer.writerow(["signal_name", "anomalous", "start_timestamp", "end_timestamp", "data_file", "patient_id", "annotators", "frequency", "data", "id"])
                            first_row_set.add(annotation_name)
                        for segment in annotation.good_segments + annotation.anomalies:
                            writer.writerow([segment.signal_name, segment.anomalous, segment.start_timestamp, segment.end_timestamp, segment.data_file, segment.patient_id, segment.annotators, segment.frequency, segment.data, segment.id])
            else:
                print(f"The export of {self._hdf5_file_stem} has been skipped as it is not annotated.")
    
    def consensus_matrix(self, mode, include_good=True):
        mode_annotations = self.get_annotations(mode)
        annotators = sorted({segment.annotators[0] for annotation in mode_annotations.values()
                            for segment in annotation.good_segments + annotation.anomalies})

        annotator_segments = {annotator: [] for annotator in annotators}
        for annotation in mode_annotations.values():
            annotator_segments[annotation.annotator].extend(annotation.good_segments + annotation.anomalies)

        consensus_matrix = np.zeros((len(annotators), len(annotators)))

        for i, annotator_i in enumerate(annotators):
            annotation_i = next(annotation for annotation in sorted(mode_annotations.values(), key=lambda a: a.annotator)
                                if annotation.annotator == annotator_i)
            
            for j, annotator_j in enumerate(annotators):
                annotation_j = next(annotation for annotation in sorted(mode_annotations.values(), key=lambda a: a.annotator)
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

    
    def annotated_anomalies(self, mode):
        mode_annotations = self.get_annotations(mode)
        annotator_anomalies_count = defaultdict(int)
        for annotation in mode_annotations.values():
            for segment in annotation.anomalies:
                for annotator in segment.annotators:
                    annotator_anomalies_count[annotator] += 1
        return dict(annotator_anomalies_count)
    

    def compute_cohen_kappa(self, mode):
        """
        Computes Cohen's Kappa score for the specified mode between all pairs of annotators.
        """
        raise NotImplementedError("This method is not yet implemented.")
        


class FolderExtractor(IExtractor):
    def __init__(self, folder_path):
        if folder_path.endswith(".hdf5"):
            raise ValueError("Please use SingleFileExtractor for single HDF5 files.")

        self._folder_path = folder_path
        self._extractors = []

        self._load_files()
    
    def _load_files(self):
        self._extractors = [
            SingleFileExtractor(os.path.join(root, file))
            for root, _, files in os.walk(self._folder_path)
            for file in files if file.endswith(".hdf5")
        ]
    
    def load_data(self, *segments):
        segments = [segment for sublist in segments for segment in sublist]
        segments_by_file = defaultdict(list)
        for segment in segments:
            segments_by_file[segment.data_file].append(segment)

        for data_file, segments in segments_by_file.items():
            extractor = next(extractor for extractor in self._extractors if extractor._hdf5_file_path == data_file)
            extractor.load_data(segments)
    
    def auto_annotate(self, optional_folder_path = None):
        if not optional_folder_path:
            optional_folder_path = self._folder_path

        for extractor in self._extractors:
            extractor.auto_annotate(optional_folder_path)
    
    def get_raw_data(self, mode):

        data = {extractor.hdf5_file_stem: extractor.get_raw_data(mode) for extractor in self._extractors}

        return data
    
    def get_modes(self):
        modes_dict = {extractor.hdf5_file_stem: extractor.get_modes() for extractor in self._extractors}
        consistent_modes = set.intersection(*[set(modes) for modes in modes_dict.values()])
        outliers = {extractor: list(set(modes_dict[extractor]) - consistent_modes) for extractor in modes_dict.keys() if set(modes_dict[extractor]) - consistent_modes}
        
        modes = {
            "consistent": list(consistent_modes),
            "outliers": outliers
        }
        return modes
    
    def get_files(self):
        return [extractor.hdf5_file_stem for extractor in self._extractors]
    
    def get_annotations(self, mode):
            
        annotations = [extractor.get_annotations(mode) for extractor in self._extractors]
        
        return annotations
    
    def get_annotators(self, mode):
        annotators_dict = {extractor.hdf5_file_stem: extractor.get_annotators(mode) for extractor in self._extractors}
        consistent_annotators = set.intersection(*[set(annotators) for annotators in annotators_dict.values()])
        outliers = {extractor: list(set(annotators_dict[extractor]) - consistent_annotators) for extractor in annotators_dict.keys() if set(annotators_dict[extractor]) - consistent_annotators}
        
        annotators = {
            "consistent": list(consistent_annotators),
            "outliers": outliers
        }

        return annotators
    
    def extract(self, mode):
        good_segments = []
        anomalous_segments = []
        for extractor in self._extractors:
            try:
                good, an = extractor.extract(mode)
                good_segments.extend(good)
                anomalous_segments.extend(an)
            except ValueError as e:
                print(f"Skipping mode {mode} of {extractor.hdf5_file_stem}: {e}")
        
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

    def export_to_folder(self, output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        for extractor in self._extractors:
            extractor.export_to_folder(Path(output_dir) / extractor.hdf5_file_stem)
    
    def describe(self, output_file=None):
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
    
    def consensus_matrix(self, mode, include_good=True):
        consensus_dict = defaultdict(list)
        
        for extractor in self._extractors:
            annotators, consensus_matrix = extractor.consensus_matrix(mode, include_good)
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
        
        # np.fill_diagonal(consensus_matrix, 1.0)
        
        return unique_annotators, consensus_matrix
    
    def annotated_anomalies(self, mode):
        final_count = defaultdict(int)
        for extractor in self._extractors:
            extractor_anomalies = extractor.annotated_anomalies(mode)
            for annotator, count in extractor_anomalies.items():
                final_count[annotator] += count
        return dict(final_count)
    
    def compute_cohen_kappa(self, mode):
        """
        Aggregates Cohen's Kappa scores across all files for the specified mode.
        """
        aggregated_scores = defaultdict(list)
        for extractor in self._extractors:
            try:
                kappa_scores = extractor.compute_cohen_kappa(mode)
                for annotator_pair, score in kappa_scores.items():
                    if score is not None:
                        aggregated_scores[annotator_pair].append(score)
            except ValueError as e:
                print(f"Skipping mode {mode} for {extractor.hdf5_file_stem}: {e}")

        
        average_scores = {pair: np.mean(scores) for pair, scores in aggregated_scores.items()}

        return average_scores

if __name__ == "__main__":
    ex = FolderExtractor("/media/pavel/DATA/data/DATASETS/2024-05-10/dataset_0")
    
    
    
    ex.auto_annotate()
    
    


    good, an = ex.extract(mode="icp")
    print(len(good), len(an))
    ex.load_data(an)

    print(sorted([seg.weight for seg in an], reverse=True))
    print(an[-3].describe())

