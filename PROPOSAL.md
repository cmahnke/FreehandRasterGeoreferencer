# Proposal: Organization, Correctness, GDAL Raster Reading, and HiDPI Dialogs

## Summary

This plugin should be organized around a small QGIS-facing shell and testable
core modules. The highest-value correctness change is to stop using Qt image
readers for raster input and instead use GDAL from the QGIS runtime for all
raster loading. In parallel, dialogs should be converted from fixed-position
widgets to layouts so they scale correctly on HiDPI displays and translated or
larger system fonts.

This proposal targets QGIS 4 only. It does not preserve QGIS 3 compatibility.

## Current Problems

- Raster loading is inconsistent:
  - most image formats are read with `QImageReader`;
  - PDFs are read through `QgsRasterLayer.previewAsImage`;
  - TIFFs receive partial GDAL preprocessing only when Qt cannot display them
    well.
- `FreehandRasterGeoreferencerLayer` mixes QGIS layer behavior, raster loading,
  transform math, canvas rendering, project persistence, CRS handling, and user
  dialogs.
- Several correctness-sensitive calculations are hard to test outside QGIS:
  world-file coefficients, geotransform import, corner coordinates, CRS
  reprojection behavior, undo state, and image data conversion.
- Dialogs still include fixed widget geometries in `.ui` files. That is fragile
  for HiDPI scaling and directly matches issue #58:
  https://github.com/gvellut/FreehandRasterGeoreferencer/issues/58.
- The plugin still stores display pixels as a `QImage`, which is acceptable for
  painting, but the creation of that `QImage` should be driven by GDAL data and
  explicit conversion rules, not by Qt's file readers.
- Missing-file recovery is confusing: plugin layers appear in the project layer
  tree with `source=""` and provider `FreehandRasterGeoreferencerLayerProvider`,
  while the actual raster path is stored later as the custom property
  `filepath`. That is technically how plugin layers are persisted today, but it
  makes project-file diagnosis hard and contributes to user confusion when paths
  break after moving a project.

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
- Dialog scaling:
  [#58](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/58)
  reports unreadable dialogs on Windows HiDPI scaling. This is both a usability
  issue and a correctness issue because the hidden missing-file name can cause
  users to replace the wrong raster.
- Toolbar state warning:
  [#68](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/68)
  reports a `QMainWindow::saveState()` warning for a toolbar with no
  `objectName`. The plugin toolbar should set a stable object name.
- Existing raster georeferencing:
  [#61](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/61)
  reports a TIFF with existing georeferencing not loading usefully and asks for
  a way to ignore or keep the embedded points. GDAL import should make this an
  explicit user choice.

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

## Issue #58 Findings

Issue #58 is titled "Dialogs are unreadable with Windows screen scaling!" The
report describes a Surface Book with a 3000x2000 physical screen scaled by
Windows 10 to an effective 1500x1000 desktop.

The concrete failures are:

- the missing-file dialog opens too small;
- the resize handle is hard to grab;
- resizing the dialog outline does not make all text readable;
- the missing file name is hidden by the folder/path field;
- the user may choose the wrong replacement file because the dialog does not
  clearly show which image is missing;
- a second error dialog has correctly scaled text but still opens with most of
  the text hidden until resized.

The issue comments also show project XML where plugin layers have
`source=""` in the layer tree, while the real image path is stored in custom
properties. That should be documented and made more diagnosable in the UI.

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

## Target Architecture

- Keep `fhgr/` as the plugin package.
- Split code into these boundaries:
  - `qgis_plugin.py` or current `freehandrastergeoreferencer.py`: QGIS actions,
    menus, toolbar, map-tool wiring.
  - `layer.py`: QGIS `QgsPluginLayer` integration only.
  - `raster_io.py`: GDAL-backed raster opening, display conversion, geotransform
    and CRS extraction.
  - `transform.py`: pure geometry and affine/world-file math.
  - `export.py`: export workflow and world-file/aux XML writing.
  - `dialogs/` or existing dialog modules: UI behavior only.
  - `qt_image.py`: narrow conversion from GDAL/numpy display buffers to `QImage`.
- Use dataclasses for non-QGIS state where possible:
  - `RasterDisplayImage`: `qimage`, `width`, `height`, `source_path`,
    `was_rescaled`, `warnings`.
  - `RasterGeoreference`: center, rotation, x/y scale, CRS WKT, raw geotransform.
  - `WorldFileTransform`: `a`, `d`, `b`, `e`, `c`, `f`.

## GDAL Raster Reading Plan

1. Introduce `raster_io.py` with a single public entry point:
   `load_raster_for_display(path) -> RasterDisplayImage`.
2. Use `osgeo.gdal` from the QGIS Python environment:
   - open with `gdal.OpenEx(path, gdal.OF_RASTER)`;
   - fail with clear messages when GDAL cannot open the file;
   - read size, band count, data type, color interpretation, nodata, alpha, and
     geotransform.
3. Convert GDAL bands to a display buffer explicitly:
   - 1 band: grayscale, respecting color tables where present;
   - 2 bands: grayscale plus alpha when the second band is alpha, otherwise
     warn and use the first band;
   - 3 bands: RGB;
   - 4+ bands: RGBA when alpha exists, otherwise first RGB-like bands by color
     interpretation or first three bands with a warning.
4. Normalize non-Byte data for display using deterministic rules:
   - preserve Byte values directly;
   - for UInt16/Float/etc., scale to 8-bit from valid min/max or GDAL
     statistics;
   - ignore nodata in min/max when possible;
   - return a warning when display pixels were rescaled.
5. Convert the final numpy buffer to `QImage` in one small adapter function.
   Keep ownership of the backing buffer explicit so the `QImage` remains valid.
6. Replace current `QImageReader` and `QgsRasterLayer.previewAsImage` paths in
   `FreehandRasterGeoreferencerLayer.initializeLayer()` and `replaceImage()`.
7. Keep export behavior initially compatible: export from the display `QImage`
   unless "only world file" is selected. A later improvement can use GDAL for
   transformed raster output too.

## HiDPI Dialog Plan

1. Convert all `.ui` files to layout-based designs:
   - remove fixed child-widget `geometry` blocks;
   - use `QVBoxLayout`, `QGridLayout`, `QFormLayout`, and `QDialogButtonBox`;
   - use expanding line edits for file paths;
   - avoid hard-coded point sizes like the current `Advanced...` button font.
2. Keep UI files loaded at runtime with `loadUi`.
3. Set useful dialog constraints after loading:
   - reasonable minimum width;
   - no fixed height unless truly necessary;
   - `adjustSize()` after dynamic text is applied for error dialogs.
4. Make long text wrap:
   - missing-file labels, including the full missing raster path;
   - validation messages;
   - tooltips and property text areas.
5. Improve missing-file recovery UX:
   - show the missing path in a selectable, wrapping text field;
   - show the layer title separately from the file path;
   - make the replacement path chooser clearly tied to that missing layer;
   - validate that replacing a file updates only that plugin layer;
   - use an error message when the selected file does not match expected image
     dimensions, unless the user explicitly chooses to replace with a different
     image.
6. Add visual/offscreen tests for dialog sizing:
   - instantiate each dialog with `QT_QPA_PLATFORM=offscreen`;
   - render at scale factors such as 1.0, 1.5, and 2.0 where available;
   - assert size hints are sane and no key widgets have zero size;
   - optionally save screenshots in failed tests for inspection.

## Testability Plan

- Keep tests runnable without launching QGIS.
- Add pure tests for:
  - image format/path helpers;
  - transform/corner coordinate calculations;
  - geotransform-to-plugin-transform conversion;
  - world-file coefficient generation;
  - display scaling rules for GDAL arrays;
  - metadata invariants and QGIS 4 API guardrails.
- Add optional GDAL tests:
  - skip when `osgeo.gdal` is unavailable;
  - create tiny in-memory or temporary rasters for Byte, UInt16, RGB, RGBA,
    nodata, and color-table cases.
- Add optional Qt tests:
  - skip when `qgis.PyQt` is unavailable;
  - validate `QImage` dimensions, format, and backing-buffer lifetime;
  - validate dialog layout behavior offscreen.
- Avoid importing QGIS core modules in pure modules. QGIS-specific adapters can
  remain thin and covered by static or optional integration tests.

## Correctness Improvements

- Preserve the recent fix that avoids overriding `QgsMapLayer.metadata()`;
  plugin-specific text should remain `freehand_metadata()` or equivalent.
- Make plugin layer path persistence easier to reason about:
  - keep the canonical image path in a named custom property;
  - expose the resolved absolute path and stored project-relative path in layer
    properties;
  - document why layer-tree `source=""` is expected for this plugin layer;
  - consider whether the dummy data provider URI can return a useful
    diagnostic source string without breaking QGIS plugin-layer behavior.
- Make raster-display warnings explicit and user-facing:
  - band selection changed;
  - datatype rescaled;
  - nodata/alpha interpreted;
  - georeferencing CRS differs from map CRS.
- Treat georeferencing as data:
  - isolate affine math in pure functions;
  - test default geotransform detection;
  - test rotated/scaled world-file coefficients.
- Fail safely:
  - no partially initialized layer after raster load failure;
  - no fall-through from a cancelled missing-file recovery dialog into raster
    loading;
  - no silent division by zero when data min equals max;
  - clear errors for unsupported or unreadable rasters.

## Phased Implementation

1. Dialog HiDPI cleanup
   - Convert `.ui` files to layouts.
   - Add offscreen dialog tests.
   - Verify issue #58 class of failures manually in QGIS 4 on HiDPI.
   - Include a manual Windows check with 200% scaling or equivalent effective
     scaling, using a project with a missing source image.

2. Pure transform extraction
   - Move coordinate and world-file math into `transform.py`.
   - Add tests before changing raster loading.

3. Missing/relocated image recovery
   - Make missing source images a first-class recoverable state.
   - Stop initialization immediately when the user cancels recovery.
   - Add tests for project reload with missing files, cancellation, and
     replacement with same-size and different-size rasters.

4. GDAL display reader
   - Implement `raster_io.py` and `qt_image.py`.
   - Test with tiny GDAL-created rasters.
   - Replace `QImageReader` and PDF preview paths.

5. Layer simplification
   - Make `FreehandRasterGeoreferencerLayer` delegate raster loading and
     transform calculations.
   - Keep QGIS API code thin.

6. Export follow-up
   - Keep current export behavior initially.
   - Consider GDAL-backed transformed export in a separate change once display
     loading is stable.

## Acceptance Criteria

- No direct `QImageReader` raster-loading path remains.
- GDAL handles PNG, JPEG, TIFF, PDF where the QGIS GDAL build supports them.
- HiDPI dialogs use layouts, not fixed child geometries.
- The missing-file dialog clearly shows the layer name, full missing path, and
  replacement path on Windows HiDPI.
- Replacing one missing raster cannot silently update or reposition another
  layer.
- Opening a project with missing linked images does not crash or block unrelated
  layers from loading.
- Cancelling missing-image recovery leaves a safe invalid/recoverable layer and
  does not attempt to read or render the missing raster.
- Layer properties clearly show stored path, resolved path, and whether the file
  currently exists.
- Core transform and raster conversion tests run without QGIS.
- Optional GDAL/Qt tests skip cleanly when dependencies are unavailable.
- `uv run task lint`, `uv run task format-check`, `uv run task test`, and
  package verification pass.
