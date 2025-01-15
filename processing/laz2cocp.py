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

import os
import json
import subprocess
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingException
)

class LazToCopc(QgsProcessingAlgorithm):
    INPUT_FOLDER = 'INPUT_FOLDER'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'

    def initAlgorithm(self, config=None):
        # Define the input parameter for the LAZ folder
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FOLDER,
                self.tr('Input Folder (LAZ files)'),
                behavior=QgsProcessingParameterFile.Folder
            )
        )
        
        # Define the output parameter for the COPC folder
        self.addParameter(
            QgsProcessingParameterFile(
                self.OUTPUT_FOLDER,
                self.tr('Output Folder (COPC files)'),
                behavior=QgsProcessingParameterFile.Folder
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # Get the input and output folders
        input_directory = self.parameterAsFile(parameters, self.INPUT_FOLDER, context)
        output_directory = self.parameterAsFile(parameters, self.OUTPUT_FOLDER, context)

        # Validate the input folder
        if not os.path.isdir(input_directory):
            raise QgsProcessingException(f"Input folder does not exist: {input_directory}")

        # Create the output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)

        # Collect all LAZ files in the input directory
        laz_files = [f for f in os.listdir(input_directory) if f.endswith('.laz')]
        if not laz_files:
            feedback.pushInfo('No LAZ files found in the input folder.')
            return {}

        # Process each LAZ file
        for laz_file in laz_files:
            basename = os.path.splitext(laz_file)[0]
            input_path = os.path.join(input_directory, laz_file)
            output_path = os.path.join(output_directory, f"{basename}.copc.laz")

            # Build the PDAL pipeline
            pipeline = {
                "pipeline": [
                    {"type": "readers.las", "filename": input_path},
                    {"type": "writers.copc", "filename": output_path}
                ]
            }

            # Write the pipeline to a temporary JSON file
            json_path = os.path.join(output_directory, f"{basename}_pipeline.json")
            with open(json_path, 'w') as f:
                json.dump(pipeline, f, indent=2)

            # Run the PDAL pipeline
            feedback.pushInfo(f"Processing: {input_path} -> {output_path}")
            process = subprocess.run(["pdal", "pipeline", json_path], capture_output=True, text=True)

            if process.returncode != 0:
                feedback.reportError(f"Error processing {laz_file}: {process.stderr}")
                continue
            else:
                feedback.pushInfo(f"Successfully processed {basename}.copc.laz")

            # Remove the temporary JSON file
            os.remove(json_path)

        feedback.pushInfo(f"All files processed. COPC files are in {output_directory}.")
        return {}

    def name(self):
        return 'laz_to_copc'

    def displayName(self):
        return self.tr('Convert LAZ to COPC')

    def group(self):
        return self.tr('LiDAR Preprocessing')

    def groupId(self):
        return 'lidar_processing'

    def shortHelpString(self):
        return self.tr("This script converts all LAZ files in the input folder "
                       "to COPC LAZ files using PDAL. Specify an input folder and an output folder. PDAL must be installed.")

    def createInstance(self):
        return LazToCopc()

    @staticmethod
    def tr(message):
        """Helper for translations."""
        return QCoreApplication.translate('LazToCopc', message)
