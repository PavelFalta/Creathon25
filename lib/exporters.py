from typing import Union
import xml.etree.ElementTree as ET
from xml.dom import minidom
from dataclasses import dataclass

from .artefact import Artefact

def prettify(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="\t")

@dataclass
class ARTFMetadata:
    hdf5_filename: Union[str, None] = None
    user_id: Union[str, None] = None

class ARTFExporter:

    DATE_FMT = '%d/%m/%Y %H:%M:%S.%f'

    def __init__(self, filename):
        self.filename = filename


    def export(self, global_artefacts : list[Artefact],
                    icp_artefacts: list[Artefact],
                    abp_artefacts: list[Artefact],
                    abp_name="abp",
                    metadata: Union[ARTFMetadata, None] = None) -> None:
        """Export artefacts to ARTF filename
        global_artefacts: list[Artefact]
        icp_artefacts: list[Artefact]
        abp_artefacts: list[Artefact]
        abp_name: str - name of the ABP signal
        """

        root = ET.Element("ICMArtefacts")

        if global_artefacts:
            global_element = ET.SubElement(root, "Global")
            for artefact in global_artefacts:
                artefact_element = ET.SubElement(global_element, "Artefact")
                artefact_element.set("ModifiedBy", artefact.modified_by)
                artefact_element.set("ModifiedDate",
                            artefact.modified_time.strftime(ARTFExporter.DATE_FMT)[:-3])
                artefact_element.set("StartTime",
                            artefact.start_time.strftime(ARTFExporter.DATE_FMT)[:-3])
                artefact_element.set("EndTime",
                            artefact.end_time.strftime(ARTFExporter.DATE_FMT)[:-3])

        if icp_artefacts:
            icp_element = ET.SubElement(root, "SignalGroup")
            icp_element.set("Name", "icp")
            for artefact in icp_artefacts:
                artefact_element = ET.SubElement(icp_element, "Artefact")
                artefact_element.set("ModifiedBy", artefact.modified_by)
                artefact_element.set("ModifiedDate",
                            artefact.modified_time.strftime(ARTFExporter.DATE_FMT)[:-3])
                artefact_element.set("StartTime",
                            artefact.start_time.strftime(ARTFExporter.DATE_FMT)[:-3])
                artefact_element.set("EndTime",
                            artefact.end_time.strftime(ARTFExporter.DATE_FMT)[:-3])

        if abp_artefacts:
            abp_element = ET.SubElement(root, "SignalGroup")
            abp_element.set("Name", abp_name)
            for artefact in abp_artefacts:
                artefact_element = ET.SubElement(abp_element, "Artefact")
                artefact_element.set("ModifiedBy", artefact.modified_by)
                artefact_element.set("ModifiedDate",
                            artefact.modified_time.strftime(ARTFExporter.DATE_FMT)[:-3])
                artefact_element.set("StartTime",
                            artefact.start_time.strftime(ARTFExporter.DATE_FMT)[:-3])
                artefact_element.set("EndTime",
                            artefact.end_time.strftime(ARTFExporter.DATE_FMT)[:-3])

        if metadata:
            metadata_element = ET.SubElement(root, "Info")
            if metadata.hdf5_filename:
                metadata_element.set("HDF5Filename", metadata.hdf5_filename)
            if metadata.user_id:
                metadata_element.set("UserID", metadata.user_id)

        with open(self.filename, "w") as f:
            f.write(prettify(root))

