
## Open Issue Triage: Bugs and Correctness

This triage only covers issues that are currently open in GitHub.

- Metadata and layer tooltip crashes:
  [#72](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/72) and
  [#73](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/73)
  report `FreehandRasterGeoreferencerLayer.metadata()` returning a string where
  newer QGIS expects `QgsLayerMetadata`. This is a QGIS API correctness issue,
  not just a tooltip issue, because it can freeze or crash QGIS layout dialogs.
- Missing or relocated source images:
  [#70](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/70),
  [#66](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/66),
  [#62](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/62),
  [#50](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/50),
  and [#42](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/42)
  all point to the same root class: project reload can enter a broken state
  when a plugin-layer source image is missing, moved, or not resolved
  automatically. This must be handled as a recoverable invalid-layer state.
- Path persistence and project reload:
  [#53](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/53),
  [#45](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/45), and
  [#41](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/41)
  describe wrong locations, absolute/relative path confusion, and crashes when
  reloading projects. This should be tested with relative paths, absolute paths,
  moved projects, and CRS changes.
- CRS and transform lifecycle:
  [#60](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/60)
  reports `_extent` access before initialization during CRS handling.
  [#34](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/34)
  reports exported rotation being wrong when the QGIS map canvas is rotated.
  Both should be covered by pure transform tests plus QGIS integration tests.
- Raster loading limits and unsupported formats:
  [#54](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/54)
  reports a crash drawing a large raster.
  [#48](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/48)
  reports large TIFFs loading with width and height as zero.
  [#65](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/65)
  reports some `.jpeg` files not being recognized.
  [#64](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/64)
  asks for formats such as ECW that QGIS can open. These all support replacing
  Qt image reading with GDAL-backed raster access.
- Export quality and transparency:
  [#59](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/59)
  reports export quality loss and 16-bit data being reduced to 8-bit.
  [#57](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/57) and
  [#55](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/55)
  report black or opaque borders around rotated/exported images. Export should
  preserve alpha/nodata semantics and expose quality/compression choices.

=> add a warning about export to JPEG if needed.

- Map-tool state:
  [#49](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/49)
  reports the 2-point tool failing after the built-in QGIS georeferencer uses
  "From Map Canvas".
  [#45](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/45) also
  reports plugin toolbar buttons sometimes needing a second click after another
  map tool is activated.
  [#42](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/42)
  also reports map-tool GUI regressions. The active layer and active map-tool
  state need clearer ownership.
- Toolbar state warning:
  [#68](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/68)
  reports a `QMainWindow::saveState()` warning for a toolbar with no
  `objectName`. The plugin toolbar should set a stable object name.
- Existing raster georeferencing:
  [#61](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/61)
  reports a TIFF with existing georeferencing not loading usefully and asks for
  a way to ignore or keep the embedded points. GDAL import should make this an
  explicit user choice.
- source inconsistency:
  [#58](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/58)
  The issue comments also show project XML where plugin layers have `source=""` in the layer tree, while the real image path is stored in custom properties. That should be documented and made more diagnosable in the UI.


## Open Issues Already Fixed or Partially Covered

- [#72](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/72):
  the QGIS 4 branch no longer overrides `QgsMapLayer.metadata()` with a string
  helper. The plugin-specific text helper is now `freehand_metadata()`, which
  should avoid the `str cannot be converted to QgsLayerMetadata` failure. This
  still needs manual validation in QGIS because the issue is UI-triggered.
- [#73](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/73):
  the `metadata()` API-conflict part is covered by the same rename as #72.
  The remaining risk is that `freehand_metadata()` still reads `self.image`, so
  invalid or partially initialized layers need a guard before this issue can be
  considered fully fixed.
- [#45](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/45):
  the issue comment says the relative-path part was already corrected in source
  before this port. The remaining open part is toolbar/map-tool responsiveness.


## Issue #70 Findings

Issue #70 is titled "Software stops working". The report says the plugin stops
working when a linked image used by a Freehand Raster Georeferencer layer is
missing or has moved.

The expected behavior should be:

- opening a project with a missing linked image must not break QGIS or stop the
  plugin from loading other layers;
- the affected plugin layer should become an invalid or recoverable placeholder,
  not a partially initialized layer;
- the recovery UI should show the layer name, stored path, resolved path, and
  whether the file exists;
- cancelling missing-file recovery should leave the layer safely invalid and
  should not continue into raster reading, GDAL access, extent calculations, or
  rendering;
- selecting a replacement image should update only that layer's stored path and
  should preserve its transform parameters;
- if the replacement image dimensions differ from the original image dimensions,
  the plugin should warn before applying it, because the existing transform may
  no longer match the intended raster.