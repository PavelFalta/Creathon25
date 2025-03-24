from lib.loader import SingleFileExtractor, FolderExtractor
import matplotlib.pyplot as plt
import numpy as np


# extract all ABP anomalous segments from all .hdf5 files
# in data/ directory
"""
extractor = FolderExtractor("data/",
                            mode="abp",
                            matching=False)
anomaly_segments, normal_segments = extractor.extract_all()
"""

# extract all ABP anomalous segments and matching number
# of normal segments from TBI_003.hdf5 file
# BE SURE TO READ `matching` ARG DOCSTRING DESCRIPTION
# OF `SingleFileExtractor` CLASS
extractor = SingleFileExtractor("data/TBI_003.hdf5",
                                mode="abp",
                                #mode="icp",
                                matching=True,
                                matching_multiplier=1)
normal_segments = extractor.get_normal()
anomalous_segments = extractor.get_anomalies()

# print number of segments
print(f"Normal: {len(normal_segments)} Anomalies: {len(anomalous_segments)}")

# plot first anomalous segment
sr = extractor.get_frequency()
segment = anomalous_segments[0]

plt.plot(segment.data)
plt.title("First ABP anomalous segment")
plt.ylabel("mmHg")
plt.xlabel("Time (s)")
xticks = np.arange(0, len(segment.data) + 1, sr)
xlabels = [f"{(tick/sr):.1f}" for tick in xticks]
plt.xticks(xticks, xlabels)
plt.show()

