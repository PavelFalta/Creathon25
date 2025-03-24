"""
Single File Example - Demonstrating how to use the SingleFileExtractor class

This script shows how to:
1. Load a single HDF5 file
2. Auto-annotate using the corresponding ARTF file
3. Extract good and anomalous segments
4. Load and visualize segments
"""

from lib.loader import SingleFileExtractor
import matplotlib.pyplot as plt
import numpy as np


# Create a SingleFileExtractor for the example file
extractor = SingleFileExtractor("example_data/TBI_example.hdf5")

# Apply annotations from the .artf file (auto-detected)
extractor.auto_annotate()

# Get the available signal names
signal_names = extractor.get_signal_names()
print(f"Available signals: {signal_names}")

# Extract the arterial signal (could be 'art' or 'abp' depending on the file)
signal_name = 'art'  # Use the name that matches your data
good_segments, anomalous_segments = extractor.extract(signal_name)

# Print summary statistics
print(f"Normal segments: {len(good_segments)}")
print(f"Anomalous segments: {len(anomalous_segments)}")
print(f"Anomaly rate: {len(anomalous_segments) / (len(good_segments) + len(anomalous_segments)) * 100:.2f}%")

# Load data for the first anomalous segment (if any exist)
if anomalous_segments:
    # Select the first anomalous segment
    segment = anomalous_segments[0]
    
    # Load the actual data (only loads what we need)
    extractor.load_data([segment])
    
    # Print detailed information about the file and segment
    print("\nFile Description:")
    print(extractor.describe())
    
    print("\nSegment Description:")
    print(segment.describe())

    # Plot the segment with proper time axis
    plt.figure(figsize=(12, 6))
    plt.plot(segment.data)
    plt.title(f"{signal_name.upper()} Anomalous Segment")
    plt.ylabel("mmHg")
    plt.xlabel("Time (s)")
    
    # Set up time-based x-axis labels
    sr = segment.frequency
    xticks = np.arange(0, len(segment.data) + 1, sr)
    xlabels = [f"{(tick/sr):.1f}" for tick in xticks]
    plt.xticks(xticks, xlabels)
    
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
else:
    print("No anomalous segments found.")
    
    # If no anomalous segments, show a normal segment instead
    if good_segments:
        segment = good_segments[0]
        extractor.load_data([segment])
        
        plt.figure(figsize=(12, 6))
        plt.plot(segment.data)
        plt.title(f"{signal_name.upper()} Normal Segment")
        plt.ylabel("mmHg")
        plt.xlabel("Time (s)")
        
        sr = segment.frequency
        xticks = np.arange(0, len(segment.data) + 1, sr)
        xlabels = [f"{(tick/sr):.1f}" for tick in xticks]
        plt.xticks(xticks, xlabels)
        
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
    else:
        print("No segments found. Check if annotation file exists and is valid.")

