# Creathon HDF5 Utils

A Python toolkit for processing, analyzing and annotating biomedical signal data stored in HDF5 + ARTF files for segment extraction.

![Example Segment](screenshots/example.png)

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
cd creathon
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
cd creathon
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

## Example Usage

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

The repository includes several command-line tools for common tasks:

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

### extract.py
Extracts signal segments from the entire dataset and exports them to CSV. You need to supply folder path and path to a folder with annotations:

```bash
python extract.py -f example_data/ -a example_data/ -o out
```

This tool:
- Extracts both normal and anomalous segments
- Can balance the dataset by limiting the number of samples per class
- Supports multiple output formats (NumPy text files, CSV)

## ARTF File Format

The ARTF file uses XML format to store anomaly annotations:

```xml
<?xml version="1.0" ?>
<ICMArtefacts>
    <Global>
        <Artefact StartTime="01/01/1970 00:00:05.000"
                  EndTime="01/01/1970 00:00:15.000"/>
    </Global>

    <SignalGroup Name="icp">
        <Artefact StartTime="01/01/1970 00:00:15.000"
                  EndTime="01/01/1970 00:00:25.000"/>
    </SignalGroup>

    <SignalGroup Name="art">
        <Artefact StartTime="01/01/1970 00:00:25.000"
                  EndTime="01/01/1970 00:00:35.000"/>
    </SignalGroup>

    <Info HDF5Filename="example.hdf5" UserID="annotator1"/>
</ICMArtefacts>
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


