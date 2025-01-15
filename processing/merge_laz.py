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

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterBoolean,
    QgsProcessingException,
    QgsVectorLayer,
    QgsProject,
    QgsMapLayer  # Import for layer type check
)
from qgis.utils import iface
import os
import subprocess


class MergeLAZFiles(QgsProcessingAlgorithm):
    ATTRIBUTE_FIELD = 'ATTRIBUTE_FIELD'
    FOLDER_PATH = 'FOLDER_PATH'
    OUTPUT_FILE = 'OUTPUT_FILE'
    CONFIRM_MERGE = 'CONFIRM_MERGE'

    def tr(self, string):
        """Translate method"""
        return QCoreApplication.translate('MergeLAZFiles', string)

    def initAlgorithm(self, config=None):
        """Define parameters for the script"""
        # Dynamically fetch attributes from the active layer
        layer = iface.activeLayer()
        if layer and layer.type() == QgsMapLayer.VectorLayer:
            fields = [field.name() for field in layer.fields()]
        else:
            fields = ['[No active layer found]']

        # Attribute field parameter
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ATTRIBUTE_FIELD,
                self.tr('Select attribute pointing to LAZ filenames'),
                options=fields,
                optional=False
            )
        )

        # Input folder parameter
        self.addParameter(
            QgsProcessingParameterFile(
                self.FOLDER_PATH,
                self.tr('Select folder containing LAZ files'),
                behavior=QgsProcessingParameterFile.Folder
            )
        )

        # Output merged LAZ file
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_FILE,
                self.tr('Output merged LAZ file'),
                fileFilter='LAZ files (*.laz);;COPC files (*.copc.laz)'
            )
        )

        # Confirmation parameter
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CONFIRM_MERGE,
                self.tr('Confirm merge operation'),
                defaultValue=False
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """Main logic for the script"""
        # Step 1: Get the active layer
        layer = iface.activeLayer()
        if not layer or layer.type() != QgsMapLayer.VectorLayer:
            raise QgsProcessingException("No active vector layer found.")

        # Step 2: Dynamically get the attribute field
        fields = [field.name() for field in layer.fields()]
        attribute_index = self.parameterAsInt(parameters, self.ATTRIBUTE_FIELD, context)
        attribute_field = fields[attribute_index]

        # Step 3: Get the folder path and output file path
        folder_path = self.parameterAsString(parameters, self.FOLDER_PATH, context)
        output_file = self.parameterAsString(parameters, self.OUTPUT_FILE, context)
        confirm_merge = self.parameterAsBool(parameters, self.CONFIRM_MERGE, context)

        if not confirm_merge:
            raise QgsProcessingException("Merge not confirmed. Enable the 'Confirm merge operation' checkbox to proceed.")

        # Step 4: Fetch file paths from selected features
        selected_features = layer.selectedFeatures()
        if not selected_features:
            raise QgsProcessingException("No features are selected in the active layer.")

        laz_files = []
        for feature in selected_features:
            filename = feature[attribute_field]
            laz_path = os.path.join(folder_path, filename)  # Combine folder and filename
            if not filename or not os.path.exists(laz_path):
                feedback.reportError(f"File '{laz_path}' does not exist. Skipping.")
                continue
            laz_files.append(laz_path)

        if len(laz_files) < 2:
            raise QgsProcessingException("At least two valid LAZ files are required for merging.")

        feedback.pushInfo(f"Files to merge: {len(laz_files)}")
        
        # Step 5: Build the PDAL merge command
        command = [
            "pdal", "merge",
            *laz_files,  # Input files
            output_file  # Output file
        ]

        # Ensure CRS is explicitly set for the output file
        crs_argument = f"--writers.copc.a_srs=EPSG:{layer.crs().postgisSrid()}"
        command.append(crs_argument)

        feedback.pushInfo("Running PDAL merge command...")
        feedback.pushInfo(f"Command: {' '.join(command)}")

        # Step 6: Execute PDAL merge command
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            feedback.pushInfo(f"PDAL merge completed. Output file: {output_file}")
        except subprocess.CalledProcessError as e:
            feedback.reportError(f"Error running PDAL merge: {e.stderr}")
            raise QgsProcessingException(self.tr(f"PDAL merge failed: {e.stderr}"))

        # Final feedback
        feedback.pushInfo("Merge operation completed successfully.")
        return {'OUTPUT_FILE': output_file}

    def name(self):
        return 'merge_laz_files'

    def displayName(self):
        return self.tr('Merge LAZ Files')

    def group(self):
        return self.tr('LiDAR Preprocessing')

    def groupId(self):
        return 'lidar_processing'

    def shortHelpString(self):
        return self.tr('Merges selected copc.LAZ files into a single file.')

    def createInstance(self):
        return MergeLAZFiles()
