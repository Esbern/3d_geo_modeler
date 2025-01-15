# This file is part of the QGIS plugin developed for the Innotech – TaskForce Interreg project.
# 
# Copyright (C) [Year] Esbern Holmes, Roskilde University
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# We encourage users to inform us about their use of this plugin for research purposes.
# Contact: holmes@ruc.dk

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsRectangle,
    QgsPointXY,
    QgsField,
    QgsVectorFileWriter,
    QgsMessageLog,
)
import os
import subprocess
import json
import re

class LazInfoToGPKG(QgsProcessingAlgorithm):
    INPUT_FOLDER = 'INPUT_FOLDER'
    OUTPUT_FILE = 'OUTPUT_FILE'

    def __init__(self):
        super().__init__()
        self.first_crs = None
        self.first_epsg = None

    def tr(self, string):
        """Translate method"""
        return QCoreApplication.translate('LazInfoToGPKG', string)

    def createInstance(self):
        return LazInfoToGPKG()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FOLDER,
                "Input folder with LAZ/LAS files",
                behavior=QgsProcessingParameterFile.Folder
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_FILE,
                "Output GeoPackage File",
                fileFilter="GeoPackage (*.gpkg)"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        input_folder = self.parameterAsFile(parameters, self.INPUT_FOLDER, context)
        output_file = self.parameterAsFile(parameters, self.OUTPUT_FILE, context)

        # Fields for GeoPackage
        fields = [
            QgsField("filename", QVariant.String),
            QgsField("epsg", QVariant.Int),
            QgsField("encoding", QVariant.String),
            QgsField("copc", QVariant.Bool),
        ]
        writer = None

        def extract_axis_order(wkt_string):
            axis_order = []
            axis_matches = re.findall(r'AXIS\["([^"]+)",([^\]]+)\]', wkt_string)
            for match in axis_matches:
                axis_order.append(match[0])  # Collect axis labels (e.g., "Easting", "Northing")
            return axis_order

        def create_geometry(coordinates, axis_order):
            # Ensure only the first two axes are used for geometry
            if axis_order[:2] == ["Easting", "Northing"]:
                # Default: (Easting, Northing)
                return QgsGeometry.fromPolygonXY(
                    [[QgsPointXY(x, y) for x, y in coordinates[0]]]
                )
            elif axis_order[:2] == ["Northing", "Easting"]:
                # Swapped: (Northing, Easting)
                return QgsGeometry.fromPolygonXY(
                    [[QgsPointXY(y, x) for x, y in coordinates[0]]]
                )
            else:
                raise ValueError(f"Unsupported or unexpected axis order: {axis_order}")


        for file_name in os.listdir(input_folder):
            if file_name.endswith(('.laz', '.las')):
                file_path = os.path.join(input_folder, file_name)
                feedback.pushInfo(f"Processing {file_path}")

                # Run pdal info
                try:
                    pdal_output = subprocess.check_output(
                        ["pdal", "info", "--all", file_path],
                        universal_newlines=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except subprocess.CalledProcessError as e:
                    feedback.reportError(f"Error running pdal info on {file_name}: {e}")
                    continue

                info = json.loads(pdal_output)

                # Extract EPSG Code by finding the last AUTHORITY["EPSG", ...]
                wkt_sources = [
                    info.get("metadata", {}).get("comp_spatialreference", ""),
                    info.get("metadata", {}).get("spatialreference", ""),
                    info.get("metadata", {}).get("srs", {}).get("compoundwkt", ""),
                    info.get("metadata", {}).get("srs", {}).get("wkt", "")
                ]

                epsg = None
                axis_order = []
                for wkt_string in wkt_sources:
                    if wkt_string:
                        matches = re.findall(r'AUTHORITY\["EPSG","(\d+)"\]', wkt_string)
                        if matches:
                            epsg = int(matches[-1])  # Use the last EPSG code
                        axis_order = extract_axis_order(wkt_string)
                        if axis_order:
                            break

                feedback.pushInfo(f"Extracted EPSG: {epsg}, Axis Order: {axis_order}")

                # Encoding type
                encoding = "laz" if info.get("metadata", {}).get("compressed", False) else "las"

                # COPC encoding
                copc = info.get("metadata", {}).get("copc", False)

                # Extract Boundary Geometry
                boundary_data = info.get("boundary", {}).get("boundary_json", None)
                geometry = None
                if boundary_data:
                    if boundary_data.get("type") == "Polygon":
                        # Handle single Polygon
                        coordinates = boundary_data.get("coordinates", [])
                        if coordinates:
                            geometry = create_geometry(coordinates, axis_order)
                    elif boundary_data.get("type") == "MultiPolygon":
                        # Handle MultiPolygon
                        multi_coordinates = boundary_data.get("coordinates", [])
                        if multi_coordinates:
                            # Extract geometries for each polygon in the MultiPolygon
                            polygons = []
                            for poly_coords in multi_coordinates:
                                # Each `poly_coords` represents one polygon with outer and inner rings
                                rings = [
                                    [QgsPointXY(x, y) if axis_order[:2] == ["Easting", "Northing"] else QgsPointXY(y, x)
                                    for x, y in ring_coords]
                                    for ring_coords in poly_coords
                                ]
                                polygons.append(rings)
                            geometry = QgsGeometry.fromMultiPolygonXY(polygons)


                if not geometry or not geometry.isGeosValid():
                    feedback.pushInfo(f"Invalid or unsupported boundary geometry for {file_name}: {boundary_data}")
                    continue

                if not epsg:
                    feedback.reportError(f"Missing CRS information for {file_name}")
                    continue

                # Set CRS for the first file and create writer
                if self.first_crs is None:
                    self.first_crs = epsg
                    writer = QgsVectorLayer(f"Polygon?crs=EPSG:{epsg}", "laz_info", "memory")
                    writer.dataProvider().addAttributes(fields)
                    writer.updateFields()

                # Check if CRS matches
                if epsg != self.first_crs:
                    feedback.pushInfo(f"Skipping {file_name}: CRS does not match the first file")
                    QgsMessageLog.logMessage(
                        f"CRS mismatch: {file_name} has a different CRS than the first file", "Processing"
                    )
                    continue

                # Add feature to layer
                feature = QgsFeature()
                feature.setGeometry(geometry)
                feature.setAttributes([file_name, epsg, encoding, copc])
                writer.dataProvider().addFeature(feature)

        # Write to GeoPackage
        if writer:
            QgsVectorFileWriter.writeAsVectorFormat(
                writer,
                output_file,
                "UTF-8",
                writer.crs(),
                "GPKG"
            )
            feedback.pushInfo(f"GeoPackage written to {output_file}")
        else:
            feedback.reportError("No valid files were processed. GeoPackage not created.")

        return {'OUTPUT_FILE': output_file}


    def name(self):
        return 'create_index'

    def displayName(self):
        return self.tr('Create Index')

    def group(self):
        return self.tr('LiDAR Preprocessing')

    def groupId(self):
        return 'lidar_processing'

    def shortHelpString(self):
        return (
            "Processes a folder of .laz or .las files, extracts metadata including CRS, encoding type, "
            "COPC encoding, and boundaries, and writes the information to a GeoPackage file. "
            "All files must have the same CRS."
        )

    def createInstance(self):
        return LazInfoToGPKG()
