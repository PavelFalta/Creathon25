from lib.funcs import get_hdf5_signal_names
from lib.loader import SingleFileExtractor

import argparse


def main(args):
    hdf5_filepath = args.f

    abp_extractor = SingleFileExtractor(hdf5_filepath,
                                    mode='abp',
                                    matching=False)
    icp_extractor = SingleFileExtractor(hdf5_filepath,
                                    mode='icp',
                                    matching=False)

    abp_normal = abp_extractor.get_normal()
    abp_anomaly = abp_extractor.get_anomalies()
    abp_array = abp_extractor.return_hdf5_as_array()
    icp_normal = icp_extractor.get_normal()
    icp_anomaly = icp_extractor.get_anomalies()
    icp_array = icp_extractor.return_hdf5_as_array()

    # get number of segments
    icp_n_segments = len(icp_anomaly) + len(icp_normal)
    abp_n_segments = len(abp_anomaly) + len(abp_normal)
    #icp_length_h = icp_n_segments / 6 / 60
    icp_length_h = len(icp_array) / icp_extractor.get_frequency() / 3600
    #abp_length_h = abp_n_segments / 6 / 60
    abp_length_h = len(abp_array) / abp_extractor.get_frequency() / 3600

    signals = get_hdf5_signal_names(hdf5_filepath)

    print(f"Signals: {','.join(signals)}")
    print(f"ICP length: {icp_length_h:.2f} h")
    print(f"ABP length: {abp_length_h:.2f} h")
    print(f"ICP segments (10 s): {icp_n_segments}")
    print(f"ABP segments (10 s): {abp_n_segments}")

    # get sample rates
    icp_sr = icp_extractor.get_frequency()
    abp_sr = abp_extractor.get_frequency()
    assert icp_sr == abp_sr

    print(f"ICP sample rate: {icp_sr:.2f} Hz")
    print(f"ABP sample rate: {abp_sr:.2f} Hz")

    print("ICP anomalous segments: ", len(icp_anomaly))
    print("ABP anomalous segments: ", len(abp_anomaly))#chtelo by zmenu artefakty -> anomalie
    total_anomalies = len(icp_anomaly) + len(abp_anomaly)
    print("Total anomalies: ", total_anomalies)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="""
            HDF5 Creathon info tool.
            Use this tool to get information about the HDF5 file and the anomalies associated with it.
            """)
    parser.add_argument('-f', type=str, help='Path to HDF5 file (with corresponding .artf file)', required=True)

    args = parser.parse_args()

    main(args)

