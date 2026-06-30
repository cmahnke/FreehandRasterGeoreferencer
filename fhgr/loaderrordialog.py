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
from qgis.PyQt.QtCore import Qt, qDebug
from qgis.PyQt.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from . import utils
from .qt_ui import adjust_dialog_to_content, configure_message_box, load_ui
from .raster_io import RasterLoadError, probe_raster_size


class LoadErrorDialog(QDialog):
    def __init__(self, layer_title, filepath=None, expected_size=None):
        QDialog.__init__(self)
        load_ui(self, "loaderrordialog.ui")

        if filepath is None:
            filepath = layer_title
            layer_title = ""

        self.expected_size = expected_size
        self.lblError.setText("The raster image for this layer could not be found.")
        self.lineEditLayerTitle.setText(layer_title)
        self.lineEditLayerTitle.setToolTip(layer_title)
        self.lineEditMissingPath.setText(filepath)
        self.lineEditMissingPath.setToolTip(filepath)
        if expected_size is not None:
            self.lblExpectedSize.setText(
                "Expected replacement dimensions: "
                f"{expected_size[0]} x {expected_size[1]} pixels."
            )
            self.checkBoxAllowDifferentDimensions.setVisible(True)
        else:
            self.lblExpectedSize.setText(
                "No saved image dimensions are available for this layer."
            )
            self.checkBoxAllowDifferentDimensions.setVisible(False)
        self.lineEditImagePath.setPlaceholderText("Replacement image path")
        QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)
        self.pushButtonBrowse.clicked.connect(self.showBrowserDialog)
        adjust_dialog_to_content(self, min_text_columns=72)

    def clear(self):
        self.lineEditImagePath.setText("")

    def showBrowserDialog(self):
        bDir, found = QgsProject.instance().readEntry(
            utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, None
        )

        if not found or not bDir or not os.path.isdir(bDir):
            bDir = os.path.expanduser("~")

        qDebug(bDir)
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select replacement raster",
            bDir,
            "Rasters (*.png *.bmp *.jpg *.jpeg *.tif *.tiff *.pdf *.jp2 *.ecw);;"
            "All files (*)",
        )
        self.lineEditImagePath.setText(filepath)
        self.lineEditImagePath.setToolTip(filepath)

        if filepath:
            bDir, _ = os.path.split(filepath)
            QgsProject.instance().writeEntry(
                utils.SETTINGS_KEY, utils.SETTING_BROWSER_RASTER_DIR, bDir
            )

    def done(self, ack):
        QApplication.restoreOverrideCursor()
        super().done(ack)

    def accept(self):
        result, message, details = self.validate()
        if result:
            self.done(QDialog.DialogCode.Accepted)
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
                width, height = probe_raster_size(self.imagePath)
            except RasterLoadError as ex:
                result = False
                if len(details) > 0:
                    details += "\n"
                details += str(ex)
            else:
                if (
                    self.expected_size is not None
                    and (width, height) != self.expected_size
                    and not self.checkBoxAllowDifferentDimensions.isChecked()
                ):
                    result = False
                    if len(details) > 0:
                        details += "\n"
                    details += (
                        "The replacement image dimensions are "
                        f"{width} x {height} pixels, but this layer expects "
                        f"{self.expected_size[0]} x {self.expected_size[1]} pixels. "
                        "Enable the different-dimensions checkbox to replace it "
                        "anyway."
                    )

        if not result:
            message = "There were errors in the form"

        return result, message, details
