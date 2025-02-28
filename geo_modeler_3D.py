# -*- coding: utf-8 -*-
"""
/***************************************************************************
 3DGeoModeler
                                 A QGIS plugin
 A suite of tools and guides for generating surfaces and 3D models.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-12-12
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Esbern Holmes /Roskilde University
        email                : holmes@ruc.dk
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import(
    QgsApplication,
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

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .geo_modeler_3D_dialog import GeoModelerDialog3D
from .provider import MyProcessingProvider
import os.path
from qgis.core import QgsProject, QgsVectorLayer
import processing


class GeoModeler3D:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize the provider
        self.provider = None
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            '3DGeoModeler_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&3D GeoModeler')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('3DGeoModeler', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/geo_modeler_3D/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'3D GeoModeler'),
            callback=self.run,
            parent=self.iface.mainWindow())
        
        # Add Step 0: Link to guide
        self.add_action(
            icon_path,
            text=self.tr(u'Step 0: Read the Guide'),
            callback=self.open_guide,
            parent=self.iface.mainWindow()
        )
 
        # Add Step 1: Load GeoJSON file
        self.add_action(
            icon_path,
            text=self.tr(u'Step 1: Access the Index File'),
            callback=self.call_load_geojson,
            parent=self.iface.mainWindow()
        )
  
        # Add Step 12: Load GeoJSON file
        self.add_action(
            icon_path,
            text=self.tr(u'Step 2: download laz files'),
            callback=self.call_download_laz,
            parent=self.iface.mainWindow()
        )
        
        """Add the processing provider."""
        self.provider = MyProcessingProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)
        

        # will be set False in run()
        self.first_start = True
    
    def open_guide(self):
        """Open the guide link in a message box."""
        QMessageBox.information(
            self.iface.mainWindow(),
            "3D GeoModeler Guide",
            "Visit the guide at: https://geogitmatics.online"
    )
        
    def call_load_geojson(self):
        """Call the processing script to load GeoJSON."""
        try:
            params = {
                'URL': 'https://raw.githubusercontent.com/Esbern/3d_geo_modeler_data/refs/heads/main/punktsky_grid.geojson'
            }
            result = processing.run("3D_geo_modeler:load_geojson", params)
            QMessageBox.information(
                self.iface.mainWindow(),
                "Success",
                f"Result: {result['Result']}"
            )
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Could not load GeoJSON: {e}"
            )
            
    def call_download_laz(self):
        """Call the processing script to display its dialog."""
        try:
            result = processing.execAlgorithmDialog("3D_geo_modeler:download_files_from_ftps")
            if result:
                QMessageBox.information(
                    self.iface.mainWindow(),
                    "Success",
                    "The processing script ran successfully."
                )
            else:
                QMessageBox.information(
                    self.iface.mainWindow(),
                    "Cancelled",
                    "The user cancelled the processing dialog."
                )
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Could not run the processing script: {e}"
            )
            
    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&3D GeoModeler'),
                action)
            self.iface.removeToolBarIcon(action)
            
        """Remove the processing provider."""
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = GeoModelerDialog3D()

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass


