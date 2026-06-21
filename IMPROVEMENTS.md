# Improvements

This file tracks improvement requests from currently open GitHub issues. It
does not include closed historical issues.

## Documentation and Guidance

- [#71](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/71):
  document direct scale entry for the scale tool, including CRS unit caveats
  such as meters versus US survey feet.
- [#61](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/61):
  document how embedded raster georeferencing is interpreted, and add a clear
  option to ignore embedded georeferencing when the user wants to manually align
  the image.

## Layer Controls

- [#69](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/69):
  add a frame-thickness control next to opacity/transparency controls and store
  it as a layer property used by the layer painter.
- [#67](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/67):
  disable the undo action when no undo history is available, and re-enable it
  only when a transform-changing operation is committed.
- [#13](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/13):
  allow direct numeric entry for translation, rotation, and scale. Rotation is
  already partially implemented; translation and scale should be completed and
  tested.

## Raster Input

- [#64](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/64):
  once raster reading is GDAL-backed, allow any raster format supported by the
  QGIS GDAL build, including ECW where the local QGIS distribution includes the
  driver.

## Export

- [#63](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/63):
  add an export mode that clips output to the current map canvas extent, if this
  remains useful beyond QGIS native export workflows.
- [#52](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/52):
  expose TIFF compression choices, including JPEG compression when supported by
  the local GDAL build.
- [#59](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/59):
  add export quality controls and preserve source bit depth where possible.
- [#57](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/57) and
  [#55](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/55):
  provide clear transparency/nodata handling for the extra bounding-box area
  introduced by rotated exports.

## Transform Tools

- [#40](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/40):
  add more general affine transforms, such as shear and a 3-point or 4-point
  alignment tool, after the current transform math has been moved into pure
  tested helpers.

## Project and Developer Experience

- [#42](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/42):
  continue the code organization work so map tools, missing-file handling, and
  testable transform logic are separated into smaller modules.
