"""
Folder Example - Demonstrating how to use the FolderExtractor class

This script shows how to:
1. Load multiple HDF5 files from a directory
2. Auto-annotate using the corresponding ARTF files
3. Extract segments from all files
4. Analyze cross-file statistics and consensus
"""

from lib.loader import FolderExtractor
import matplotlib.pyplot as plt
import numpy as np
import os

# Create a FolderExtractor for the example data directory
extractor = FolderExtractor("example_data/")

# Print the available files
print(f"Loaded files: {extractor.get_files()}")

# Automatically find and apply annotations from .artf files
extractor.auto_annotate()

# Get the names of signals consistent across all files
signal_info = extractor.get_signal_names()
print(f"Consistent signals across all files: {signal_info['consistent']}")
if signal_info['outliers']:
    print("Signals present in only some files:")
    for file, signals in signal_info['outliers'].items():
        print(f"  {file}: {signals}")

# Extract segments for a specific signal (e.g., 'art' or 'abp')
signal_name = 'art'  # Use the appropriate signal name for your files
good_segments, anomalous_segments = extractor.extract(signal_name)

# Print segment statistics
print(f"Total normal segments: {len(good_segments)}")
print(f"Total anomalous segments: {len(anomalous_segments)}")
print(f"Anomaly rate: {len(anomalous_segments) / (len(good_segments) + len(anomalous_segments)) * 100:.2f}%")

# Get counts of anomalies annotated by each annotator
anomaly_counts = extractor.annotated_anomalies(signal_name)
print("\nAnomalies by annotator:")
for annotator, count in anomaly_counts.items():
    print(f"  {annotator}: {count}")

# If there are anomalous segments, load and plot one
if anomalous_segments:
    # Select the last anomalous segment
    segment = anomalous_segments[-1]
    
    # Load the actual data (only loads what we need)
    extractor.load_data([segment])
    
    # Print segment details
    print(f"\nSegment from patient {segment.patient_id}:")
    print(segment.describe())
    
    # Plot the segment
    plt.figure(figsize=(12, 6))
    plt.plot(segment.data)
    plt.title(f"{signal_name.upper()} Anomalous Segment - Patient {segment.patient_id}")
    plt.ylabel("mmHg")
    plt.xlabel("Time (s)")
    
    # Add time-based x-axis labels if available
    sr = segment.frequency
    if sr > 0:
        xticks = np.arange(0, len(segment.data) + 1, sr)
        xlabels = [f"{(tick/sr):.1f}" for tick in xticks]
        plt.xticks(xticks, xlabels)
    
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
else:
    print("No anomalous segments found across all files.")
