from qgis.utils import iface
"""
LiDARTo3DProcessingAlgorithm is a QGIS processing algorithm that converts LiDAR data into 3D building geometries using geoflow.
Attributes:
    ATTRIBUTE_FIELD (str): Parameter name for selecting the attribute field.
    RECONSTRUCT_JSON (str): Parameter name for the reconstruct JSON file.
    INPUT_POINTCLOUD (str): Parameter name for the input point cloud folder.
    OUTPUT_OGR_CRS (str): Parameter name for the output CRS (OGR).
    OUTPUT_CITYJSON_FOLDER (str): Parameter name for the output CityJSON folder.
    OUTPUT_OBJ_FOLDER (str): Parameter name for the output OBJ folder.
    OUTPUT_GPKG (str): Parameter name for the output GeoPackage file path.
    GEOF_EXECUTABLE (str): Parameter name for the path to geof.exe.
    PROCESS_SELECTION (str): Parameter name for selecting whether to process all features or only selected features.
Methods:
    initAlgorithm(config=None):
        Initializes the algorithm with parameters for selecting attribute fields, input files, output folders, CRS, and processing options.
    processAlgorithm(parameters, context, feedback):
        Processes the algorithm by extracting necessary parameters, validating inputs, and executing the geoflow command for each feature.
    name():
        Returns the unique name of the algorithm.
    displayName():
        Returns the display name of the algorithm.
    group():
        Returns the group name of the algorithm.
    groupId():
        Returns the unique group ID of the algorithm.
    shortHelpString():
        Returns a short help string describing the algorithm.
    createInstance():
        Creates and returns a new instance of the algorithm.
    tr(message):
        Translates the given message for internationalization.
"""
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterCrs,
    QgsProcessingParameterEnum,
    QgsProcessingException,
    QgsCoordinateReferenceSystem,
    QgsMessageLog,
    QgsMapLayer,
    QgsVectorLayer,
    QgsVectorFileWriter,
    Qgis
)
from qgis.PyQt.QtCore import QCoreApplication
import os
import subprocess
import sqlite3


class GeoFLow(QgsProcessingAlgorithm):
    ATTRIBUTE_FIELD = 'ATTRIBUTE_FIELD'
    RECONSTRUCT_JSON = 'RECONSTRUCT_JSON'
    INPUT_POINTCLOUD = 'INPUT_POINTCLOUD'
    OUTPUT_OGR_CRS = 'OUTPUT_OGR_CRS'
    OUTPUT_CITYJSON_FOLDER = 'OUTPUT_CITYJSON_FOLDER'
    OUTPUT_OBJ_FOLDER = 'OUTPUT_OBJ_FOLDER'
    OUTPUT_GPKG = 'OUTPUT_GPKG'
    GEOF_EXECUTABLE = 'GEOF_EXECUTABLE'
    PROCESS_SELECTION = 'PROCESS_SELECTION'

    def initAlgorithm(self, config=None):
        ATTRIBUTE_FIELD = 'ATTRIBUTE_FIELD'

        # Dynamically fetch attributes from the active layer
        layer = iface.activeLayer()
        if layer:
             # Check if the active layer is a vector layer
            if layer.type() == QgsMapLayer.VectorLayer:
                fields = [field.name() for field in layer.fields()]
            else:
                fields = ['[No fields available - not a vector layer]']
        else:
            # Default to an empty dropdown or placeholder if no active layer
            fields = ['[No active layer found]']


        # Attribute field parameter
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ATTRIBUTE_FIELD,
                self.tr('Select Attribute for Object ID'),
                options=fields,
                optional=True
            )
        )

        # Reconstruct JSON parameter
        self.addParameter(
            QgsProcessingParameterFile(
                self.RECONSTRUCT_JSON,
                self.tr('Reconstruct JSON File'),
                behavior=QgsProcessingParameterFile.File
            )
        )

        # Input point cloud folder parameter
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_POINTCLOUD,
                self.tr('Input Point Cloud Folder'),
                behavior=QgsProcessingParameterFile.Folder
            )
        )

        # CRS selector parameter
        self.addParameter(
            QgsProcessingParameterCrs(
                self.OUTPUT_OGR_CRS,
                self.tr('Output CRS (OGR)')
            )
        )

        # CityJSON and OBJ folders
        self.addParameter(
            QgsProcessingParameterFile(
                self.OUTPUT_CITYJSON_FOLDER,
                self.tr('Output CityJSON Folder'),
                behavior=QgsProcessingParameterFile.Folder
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.OUTPUT_OBJ_FOLDER,
                self.tr('Output OBJ Folder'),
                behavior=QgsProcessingParameterFile.Folder
            )
        )

        # GeoPackage output parameter
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_GPKG,
                self.tr('Output GeoPackage File Path'),
                fileFilter='GeoPackage (*.gpkg)'
            )
        )

        # geof.exe path
        self.addParameter(
            QgsProcessingParameterFile(
                self.GEOF_EXECUTABLE,
                self.tr('Path to geof.exe'),
                behavior=QgsProcessingParameterFile.File,
                defaultValue='C:/Program Files/Geoflow/bin/geof.exe'.replace('\\', '/')
            )
        )

        # Process selection: All or Selected Features
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PROCESS_SELECTION,
                self.tr('Process Selection'),
                options=['All Features', 'Only Selected Features'],
                defaultValue=0
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        # Get the active layer
        layer = iface.activeLayer()
        if not layer:
            raise QgsProcessingException('No active layer found.')

        # Extract layer name from GeoPackage
        data_source_uri = layer.dataProvider().dataSourceUri()
        if '.gpkg' not in data_source_uri:
            raise QgsProcessingException('Active layer is not from a GeoPackage.')

        # Extract the layer name
        if 'layername=' in data_source_uri:
            layer_name = data_source_uri.split('layername=')[-1].split('|')[0]
        else:
            raise QgsProcessingException('Unable to extract layer name from GeoPackage.')

        feedback.pushInfo(f"Active GeoPackage layer name: {layer_name}")

        # Get the selected CRS and its EPSG code
        selected_crs = self.parameterAsCrs(parameters, self.OUTPUT_OGR_CRS, context)
        epsg_code = selected_crs.postgisSrid()
        if epsg_code <= 0:
            raise QgsProcessingException('Invalid EPSG code from selected CRS.')

        feedback.pushInfo(f"Selected CRS: {selected_crs.authid()}, EPSG: {epsg_code}")

        # Retrieve the selected attribute
        attribute_field_index = self.parameterAsEnum(parameters, self.ATTRIBUTE_FIELD, context)
        if attribute_field_index < 0 or attribute_field_index >= len(layer.fields()):
            raise QgsProcessingException('Selected attribute index is out of range.')
        field_name = layer.fields()[attribute_field_index].name()

        feedback.pushInfo(f"Selected Attribute: {field_name}")

        # Check if the layer has a valid data source
        input_footprint = layer.dataProvider().dataSourceUri().split("|")[0]
        if not os.path.exists(input_footprint):
            raise QgsProcessingException(f"Input footprint file '{input_footprint}' does not exist.")

        # Other parameters
        reconstruct_json = self.parameterAsString(parameters, self.RECONSTRUCT_JSON, context)
        output_ogr_epsg = epsg_code
        input_pointcloud = self.parameterAsString(parameters, self.INPUT_POINTCLOUD, context)
        output_cityjson_folder = self.parameterAsString(parameters, self.OUTPUT_CITYJSON_FOLDER, context)
        output_obj_folder = self.parameterAsString(parameters, self.OUTPUT_OBJ_FOLDER, context)
        output_gpkg = self.parameterAsString(parameters, self.OUTPUT_GPKG, context)
        geof_executable = self.parameterAsString(parameters, self.GEOF_EXECUTABLE, context)
        process_selection = self.parameterAsEnum(parameters, self.PROCESS_SELECTION, context)
        output_epsg_string = f"EPSG:{output_ogr_epsg}"


        # Create GeoPackage if it does not exist
        if not os.path.exists(output_gpkg):
            feedback.pushInfo(f"Creating new GeoPackage: {output_gpkg}")
            try:
                # Use QgsVectorFileWriter to create an empty GeoPackage
                temp_layer = QgsVectorLayer("Point?crs=EPSG:4326", "temp", "memory")
                error = QgsVectorFileWriter.writeAsVectorFormat(
                    temp_layer,
                    output_gpkg,
                    "UTF-8",
                    QgsCoordinateReferenceSystem("EPSG:4326"),
                    "GPKG"
                )
                if error[0] != QgsVectorFileWriter.NoError:
                    raise QgsProcessingException(f"Error creating GeoPackage: {error[1]}")
                del temp_layer  # Cleanup temporary layer
            except Exception as e:
                raise QgsProcessingException(f"Error creating GeoPackage: {e}")


        # Determine features to process
        features = layer.selectedFeatures() if process_selection == 1 else layer.getFeatures()
        features = list(layer.selectedFeatures() if process_selection == 1 else layer.getFeatures())


        for feature in features:
            # Fetch the value of the selected attribute
            attribute_value = feature[field_name]

            # Determine quoting style based on data type
            sql_query = f"{field_name}='{attribute_value}'" if isinstance(attribute_value, str) else f"{field_name}={attribute_value}"

            # Generate file paths
            obj_str = str(attribute_value)
            output_cityjson = os.path.join(output_cityjson_folder, f"byg_{obj_str}.json")
            output_obj = os.path.join(output_obj_folder, f"byg_{obj_str}.obj")

            # Construct command
            command = [
                geof_executable,
                reconstruct_json,
                f"--input_pointcloud={input_pointcloud}",
                f"--input_footprint={input_footprint}",
                f"--input_footprint_layer={layer_name}",
                f"--output_ogr_EPSG={output_ogr_epsg}",
                f"--output_espg_string={output_epsg_string}",
                f"--output_ogr={output_gpkg}",
                f"--output_cityjson={output_cityjson}",
                f"--input_footprint_select_sql={sql_query}",
                f"--output_obj_lod22={output_obj}"
            ]

            # Log command
            feedback.pushInfo(f"Running command for {field_name}={attribute_value}: {' '.join(command)}")

            # Execute command
            try:
                subprocess.run(command, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                feedback.reportError(f"Error processing {field_name}={attribute_value} with command {' '.join(command)}:\n{e.stderr}")

        feedback.pushInfo("Processing complete.")
        return {}

    def name(self):
        return 'lidar_to_3d'

    def displayName(self):
        return self.tr('LiDAR to 3D Geometry')

    def group(self):
        return self.tr('GeoFlow interface')

    def groupId(self):
        return 'GeoFlow_interface'

    def shortHelpString(self):
        return self.tr("This script converts LiDAR data into 3D building geometries using geoflow.")

  
    def createInstance(self):
        return  GeoFLow()


    @staticmethod
    def tr(message):
        return QCoreApplication.translate('GeoFLow', message)
