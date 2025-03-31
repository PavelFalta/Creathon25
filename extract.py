#!/usr/bin/env python3
"""
Extract Tool - Exports signal segments from HDF5 files

This script extracts normal and anomalous segments from a signal in an HDF5 file
and exports them to various formats (CSV, NumPy text files).
"""

from lib.loader import FolderExtractor
import numpy as np
import argparse
import os
from pathlib import Path


def main(args):
    hdf5_filepath = args.f
    output_dir = args.o
    art_filepath = args.a

    extractor = FolderExtractor(hdf5_filepath)

    extractor.auto_annotate(art_filepath)

    extractor.export_to_csv(output_dir)

    print(f"Number of exported segments in the output directory: {len(os.listdir(output_dir))}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
        HDF5 Extract Tool.
        
        Extracts signal segments from an folder containing HDF5 files and saves them to csv format.
        """)
    
    parser.add_argument('-f', type=str, 
                       help='Path to a folder containing HDF5 files', 
                       required=True)
    parser.add_argument('-a', type=str, 
                       help='Path to a folder containing ART files', 
                       required=True)
    parser.add_argument('-o', type=str, 
                       help='Output directory', 
                       required=True)

    args = parser.parse_args()

    main(args)

