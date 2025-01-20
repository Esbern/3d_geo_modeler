from qgis.core import QgsProcessingProvider
from .processing.GeoFlow import GeoFLow  # Import your scripts
from .processing.assign_crs import AssignCRSToFolder
from .processing.laz2cocp import LazToCopc
from .processing.create_laz_index import LazInfoToGPKG   
from .processing.delete_laz import DeleteFeaturesAndLAZFiles
from .processing.merge_laz import MergeLAZFiles
from .processing.load_geojson import LoadGeoJSON
from .processing.download_laz import DownloadFilesFromFTPS

class MyProcessingProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        """Register algorithms."""
        self.addAlgorithm(GeoFLow())  # Add each algorithm here
        self.addAlgorithm(AssignCRSToFolder())
        self.addAlgorithm(LazToCopc())
        self.addAlgorithm(LazInfoToGPKG())
        self.addAlgorithm(DeleteFeaturesAndLAZFiles())
        self.addAlgorithm(MergeLAZFiles())
        self.addAlgorithm(LoadGeoJSON())
        self.addAlgorithm(DownloadFilesFromFTPS())

    def id(self):
        """Unique provider ID."""
        return '3D_geo_modeler'

    def name(self):
        """Provider name shown in QGIS."""
        return '3D Geo Modeler'
    def longName(self):
        """Detailed provider name."""
        return 'Collection os scripts for 3D modeling'
