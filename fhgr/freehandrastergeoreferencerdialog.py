"""
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os.path

from qgis.core import QgsProject
from qgis.PyQt.QtGui import QAction
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMenu, QMessageBox

from . import utils
from .qt_ui import adjust_dialog_to_content, configure_message_box, load_ui
from .raster_io import RasterLoadError, probe_raster_size


class FreehandRasterGeoreferencerDialog(QDialog):
    REPLACE = 2
    DUPLICATE = 3

    def __init__(self):
        QDialog.__init__(self)
        load_ui(self, "freehandrastergeoreferencerdialog.ui")
        adjust_dialog_to_content(self)
        self.configureAdvancedMenu()
        self.pushButtonAdd.clicked.connect(self.addNew)
        self.pushButtonCancel.clicked.connect(self.reject)
        self.pushButtonBrowse.clicked.connect(self.showBrowserDialog)
        self.toolButtonAdvanced.clicked.connect(self.showAdvancedMenu)

    def clear(self, layer):
        self.layer = layer
        if layer is None:
            imagepath = ""
        else:
            imagepath = layer.filepath

        self.lineEditImagePath.setText(imagepath)
        self.lineEditImagePath.setToolTip(imagepath)
        adjust_dialog_to_content(self)

    def showBrowserDialog(self):
        bDir, found = QgsProject.instance().readEntry(
            utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, None
        )
        if not found or not bDir or not os.path.isdir(bDir):
            bDir = os.path.expanduser("~")

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select raster",
            bDir,
            "Rasters (*.png *.bmp *.jpg *.jpeg *.tif *.tiff *.pdf *.jp2 *.ecw);;"
            "All files (*)",
        )

        if filepath:
            self.lineEditImagePath.setText(filepath)
            self.lineEditImagePath.setToolTip(filepath)
            bDir, _ = os.path.split(filepath)
            QgsProject.instance().writeEntry(
                utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, bDir
            )

    def configureAdvancedMenu(self):
        action1 = QAction("Replace image for selected layer", self)
        action2 = QAction("Duplicate selected layer", self)

        action1.triggered.connect(self.replaceImage)
        action2.triggered.connect(self.duplicateLayer)

        menu = QMenu(self)
        menu.addAction(action1)
        menu.addAction(action2)

        self.toolButtonAdvanced.setMenu(menu)

    def showAdvancedMenu(self):
        self.toolButtonAdvanced.showMenu()

    def replaceImage(self):
        self.accept(self.REPLACE)

    def duplicateLayer(self):
        self.accept(self.DUPLICATE, False)

    def addNew(self):
        self.accept()

    def accept(self, retValue=QDialog.DialogCode.Accepted, validate=True):
        if not validate:
            self.done(retValue)
            return

        result, message, details = self.validate()
        if result:
            self.done(retValue)
        else:
            msgBox = QMessageBox()
            msgBox.setWindowTitle("Error")
            msgBox.setText(message)
            msgBox.setDetailedText(details)
            msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
            configure_message_box(msgBox)
            msgBox.exec()

    def validate(self):
        result = True
        message = ""
        details = ""

        self.imagePath = self.lineEditImagePath.text()
        if not os.path.isfile(self.imagePath):
            result = False
            details += "The path must be an image file"
        else:
            try:
                probe_raster_size(self.imagePath)
            except RasterLoadError as ex:
                result = False
                if len(details) > 0:
                    details += "\n"
                details += str(ex)

        if not result:
            message = "There were errors in the form"

        return result, message, details
