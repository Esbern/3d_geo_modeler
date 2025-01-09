import os
import json
import subprocess
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterFile,
    QgsProcessingParameterCrs,
    QgsProcessingException
)

class AssignCRSToFolder(QgsProcessingAlgorithm):
    """
    Assign CRS to all LAS/LAZ files in a folder without transformation.
    """

    INPUT_FOLDER = 'INPUT_FOLDER'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    CRS = 'CRS'

    def tr(self, string):
        """
        Translation method for GUI strings.
        """
        return QCoreApplication.translate('AssignCRSToFolder', string)

    def createInstance(self):
        return AssignCRSToFolder()

    def initAlgorithm(self, config=None):
        # Input folder: Using QgsProcessingParameterFile with folder type
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FOLDER,
                self.tr('Input Folder with LAS/LAZ files'),
                behavior=QgsProcessingParameterFile.Folder
            )
        )

        # Output folder
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER,
                self.tr('Output Folder for Processed Files')
            )
        )

        # CRS selection
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS,
                self.tr('Coordinate Reference System (CRS)')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        input_folder = self.parameterAsString(parameters, self.INPUT_FOLDER, context)
        output_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        crs = self.parameterAsCrs(parameters, self.CRS, context)
        epsg_code = crs.authid().split(":")[-1]

        if not os.path.exists(input_folder):
            raise QgsProcessingException(self.tr(f"Input folder does not exist: {input_folder}"))
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.las', '.laz'))]
        if not files:
            raise QgsProcessingException(self.tr("No LAS/LAZ files found in the input folder."))

        total_files = len(files)
        feedback.pushInfo(f"Found {total_files} files to process.")

        for index, file_name in enumerate(files):
            input_file = os.path.join(input_folder, file_name)
            output_file = os.path.join(output_folder, file_name)

            feedback.pushInfo(f"Processing file {index + 1}/{total_files}: {file_name}")

            # PDAL pipeline
            pipeline = {
                "pipeline": [
                    {"type": "readers.las", "filename": input_file},
                    {"type": "writers.copc", "filename": output_file, "a_srs": f"EPSG:{epsg_code}"}
                ]
            }

            pipeline_path = os.path.join(output_folder, f"pipeline_{index}.json")
            with open(pipeline_path, 'w') as f:
                json.dump(pipeline, f, indent=4)

            try:
                subprocess.run(
                    ["pdal", "pipeline", pipeline_path],
                    check=True,
                    text=True,
                    capture_output=True
                )
                feedback.pushInfo(f"Successfully processed: {file_name}")
            except subprocess.CalledProcessError as e:
                feedback.reportError(f"Error processing {file_name}: {e.stderr}")
                continue
            finally:
                os.remove(pipeline_path)

            # Update progress
            feedback.setProgress((index + 1) / total_files * 100)

        feedback.pushInfo("CRS assignment completed for all files.")
        return {self.OUTPUT_FOLDER: output_folder}

    def name(self):
        return 'AssignCRSToFolder'

    def displayName(self):
        return self.tr('Assign CRS to Folder of LAS/LAZ Files')

    def group(self):
        return self.tr('LiDAR Preprocessing')

    def groupId(self):
        return 'lidar_processing'

    def shortHelpString(self):
        return self.tr("Assigns a CRS to all LAS/LAZ files in a folder without transforming their coordinates.")
