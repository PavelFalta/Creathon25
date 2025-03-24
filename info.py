#!/usr/bin/env python3
"""
Info Tool - Displays information about signals in HDF5 files

This script provides detailed information about signals in an HDF5 file,
including signal names, lengths, sampling frequencies, and annotation statistics.
"""

from lib.loader import SingleFileExtractor
import argparse
from pathlib import Path
import datetime


def main(args):
    hdf5_filepath = args.f
    file_path = Path(hdf5_filepath)
    
    print(f"File: {file_path.name}")
    print("-" * 60)
    
    # Create an extractor for the file
    extractor = SingleFileExtractor(hdf5_filepath)
    
    # Get available signal names
    signal_names = extractor.get_signal_names()
    print(f"Available signals: {', '.join(signal_names)}")
    
    # Try to auto-annotate if an .artf file exists
    try:
        extractor.auto_annotate()
        annotations_loaded = True
        print("\nAnnotations found and loaded.")
    except Exception as e:
        annotations_loaded = False
        print(f"\nNo annotations found or error loading them: {e}")
    
    # Print detailed signal information
    print("\nSignal Details:")
    print("-" * 60)
    
    for signal_name in signal_names:
        print(f"\n{signal_name.upper()} Signal:")
        
        # Get raw data to find general properties
        raw_data = extractor.get_raw_data(signal_name)
        
        if raw_data is None or len(raw_data) == 0:
            print(f"  No data found for {signal_name}")
            continue
        
        # Get the first signal object to access properties
        signal_obj = next((s for s in extractor._signals if s.signal_name == signal_name), None)
        
        if signal_obj:
            # Calculate signal properties
            freq = signal_obj.frequency
            duration_sec = len(raw_data) / freq
            duration_min = duration_sec / 60
            duration_hours = duration_min / 60
            
            # Get start and end times
            start_time = datetime.datetime.fromtimestamp(
                signal_obj.starttime / 1_000_000, 
                datetime.timezone.utc
            )
            end_time = datetime.datetime.fromtimestamp(
                (signal_obj.starttime + int(signal_obj.length * 1_000_000 / freq)) / 1_000_000,
                datetime.timezone.utc
            )
            
            # Print general properties
            print(f"  Sampling Rate: {freq:.2f} Hz")
            print(f"  Duration: {duration_hours:.2f} hours ({duration_sec:.0f} seconds)")
            print(f"  Number of Samples: {len(raw_data)}")
            print(f"  Start Time: {start_time}")
            print(f"  End Time: {end_time}")
            
            # Get signal statistics
            nan_count = sum(1 for x in raw_data if np.isnan(x))
            nan_percent = (nan_count / len(raw_data)) * 100 if len(raw_data) > 0 else 0
            
            print(f"  Missing Values: {nan_count} ({nan_percent:.2f}%)")
            
            valid_data = [x for x in raw_data if not np.isnan(x)]
            if valid_data:
                print(f"  Min Value: {min(valid_data):.2f}")
                print(f"  Max Value: {max(valid_data):.2f}")
                print(f"  Mean Value: {sum(valid_data) / len(valid_data):.2f}")
            
            # Print annotation information if loaded
            if annotations_loaded:
                try:
                    good_segments, anomalous_segments = extractor.extract(signal_name)
                    
                    # Get segment statistics
                    total_segments = len(good_segments) + len(anomalous_segments)
                    anomaly_percentage = (len(anomalous_segments) / total_segments * 100) if total_segments > 0 else 0
                    
                    print(f"  Annotation Summary:")
                    print(f"    Total Segments: {total_segments}")
                    print(f"    Normal Segments: {len(good_segments)}")
                    print(f"    Anomalous Segments: {len(anomalous_segments)} ({anomaly_percentage:.2f}%)")
                    
                    # Get annotator information
                    annotator_counts = extractor.annotated_anomalies(signal_name)
                    if annotator_counts:
                        print(f"    Annotators: {', '.join(annotator_counts.keys())}")
                except Exception as e:
                    print(f"  Error extracting annotations: {e}")
        else:
            print(f"  Error: Could not get signal properties")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
        HDF5 Info Tool.
        
        Displays detailed information about signals in an HDF5 file, including
        signal names, lengths, sampling frequencies, and annotation statistics.
        """)
    
    parser.add_argument('-f', type=str, 
                       help='Path to HDF5 file (with optional .artf file)', 
                       required=True)

    args = parser.parse_args()

    # Import numpy here to avoid slow startup time if displaying help
    import numpy as np
    
    main(args)

