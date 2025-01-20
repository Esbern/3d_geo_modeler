# This file is part of the QGIS plugin developed for the Innotech – TaskForce Interreg project.
# 
# Copyright (C) 2025 Esbern Holmes, Roskilde University
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
    QgsProcessingParameterString,
    QgsProcessingException,
    QgsVectorLayer,
    QgsFillSymbol,
    QgsLinePatternFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsProject
)
from PyQt5.QtGui import QColor

class LoadGeoJSON(QgsProcessingAlgorithm):
    """Processing script to load a GeoJSON file with hatched style."""

    URL = 'URL'

    def tr(self, string):
        """Translate the string."""
        return QCoreApplication.translate('LoadGeoJSON', string)

    def initAlgorithm(self, config=None):
        """Define parameters."""
        self.addParameter(
            QgsProcessingParameterString(
                self.URL,
                self.tr('Enter the URL of the GeoJSON file'),
                defaultValue='https://raw.githubusercontent.com/Esbern/3d_geo_modeler_data/refs/heads/main/punktsky_grid.geojson'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """Main logic for loading the GeoJSON file."""
        url = self.parameterAsString(parameters, self.URL, context)

        if not url:
            raise QgsProcessingException(self.tr("No URL provided."))

        feedback.pushInfo(f"Loading GeoJSON from: {url}")

        # Load the GeoJSON as a vector layer

        layer = QgsVectorLayer(url, "Punktsky_grid", "ogr")

        if not layer.isValid():
            raise QgsProcessingException(self.tr("Failed to load the GeoJSON file."))

        feedback.pushInfo("Applying hatched style...")

        # Create a hatched style
        line_pattern_fill = QgsLinePatternFillSymbolLayer()
        line_pattern_fill.setLineWidth(0.26)
        line_pattern_fill.setDistance(2.0)
        line_pattern_fill.setAngle(45)
        line_pattern_fill.setColor(QColor(55, 126, 184))

        outline = QgsSimpleLineSymbolLayer()
        outline.setColor(QColor(0, 0, 0))
        outline.setWidth(0.46)

        fill_symbol = QgsFillSymbol()
        fill_symbol.changeSymbolLayer(0, line_pattern_fill)
        fill_symbol.appendSymbolLayer(outline)

        layer.renderer().setSymbol(fill_symbol)

        # Add the layer to the project
        QgsProject.instance().addMapLayer(layer)
        feedback.pushInfo("GeoJSON file loaded successfully with hatched style.")

        return {'Result': f"GeoJSON loaded: {layer.name()}"}

    def name(self):
        """Algorithm name."""
        return 'load_geojson'

    def displayName(self):
        """Display name for the algorithm."""
        return self.tr('Load GeoJSON File')

    def group(self):
        return self.tr('LiDAR Preprocessing')

    def groupId(self):
        return 'lidar_processing'

    def shortHelpString(self):
        """Help string."""
        return self.tr('Loads a GeoJSON file from a URL and applies a hatched style.')

    def createInstance(self):
        """Create an instance of the algorithm."""
        return LoadGeoJSON()
