from lib.loader import FolderExtractor

extractor = FolderExtractor("example_data")

extractor.auto_annotate()

extractor.export_to_csv("out")