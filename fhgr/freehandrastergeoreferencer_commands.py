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

import math
import os

from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgsMessageBar
from qgis.PyQt.QtCore import QPointF, QRectF, QSize, qDebug
from qgis.PyQt.QtGui import QColor, QImage, QImageWriter, QPainter

from . import transform as transform_math, utils


class ExportGeorefRasterCommand:
    def __init__(self, iface):
        self.iface = iface

    def exportGeorefRaster(
        self, layer, rasterPath, isPutRotationInWorldFile, isExportOnlyWorldFile
    ):
        baseRasterFilePath, _ = os.path.splitext(rasterPath)
        # suppose supported format already checked
        rasterFormat = utils.imageFormat(rasterPath)

        try:
            originalWidth = layer.image.width()
            originalHeight = layer.image.height()
            radRotation = layer.rotation * math.pi / 180

            if isPutRotationInWorldFile or isExportOnlyWorldFile:
                # keep the image as is and put all transformation params
                # in world file
                img = layer.image

                world_file_transform = transform_math.world_file_transform_for_image(
                    originalWidth,
                    originalHeight,
                    transform_math.Point(layer.center.x(), layer.center.y()),
                    layer.rotation,
                    layer.xScale,
                    layer.yScale,
                )

            else:
                # transform the image with rotation and scaling between the
                # axes
                # maintain at least the original resolution of the raster
                ratio = layer.xScale / layer.yScale
                if ratio > 1:
                    # increase x
                    scaleX = ratio
                    scaleY = 1
                else:
                    # increase y
                    scaleX = 1
                    scaleY = 1.0 / ratio

                width = abs(scaleX * originalWidth * math.cos(radRotation)) + abs(
                    scaleY * originalHeight * math.sin(radRotation)
                )
                height = abs(scaleX * originalWidth * math.sin(radRotation)) + abs(
                    scaleY * originalHeight * math.cos(radRotation)
                )

                qDebug(f"wh {width:f},{height:f}")

                img = QImage(
                    QSize(math.ceil(width), math.ceil(height)),
                    QImage.Format.Format_ARGB32,
                )
                # transparent background
                img.fill(QColor(0, 0, 0, 0))

                painter = QPainter(img)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                # painter.setRenderHint(
                #     QPainter.RenderHint.SmoothPixmapTransform, True
                # )

                rect = QRectF(
                    QPointF(-layer.image.width() / 2.0, -layer.image.height() / 2.0),
                    QPointF(layer.image.width() / 2.0, layer.image.height() / 2.0),
                )

                painter.translate(QPointF(width / 2.0, height / 2.0))
                painter.rotate(layer.rotation)
                painter.scale(scaleX, scaleY)
                painter.drawImage(rect, layer.image)
                painter.end()

                extent = layer.extent()
                world_file_transform = transform_math.world_file_transform_for_extent(
                    width,
                    height,
                    (
                        extent.xMinimum(),
                        extent.yMinimum(),
                        extent.xMaximum(),
                        extent.yMaximum(),
                    ),
                )

            if not isExportOnlyWorldFile:
                # export image
                if rasterFormat == "tif":
                    writer = QImageWriter()
                    # use LZW compression for tiff
                    # useful for scanned documents (mostly white)
                    writer.setCompression(1)
                    writer.setFormat(b"TIFF")
                    writer.setFileName(rasterPath)
                    writer.write(img)
                else:
                    img.save(rasterPath, rasterFormat)

            worldFilePath = baseRasterFilePath + "."
            if rasterFormat == "jpg":
                worldFilePath += "jgw"
            elif rasterFormat == "png":
                worldFilePath += "pgw"
            elif rasterFormat == "bmp":
                worldFilePath += "bpw"
            elif rasterFormat == "tif":
                worldFilePath += "tfw"

            with open(worldFilePath, "w") as writer:
                # order is as described at
                # http://webhelp.esri.com/arcims/9.3/General/topics/author_world_files.htm
                writer.write(
                    "\n".join(
                        f"{value:.13f}" for value in world_file_transform.as_lines()
                    )
                )

            crsFilePath = rasterPath + ".aux.xml"
            with open(crsFilePath, "w") as writer:
                writer.write(
                    self.auxContent(
                        self.iface.mapCanvas().mapSettings().destinationCrs()
                    )
                )

            widget = QgsMessageBar.createMessage(
                "Raster Geoferencer", "Raster exported successfully."
            )
            self.iface.messageBar().pushWidget(widget, Qgis.MessageLevel.Info, 2)
        except Exception as ex:
            QgsMessageLog.logMessage(repr(ex))
            widget = QgsMessageBar.createMessage(
                "Raster Geoferencer",
                "There was an error performing this command. "
                "See QGIS Message log for details.",
            )
            self.iface.messageBar().pushWidget(widget, Qgis.MessageLevel.Critical, 5)

    def auxContent(self, crs):
        content = """<PAMDataset>
  <Metadata domain="xml:ESRI" format="xml">
    <GeodataXform xsi:type="typens:IdentityXform" 
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
      xmlns:xs="http://www.w3.org/2001/XMLSchema" 
      xmlns:typens="http://www.esri.com/schemas/ArcGIS/9.2">
      <SpatialReference xsi:type="typens:%sCoordinateSystem">
        <WKT>%s</WKT>
      </SpatialReference>
    </GeodataXform>
  </Metadata>
</PAMDataset>"""  # noqa
        geogOrProj = "Geographic" if crs.isGeographic() else "Projected"
        return content % (geogOrProj, crs.toWkt())
