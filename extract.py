from lib.loader import SingleFileExtractor

import numpy as np
import argparse
import os

WINDOW_SIZE_SEC = 10


def main(args):
    hdf5_filepath = args.f
    output_dir = args.o
    mode = args.s
    matching = args.sn

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    
    if matching:
        extractor = SingleFileExtractor(hdf5_filepath,
                                        mode=mode,
                                        matching=True,
                                        matching_multiplier=2)
        anomaly_segments = extractor.get_anomalies()
        normal_segments = extractor.get_normal()[:len(anomaly_segments)]
    else:
        extractor = SingleFileExtractor(hdf5_filepath,
                                        mode=mode,
                                        matching=False)
        anomaly_segments = extractor.get_anomalies()
        normal_segments = extractor.get_normal()

    # save segments
    for segment in anomaly_segments:
        np.savetxt(
                os.path.join(output_dir, f"{mode}_{int(segment.start_time)}_1.txt"),
                segment.data)
    for segment in normal_segments:
        np.savetxt(
                os.path.join(output_dir, f"{mode}_{int(segment.start_time)}_0.txt"),
                segment.data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="""
            HDF5 Creathon extract tool.
            Use this tool to extract signal segments from HDF5 file and their annotations from ARTF file.
            Outputs signal segments as numpy text files in the output directory.
            Files are named as {signal}_{start_ts_micro}_{is_anomalous}.txt where 0 is not an anomaly and 1 is an anomaly.
            """)
    parser.add_argument('-f', type=str, help='Path to HDF5 file (with corresponding .artf file)', required=True)
    parser.add_argument('-s', type=str, help='Signal to export, abp or icp', required=True)
    parser.add_argument('-o', type=str, help='Output directory', required=True)
    parser.add_argument('-sn', action='store_true', help='Export same number of normal and anomalous segments')

    args = parser.parse_args()

    if args.s not in {'abp', 'icp'}:
        raise Exception("Unknown signal value")

    main(args)

