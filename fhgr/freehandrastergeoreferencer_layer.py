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

import os

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataProvider,
    QgsMapLayerRenderer,
    QgsMessageLog,
    QgsPluginLayer,
    QgsPluginLayerType,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QPointF, QRectF, Qt, pyqtSignal, qDebug
from qgis.PyQt.QtGui import QColor, QPainter, QPen
from qgis.PyQt.QtWidgets import QDialog

from . import transform as transform_math, utils
from .loaderrordialog import LoadErrorDialog
from .raster_io import RasterLoadError, load_raster_for_display


class LayerDefaultSettings:
    TRANSPARENCY = 30
    BLEND_MODE = "SourceOver"


class FreehandRasterGeoreferencerLayer(QgsPluginLayer):
    LAYER_TYPE = "FreehandRasterGeoreferencerLayer"
    transformParametersChanged = pyqtSignal(tuple)

    def __init__(self, plugin, filepath, title, screenExtent):
        QgsPluginLayer.__init__(
            self, FreehandRasterGeoreferencerLayer.LAYER_TYPE, title
        )
        self.plugin = plugin
        self.iface = plugin.iface

        self.title = title
        self.filepath = filepath
        self.screenExtent = screenExtent
        self.history = []
        # set custom properties
        self.setCustomProperty("title", title)
        self.setCustomProperty("filepath", self.filepath)

        self.setValid(True)

        self.setTransparency(LayerDefaultSettings.TRANSPARENCY)
        self.setBlendModeByName(LayerDefaultSettings.BLEND_MODE)

        # dummy data: real init is done in intializeLayer
        self.center = QgsPointXY(0, 0)
        self.rotation = 0.0
        self.xScale = 1.0
        self.yScale = 1.0

        self.image = None
        self._raster_display = None
        self.raster_warnings = []
        self.load_error = ""
        self._extent = None

        self.error = False
        self.initializing = False
        self.initialized = False
        self.initializeLayer(screenExtent)

        self.provider = FreehandRasterGeoreferencerLayerProvider(self)

    def dataProvider(self):
        # issue with DBManager if the dataProvider of the QgsLayerPlugin
        # returns None
        return self.provider

    def setScale(self, xScale, yScale):
        self.xScale = xScale
        self.yScale = yScale

    def setRotation(self, rotation):
        # 3 decimals ought to be enough for everybody
        rotation = round(rotation, 3)
        # keep in -180,180 interval
        if rotation < -180:
            rotation += 360
        if rotation > 180:
            rotation -= 360
        self.rotation = rotation

    def setCenter(self, center):
        self.center = center

    def commitTransformParameters(self):
        QgsProject.instance().setDirty(True)
        self._extent = None
        self.setCustomProperty("xScale", self.xScale)
        self.setCustomProperty("yScale", self.yScale)
        self.setCustomProperty("rotation", self.rotation)
        self.setCustomProperty("xCenter", self.center.x())
        self.setCustomProperty("yCenter", self.center.y())
        self.transformParametersChanged.emit((
            self.xScale,
            self.yScale,
            self.rotation,
            self.center,
        ))

    def reprojectTransformParameters(self, oldCrs, newCrs):
        transform = QgsCoordinateTransform(oldCrs, newCrs, QgsProject.instance())

        newCenter = transform.transform(self.center)
        newExtent = transform.transform(self.extent())

        # transform the parameters except rotation
        # TODO rotation could be better handled (maybe check rotation between
        # old and new extent)
        # but not really worth the effort ?
        self.setCrs(newCrs)
        self.setCenter(newCenter)
        self.resetScale(newExtent.width(), newExtent.height())

    def resetTransformParametersToNewCrs(self):
        """
        Attempts to keep the layer on the same region of the map when
        the map CRS is changed
        """
        oldCrs = self.crs()
        newCrs = self.iface.mapCanvas().mapSettings().destinationCrs()
        self.reprojectTransformParameters(oldCrs, newCrs)
        self.commitTransformParameters()

    def setupCrsEvents(self):
        layerId = self.id()

        def removeCrsChangeHandler(layerIds):
            if layerId in layerIds:
                try:
                    self.iface.mapCanvas().destinationCrsChanged.disconnect(
                        self.resetTransformParametersToNewCrs
                    )
                except Exception:
                    pass
                try:
                    QgsProject.instance().disconnect(removeCrsChangeHandler)
                except Exception:
                    pass

        self.iface.mapCanvas().destinationCrsChanged.connect(
            self.resetTransformParametersToNewCrs
        )
        QgsProject.instance().layersRemoved.connect(removeCrsChangeHandler)

    def setupCrs(self):
        mapCrs = self.iface.mapCanvas().mapSettings().destinationCrs()
        self.setCrs(mapCrs)

        self.setupCrsEvents()

    def repaint(self):
        self.repaintRequested.emit()

    def transformParameters(self):
        return (self.center, self.rotation, self.xScale, self.yScale)

    def initializeLayer(self, screenExtent=None):
        if self.error or self.initialized or self.initializing:
            return

        if self.filepath is None:
            return

        self.initializing = True
        try:
            absPath = self.getAbsoluteFilepath()
            replacement_filepath = None

            if not os.path.exists(absPath):
                loadErrorDialog = LoadErrorDialog(
                    self.title, absPath, self.expectedImageSize()
                )
                result = loadErrorDialog.exec()
                if result == QDialog.DialogCode.Accepted:
                    absPath = loadErrorDialog.lineEditImagePath.text()
                    replacement_filepath = utils.toRelativeToQGS(absPath)
                else:
                    self.load_error = f"Raster image was not found: {absPath}"
                    self.error = True
                    self.setValid(False)
                    return

                del loadErrorDialog

            display = load_raster_for_display(absPath)
            if replacement_filepath is not None:
                self.filepath = replacement_filepath
                self.setCustomProperty("filepath", self.filepath)
                QgsProject.instance().setDirty(True)
            self._applyRasterDisplay(display)
            self.setupCrs()

            if screenExtent:
                self.initializeTransformParameters(screenExtent, display)
        except RasterLoadError as ex:
            self.load_error = str(ex)
            self.error = True
            self.setValid(False)
            self.showBarMessage(
                "Raster load failed",
                self.load_error,
                Qgis.MessageLevel.Critical,
                8,
            )
        finally:
            self.initializing = False

    def _applyRasterDisplay(self, display):
        self._raster_display = display
        self.image = display.qimage
        self.raster_warnings = list(display.warnings)
        self.load_error = ""
        self.error = False
        self.initialized = True
        self.setValid(True)
        self._extent = None
        self.setCustomProperty("imageWidth", display.width)
        self.setCustomProperty("imageHeight", display.height)
        for warning in self.raster_warnings:
            self.showBarMessage(
                "Raster display",
                warning,
                Qgis.MessageLevel.Warning,
                10,
            )

    def initializeTransformParameters(self, screenExtent, display):
        if display.geotransform and not self.is_default_geotransform(
            display.geotransform
        ):
            raster_georef = transform_math.georeference_from_geotransform(
                display.geotransform,
                display.width,
                display.height,
                display.crs_wkt,
            )
            self.initializeExistingGeoreferencing(raster_georef)
        else:
            self.setCenter(screenExtent.center())
            self.setRotation(0.0)
            self.resetScale(screenExtent.width(), screenExtent.height())
            self.commitTransformParameters()

    def initializeExistingGeoreferencing(self, raster_georef):
        center = QgsPointXY(raster_georef.center.x, raster_georef.center.y)

        qDebug(
            repr(raster_georef.rotation)
            + " "
            + repr((raster_georef.x_scale, raster_georef.y_scale))
            + " "
            + repr(center)
        )

        self.setRotation(raster_georef.rotation)
        self.setCenter(center)
        self.setScale(raster_georef.x_scale, raster_georef.y_scale)
        self.commitTransformParameters()

        message_shown = False
        if raster_georef.crs_wkt:
            qcrs = QgsCoordinateReferenceSystem(raster_georef.crs_wkt)
            # TODO check change
            if qcrs.description() != self.crs().description():
                # reproject
                try:
                    self.reprojectTransformParameters(qcrs, self.crs())
                    self.commitTransformParameters()
                    self.showBarMessage(
                        "Transform parameters changed: ",
                        "Found existing georeferencing in raster but "
                        "its CRS does not match the CRS of the map. "
                        "Reprojected the extent.",
                        Qgis.MessageLevel.Warning,
                        25,
                    )
                    message_shown = True
                except Exception as ex:
                    QgsMessageLog.logMessage(repr(ex))
                    self.showBarMessage(
                        "CRS does not match",
                        "Found existing georeferencing in raster but "
                        "its CRS does not match the CRS of the map. "
                        "Unable to reproject.",
                        Qgis.MessageLevel.Warning,
                        5,
                    )
                    message_shown = True
        # if no projection info, assume it is the same CRS
        # as the map and no warning
        if not message_shown:
            self.showBarMessage(
                "Georeferencing loaded",
                "Found existing georeferencing in raster",
                Qgis.MessageLevel.Info,
                3,
            )

        # zoom (assume the user wants to work on the image)
        self.iface.mapCanvas().setExtent(self.extent())

    def is_default_geotransform(self, georef):
        """
        Check if there is really a transform or if it is just the default
        made up by GDAL
        """
        return transform_math.is_default_geotransform(georef)

    def resetScale(self, sw, sh):
        x_scale, y_scale = transform_math.fit_scale_to_extent(
            self.image.width(), self.image.height(), sw, sh
        )
        self.setScale(x_scale, y_scale)

    def replaceImage(self, filepath, title):
        try:
            display = load_raster_for_display(filepath)
        except RasterLoadError as ex:
            QgsMessageLog.logMessage(repr(ex))
            self.showBarMessage(
                "Raster load failed",
                str(ex),
                Qgis.MessageLevel.Critical,
                8,
            )
            return False

        self.title = title
        self.filepath = filepath

        # set custom properties
        self.setCustomProperty("title", title)
        self.setCustomProperty("filepath", self.filepath)
        self.setName(title)

        self._applyRasterDisplay(display)
        QgsProject.instance().setDirty(True)
        self.repaint()
        return True

    def clone(self):
        layer = FreehandRasterGeoreferencerLayer(
            self.plugin, self.filepath, self.title, self.screenExtent
        )
        layer.center = self.center
        layer.rotation = self.rotation
        layer.xScale = self.xScale
        layer.yScale = self.yScale
        layer.commitTransformParameters()
        return layer

    def getAbsoluteFilepath(self):
        if not self.filepath:
            return ""
        if not os.path.isabs(self.filepath):
            # relative to QGS file
            qgsPath = QgsProject.instance().fileName()
            qgsFolder, _ = os.path.split(qgsPath)
            filepath = os.path.join(qgsFolder, self.filepath)
        else:
            filepath = self.filepath

        return filepath

    def expectedImageSize(self):
        width = int(self.customProperty("imageWidth", 0) or 0)
        height = int(self.customProperty("imageHeight", 0) or 0)
        if width > 0 and height > 0:
            return (width, height)
        if self.image is not None:
            return (self.image.width(), self.image.height())
        return None

    def extent(self):
        self.initializeLayer()
        if not self.initialized:
            qDebug("Not Initialized")
            return QgsRectangle(0, 0, 1, 1)

        if self._extent:
            return self._extent

        corners = tuple(self._pointFromQgs(point) for point in self.cornerCoordinates())
        left, bottom, right, top = transform_math.extent_from_corners(corners)

        # recenter + create rectangle
        self._extent = QgsRectangle(left, bottom, right, top)
        return self._extent

    def cornerCoordinates(self):
        return self.transformedCornerCoordinates(
            self.center, self.rotation, self.xScale, self.yScale
        )

    def transformedCornerCoordinates(self, center, rotation, xScale, yScale):
        return tuple(
            self._qgsPointFromPoint(point)
            for point in transform_math.corner_coordinates(
                self.image.width(),
                self.image.height(),
                self._pointFromQgs(center),
                rotation,
                xScale,
                yScale,
            )
        )

    def transformedCornerCoordinatesFromPoint(
        self, startPoint, rotation, xScale, yScale
    ):
        return tuple(
            self._qgsPointFromPoint(point)
            for point in transform_math.corner_coordinates_from_point(
                self.image.width(),
                self.image.height(),
                self._pointFromQgs(self.center),
                self.rotation,
                self.xScale,
                self.yScale,
                self._pointFromQgs(startPoint),
                rotation,
                xScale,
                yScale,
            )
        )

    def moveCenterFromPointRotate(self, startPoint, rotation, xScale, yScale):
        center = transform_math.center_from_point_transform(
            self.image.width(),
            self.image.height(),
            self._pointFromQgs(self.center),
            self.rotation,
            self.xScale,
            self.yScale,
            self._pointFromQgs(startPoint),
            rotation,
            xScale,
            yScale,
        )
        self.center = self._qgsPointFromPoint(center)

    def _pointFromQgs(self, point):
        return transform_math.Point(point.x(), point.y())

    def _qgsPointFromPoint(self, point):
        return QgsPointXY(point.x, point.y)

    def createMapRenderer(self, rendererContext):
        return FreehandRasterGeoreferencerLayerRenderer(self, rendererContext)

    def setBlendModeByName(self, modeName):
        self.blendModeName = modeName
        blendMode = getattr(
            QPainter.CompositionMode,
            "CompositionMode_" + modeName,
            QPainter.CompositionMode.CompositionMode_SourceOver,
        )
        self.setBlendMode(blendMode)
        self.setCustomProperty("blendMode", modeName)

    def setTransparency(self, transparency):
        self.transparency = transparency
        self.setCustomProperty("transparency", transparency)

    def draw(self, renderContext):
        if renderContext.extent().isEmpty():
            qDebug("Drawing is skipped because map extent is empty.")
            return True

        self.initializeLayer()
        if not self.initialized:
            qDebug("Drawing is skipped because nothing to draw.")
            return True

        painter = renderContext.painter()
        painter.save()
        self.prepareStyle(painter)
        self.drawRaster(renderContext)
        painter.restore()

        return True

    def drawRaster(self, renderContext):
        painter = renderContext.painter()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.map2pixel = renderContext.mapToPixel()

        scaleX = self.xScale / self.map2pixel.mapUnitsPerPixel()
        scaleY = self.yScale / self.map2pixel.mapUnitsPerPixel()

        rect = QRectF(
            QPointF(-self.image.width() / 2.0, -self.image.height() / 2.0),
            QPointF(self.image.width() / 2.0, self.image.height() / 2.0),
        )
        mapCenter = self.map2pixel.transform(self.center)

        # draw the image on the map canvas
        painter.translate(QPointF(mapCenter.x(), mapCenter.y()))
        painter.rotate(self.rotation)
        painter.scale(scaleX, scaleY)
        painter.drawImage(rect, self.image)

        painter.setOpacity(1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen()
        pen.setColor(QColor(0, 0, 0))
        pen.setWidth(3)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRect(rect)

    def prepareStyle(self, painter):
        painter.setOpacity(1.0 - self.transparency / 100.0)

    def readXml(self, node, context):
        self.readCustomProperties(node)
        self.title = self.customProperty("title", "")
        self.filepath = self.customProperty("filepath", "")
        self.xScale = float(self.customProperty("xScale", 1.0))
        self.yScale = float(self.customProperty("yScale", 1.0))
        self.rotation = float(self.customProperty("rotation", 0.0))
        xCenter = float(self.customProperty("xCenter", 0.0))
        yCenter = float(self.customProperty("yCenter", 0.0))
        self.center = QgsPointXY(xCenter, yCenter)
        self.setTransparency(
            int(self.customProperty("transparency", LayerDefaultSettings.TRANSPARENCY))
        )
        self.setBlendModeByName(
            self.customProperty("blendMode", LayerDefaultSettings.BLEND_MODE)
        )
        return True

    def writeXml(self, node, doc, context):
        element = node.toElement()
        self.writeCustomProperties(node, doc)
        element.setAttribute("type", "plugin")
        element.setAttribute("name", FreehandRasterGeoreferencerLayer.LAYER_TYPE)
        return True

    def freehand_metadata(self):
        lines = []
        fmt = "%s:\t%s"
        lines.append(fmt % (self.tr("Title"), self.title))
        stored_path = self.filepath or ""
        resolved_path = self.getAbsoluteFilepath()
        if resolved_path:
            resolved_path = os.path.normpath(resolved_path)
        lines.append(fmt % (self.tr("Stored path"), stored_path))
        lines.append(fmt % (self.tr("Resolved path"), resolved_path))
        lines.append(
            fmt
            % (
                self.tr("File exists"),
                str(bool(resolved_path and os.path.exists(resolved_path))),
            )
        )
        lines.append(fmt % (self.tr("Layer initialized"), str(self.initialized)))
        if self.load_error:
            lines.append(fmt % (self.tr("Load error"), self.load_error))
        expected_size = self.expectedImageSize()
        image_width = self.image.width() if self.image is not None else 0
        image_height = self.image.height() if self.image is not None else 0
        if expected_size is not None and image_width == 0 and image_height == 0:
            image_width, image_height = expected_size
        lines.append(fmt % (self.tr("Image Width"), str(image_width)))
        lines.append(fmt % (self.tr("Image Height"), str(image_height)))
        lines.append(fmt % (self.tr("Rotation (CW)"), str(self.rotation)))
        lines.append(fmt % (self.tr("X center"), str(self.center.x())))
        lines.append(fmt % (self.tr("Y center"), str(self.center.y())))
        lines.append(fmt % (self.tr("X scale"), str(self.xScale)))
        lines.append(fmt % (self.tr("Y scale"), str(self.yScale)))
        lines.append(
            self.tr(
                "Plugin layer source is stored in custom properties; an empty "
                "layer-tree source and dummy provider URI are expected."
            )
        )

        return "\n".join(lines)

    def log(self, msg):
        qDebug(msg)

    def dump(self, detail=False, bbox=None):
        pass

    def showStatusMessage(self, msg, timeout):
        self.iface.mainWindow().statusBar().showMessage(msg, timeout)

    def showBarMessage(self, title, text, level, duration):
        self.iface.messageBar().pushMessage(title, text, level, duration)

    def transparencyChanged(self, val):
        QgsProject.instance().setDirty(True)
        self.setTransparency(val)
        self.repaintRequested.emit()

    def setTransformContext(self, transformContext):
        pass


class FreehandRasterGeoreferencerLayerType(QgsPluginLayerType):
    def __init__(self, plugin):
        QgsPluginLayerType.__init__(self, FreehandRasterGeoreferencerLayer.LAYER_TYPE)
        self.plugin = plugin

    def createLayer(self):
        return FreehandRasterGeoreferencerLayer(self.plugin, None, "", None)

    def showLayerProperties(self, layer):
        from .propertiesdialog import PropertiesDialog

        dialog = PropertiesDialog(layer)
        dialog.horizontalSlider_Transparency.valueChanged.connect(
            layer.transparencyChanged
        )
        dialog.spinBox_Transparency.valueChanged.connect(layer.transparencyChanged)

        dialog.exec()

        dialog.horizontalSlider_Transparency.valueChanged.disconnect(
            layer.transparencyChanged
        )
        dialog.spinBox_Transparency.valueChanged.disconnect(layer.transparencyChanged)
        return True


class FreehandRasterGeoreferencerLayerProvider(QgsDataProvider):
    def __init__(self, layer):
        QgsDataProvider.__init__(self, "dummyURI")
        self.layer = layer

    def name(self):
        return "FreehandRasterGeoreferencerLayerProvider"

    def description(self):
        return "Freehand raster georeferencer layer provider"

    def isValid(self):
        return True

    def crs(self):
        return self.layer.crs()

    def extent(self):
        return self.layer.extent()


class FreehandRasterGeoreferencerLayerRenderer(QgsMapLayerRenderer):
    """
    Custom renderer: in QGIS3 no implementation is provided for
    QgsPluginLayers
    """

    def __init__(self, layer, rendererContext):
        QgsMapLayerRenderer.__init__(self, layer.id())
        self.layer = layer
        self.rendererContext = rendererContext

    def render(self):
        # same implementation as for QGIS2
        return self.layer.draw(self.rendererContext)
