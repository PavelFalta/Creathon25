#!/usr/bin/env python3
"""
Anomalies Tool - Displays information about anomalies in HDF5 files

This script lists all anomalies present in a given HDF5 file for a specific signal,
including their start times, durations, and annotators.
"""

from lib.loader import SingleFileExtractor
import datetime
import argparse
from pathlib import Path


def main(args):
    hdf5_filepath = args.f
    signal_name = args.s
    
    print(f"Analyzing file: {Path(hdf5_filepath).name}")
    print(f"Signal: {signal_name}")
    print("-" * 60)
    
    # Create an extractor for the file
    extractor = SingleFileExtractor(hdf5_filepath)
    
    # Check if the signal exists in the file
    available_signals = extractor.get_signal_names()
    print(f"Available signals: {', '.join(available_signals)}")
    
    if signal_name not in available_signals:
        print(f"\nERROR: Signal '{signal_name}' not found in file!")
        print(f"Please choose one of: {', '.join(available_signals)}")
        return

    # Apply annotations from the .artf file
    extractor.auto_annotate()
    
    # Extract only anomalous segments
    _, anomalous_segments = extractor.extract(signal_name)
    
    print(f"\nFound {len(anomalous_segments)} anomalous segments")
    
    # Get annotator statistics
    annotator_counts = extractor.annotated_anomalies(signal_name)
    if annotator_counts:
        print("\nAnnotators:")
        for annotator, count in annotator_counts.items():
            print(f"  {annotator}: {count} anomalies")
    
    # Sort segments by start time
    anomalous_segments.sort(key=lambda x: x.start_timestamp)
    
    # Display anomalies
    if anomalous_segments:
        print("\nAnomaly details:")
        print(f"{'Index':>5} | {'Start Time':^25} | {'Duration':>10} | {'Weight':>8} | {'Patient ID':>10}")
        print("-" * 70)
        
        for i, segment in enumerate(anomalous_segments):
            # Convert microsecond timestamp to datetime
            dt = datetime.datetime.fromtimestamp(
                segment.start_timestamp / 1_000_000,
                datetime.timezone.utc
            )
            
            # Calculate duration in seconds
            duration = (segment.end_timestamp - segment.start_timestamp) / 1_000_000
            
            print(f"{i+1:5d} | {dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]:25} | {duration:10.2f}s | {segment.weight:8.2f} | {segment.patient_id:10}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
        HDF5 Creathon anomalies tool.
        Use this tool to get information about anomalies present in HDF5 file.
        """)
    parser.add_argument('-f', type=str, help='Path to HDF5 file (with corresponding .artf file)', required=True)
    parser.add_argument('-s', type=str, help='Signal to analyze (e.g., "art", "abp", or "icp")', required=True)

    args = parser.parse_args()

    main(args)

