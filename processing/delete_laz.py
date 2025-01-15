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
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFile,
    QgsProcessingException,
    QgsVectorLayer,
    QgsFeatureRequest,
    QgsMapLayer,
    QgsProject
)
from qgis.utils import iface
import os


class DeleteFeaturesAndLAZFiles(QgsProcessingAlgorithm):
    ATTRIBUTE_FIELD = 'ATTRIBUTE_FIELD'
    INPUT_FOLDER = 'INPUT_FOLDER'
    CONFIRM_DELETE = 'CONFIRM_DELETE'

    def tr(self, string):
        """Translate method"""
        return QCoreApplication.translate('DeleteFeaturesAndLAZFiles', string)

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
                self.tr('Select attribute pointing to LAZ file names'),
                options=fields,
                optional=False
            )
        )

        # Folder containing LAZ files
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FOLDER,
                self.tr('Folder containing LAZ files'),
                behavior=QgsProcessingParameterFile.Folder
            )
        )

        # Confirmation parameter
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CONFIRM_DELETE,
                self.tr('Confirm deletion of features and LAZ files'),
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

        # Step 3: Get the LAZ folder path
        laz_folder = self.parameterAsFile(parameters, self.INPUT_FOLDER, context)
        if not os.path.exists(laz_folder):
            raise QgsProcessingException(f"Specified folder does not exist: {laz_folder}")

        confirm_delete = self.parameterAsBool(parameters, self.CONFIRM_DELETE, context)

        # Step 4: Ensure features are selected
        selected_features = layer.selectedFeatures()
        if not selected_features:
            raise QgsProcessingException("No features are selected in the active layer.")

        # Confirm deletion
        if not confirm_delete:
            raise QgsProcessingException("Deletion not confirmed. Enable the 'Confirm deletion' checkbox to proceed.")

        feedback.pushInfo(f"Processing {len(selected_features)} selected features...")

        # Step 5: Process each selected feature
        features_to_delete = []
        laz_files_deleted = 0

        for feature in selected_features:
            laz_filename = feature[attribute_field]
            laz_path = os.path.join(laz_folder, laz_filename)

            feedback.pushInfo(f"Processing feature ID {feature.id()} with LAZ file: {laz_path}")

            # Validate the LAZ file path
            if not os.path.exists(laz_path):
                feedback.reportError(f"LAZ file '{laz_path}' does not exist. Skipping feature ID {feature.id()}.")
                continue

            try:
                # Delete the LAZ file
                os.remove(laz_path)
                laz_files_deleted += 1
                feedback.pushInfo(f"Deleted LAZ file: {laz_path}")

                # Mark feature for deletion
                features_to_delete.append(feature.id())
            except Exception as e:
                feedback.reportError(f"Failed to delete file '{laz_path}': {str(e)}")

        # Step 6: Delete the features from the layer
        if features_to_delete:
            layer.startEditing()
            layer.deleteFeatures(features_to_delete)
            layer.commitChanges()
            feedback.pushInfo(f"Deleted {len(features_to_delete)} features from the layer.")
        else:
            feedback.pushInfo("No features were deleted from the layer.")

        # Final feedback
        feedback.pushInfo(f"Successfully deleted {laz_files_deleted} LAZ files.")
        return {'DELETED_FILES': laz_files_deleted, 'DELETED_FEATURES': len(features_to_delete)}

    def name(self):
        return 'delete_features_and_laz_files'

    def displayName(self):
        return self.tr('Delete Features and Corresponding LAZ Files')

    def group(self):
        return self.tr('LiDAR Preprocessing')

    def groupId(self):
        return 'lidar_processing'

    def shortHelpString(self):
        return self.tr('Deletes selected features and their associated LAZ files specified in an attribute.')

    def createInstance(self):
        return DeleteFeaturesAndLAZFiles()
