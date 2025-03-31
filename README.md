# Creathon HDF5 Utils

> **TLDR**: The library follows a simple workflow: initialize an extractor → load annotations → extract segments → load data → process/export. See [General Dataflow](#general-dataflow) for a quick start.

A Python toolkit for processing, analyzing and annotating biomedical signal data stored in HDF5 + ARTF files for segment extraction.

![Example Segment](screenshots/example.png)

> **Note for non-Python users**: If you prefer not to code in Python, you can use the `export.py` script to export all segments to CSV format, which can then be imported into any data analysis tool of your choice. See the [export.py](#exportpy) section for details.

## Features

- Load and process biomedical signals from HDF5 files
- Extract annotated anomalous and normal signal segments
- Work with single files or entire directories of data
- Export data to CSV for use in other tools and languages
- Compute consensus between different annotators

## Installation (Linux/MacOS)
**Python 3.9+ is required**

1. Clone and enter the repository:
```bash
git clone https://github.com/PavelFalta/Creathon25.git
cd Creathon25
```

2. Create and activate Python virtualenv:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Installation (Windows)
**Python 3.9+ is required**

1. Clone and enter the repository:
```
git clone https://github.com/PavelFalta/Creathon25.git
cd Creathon25
```

2. Create and activate Python virtual environment:
```
python -m venv .venv
.venv\Scripts\activate
```

3. Install the required dependencies:
```
pip install -r requirements.txt
```

## Core Concepts

### Signal Data

Raw signals are stored in HDF5 files. When a signal is annotated, it is split into segments of 10 seconds. Each segment is given a label based on whether an anomaly is present in the segment. 

### Annotations

The anomaly information is stored in a separate XML file with the same name as the HDF5 file, but with an `.artf` extension. These files follow a structured XML format (see ARTF File Format section).

### Extractors

The library provides two main classes for working with signal data:

- `SingleFileExtractor`: For processing a single HDF5 file with its corresponding `.artf` file
- `FolderExtractor`: For processing multiple HDF5 files in a directory

### Segment Structure

Each extracted segment is represented by a `Segment` dataclass with the following attributes:

```python
@dataclass
class Segment:
    # Basic information
    signal_name: str         # Name of the signal this segment belongs to
    patient_id: str          # Identifier of the patient this segment belongs to
    frequency: float         # Sampling frequency of the signal in Hz
    
    # Timing information
    start_timestamp: int     # Start time in microseconds (Unix timestamp)
    end_timestamp: int       # End time in microseconds (Unix timestamp)
    
    # Data and file information
    data: np.ndarray        # Array of signal values (empty until load_data is called)
    data_file: str          # Path to the file containing the segment data
    
    # Annotation information
    anomalous: bool         # Boolean indicating if this segment contains an anomaly
    annotators: List[str]   # List of annotators who have annotated this segment
    anomalies_annotations: List[str]  # List of annotators who marked this segment as anomalous
    weight: float           # Weight value representing annotator consensus (0.0-1.0)
    
    # Metadata
    id: str                 # Unique identifier for the segment
```

The `Segment` class provides a `describe()` method that returns a formatted string with segment information. This can for example be used for feature extraction:

```python
print(segment.describe())
# Output example:
# Signal Name: art
# Patient ID: patient_001
# Annotators: annotator1, annotator2
# Frequency (Hz): 125.0
# Start Time: 2024-01-01 12:00:00
# End Time: 2024-01-01 12:00:10
# Duration (s): 10.0
# Anomalous: True
# Data Loaded: True
#
# Data Summary:
#    Count: 1250
#    NaN Count: 0
#    Mean: 120.5
#    Standard Deviation: 5.2
#    Min: 110.0
#    25th Percentile: 116.0
#    Median: 120.0
#    75th Percentile: 125.0
#    Max: 130.0
```

## Example Usage

### General Dataflow

When working with the library, you typically follow these steps:

1. **Initialize an Extractor**
   ```python
   from lib.loader import SingleFileExtractor, FolderExtractor

   # For single file
   extractor = SingleFileExtractor("path/to/file.hdf5")
   
   # Or for multiple files
   extractor = FolderExtractor("path/to/directory/")
   ```

2. **Load Annotations**
   ```python
   # Automatically find and load annotations in the parent folder.
   # If you wish to annotate with files from elsewhere, you will need to supply the folder path.
   extractor.auto_annotate()
   ```

3. **Extract Segments**
   ```python
   # Get segments for a specific signal
   good_segments, anomalous_segments = extractor.extract("signal_name")
   ```

4. **Load Data** (if needed)
   ```python
   # Load actual signal data for segments.
   # If you don't load the data, you will have empty arrays instead of the data. This is done so that you only load the actual data you need into memory.
   extractor.load_data(good_segments, anomalous_segments)
   ```

5. **Process or Export**
   ```python
   # Export to CSV
   extractor.export_to_csv("output_directory")
   
   # Or work with segments directly
   for segment in segments:
       # Process segment.data
       pass
   ```

### Working with a Single File

```python
from lib.loader import SingleFileExtractor
import matplotlib.pyplot as plt
import numpy as np

# Load and process a single HDF5 file
extractor = SingleFileExtractor("example_data/TBI_example.hdf5")

# Automatically find and apply annotations
extractor.auto_annotate()

# Extract good and anomalous segments for the "art" signal
good_segments, anomalous_segments = extractor.extract("art")

# Print information about the segments
print(f"Normal: {len(good_segments)} Anomalies: {len(anomalous_segments)}")
print(f"The data is {len(anomalous_segments) / (len(good_segments) + len(anomalous_segments)) * 100:.2f}% anomalous")

# Load data for a specific segment
segment = anomalous_segments[0]
extractor.load_data([segment])

# Display information about the signal and segment
print(extractor.describe())
print(segment.describe())

# Plot the segment
plt.figure(figsize=(12, 6))
plt.plot(segment.data)
plt.title(f"ABP Anomalous Segment")
plt.ylabel("mmHg")
plt.xlabel("Time (s)")
sr = segment.frequency
xticks = np.arange(0, len(segment.data) + 1, sr)
xlabels = [f"{(tick/sr):.1f}" for tick in xticks]
plt.xticks(xticks, xlabels)
plt.grid(True, alpha=0.3)
plt.show()
```

### Working with Multiple Files

```python
from lib.loader import FolderExtractor
import matplotlib.pyplot as plt

# Load all HDF5 files in a directory
extractor = FolderExtractor("example_data/")

# Automatically find and apply annotations
extractor.auto_annotate()

# Extract all segments from all files for the "art" signal
good_segments, anomalous_segments = extractor.extract("art")

# Display information about all segments
print(f"Normal: {len(good_segments)} Anomalies: {len(anomalous_segments)}")
print(f"The data is {len(anomalous_segments) / (len(good_segments) + len(anomalous_segments)) * 100:.2f}% anomalous")

# Load and display a specific segment
segment = anomalous_segments[-1]
extractor.load_data([segment])
print(segment.describe())

# Plot the segment
plt.figure(figsize=(12, 6))
plt.plot(segment.data)
plt.title(f"ABP Anomalous Segment - Patient {segment.patient_id}")
plt.ylabel("mmHg")
plt.xlabel("Sample")
plt.grid(True, alpha=0.3)
plt.show()
```

### Exporting Data to CSV

```python
from lib.loader import SingleFileExtractor

# Load an HDF5 file
extractor = SingleFileExtractor("example_data/TBI_example.hdf5")
extractor.auto_annotate()

# Export data to CSV
extractor.export_to_csv("output_directory")
```

## Or for folder export

```python
from lib.loader import FolderExtractor

# Load an HDF5 file
extractor = FolderExtractor("example_data/")
extractor.auto_annotate()

# Export data to CSV
extractor.export_to_csv("output_directory")
```

## Command-line Tools

The repository includes several command-line tools:

### anomalies.py
Display information about anomalies in an HDF5 file:

```bash
python anomalies.py -f example_data/TBI_example.hdf5 -s art
```

This tool:
- Lists all anomalous segments for a specific signal
- Shows start times, durations, and weights of anomalies
- Provides statistics about annotators

### info.py
Displays comprehensive information about signals in an HDF5 file:

```bash
python info.py -f example_data/TBI_example.hdf5
```

This tool:
- Lists all available signals in the file
- Shows signal properties (frequency, duration, start/end times)
- Provides statistics about signal values
- Summarizes annotation information if available

### export.py
Extracts segments from the entire dataset and exports them to CSV. You need to supply folder path and path to a folder with annotations:

```bash
python export.py -f example_data/ -a example_data/ -o out
```

This tool:
- Extracts both normal and anomalous segments of all signals in the following format:
```
<signal_name>_<weight>_<id>.csv
```

## Notes

- Signal names can vary between files. ABP may be stored as `art` or `abp` in the HDF5 file.
- The library automatically handles NaN values and missing data points.
- You can add multiple annotations from different annotators to the same signal.

## Further Resources

For detailed API documentation, see the docstrings in the source code files.

---

Developed by The Laboratory of Data Analysis and Simulations.  
More information at [odas.ujep.cz](http://odas.ujep.cz)


