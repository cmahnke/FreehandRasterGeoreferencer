
## Problems to fix at the same time

- Export quality and transparency:
  [#59](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/59)
  reports export quality loss and 16-bit data being reduced to 8-bit.
  [#57](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/57) and
  [#55](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/55)
  report black or opaque borders around rotated/exported images. Export should
  preserve alpha/nodata semantics and expose quality/compression choices.

## Issues Already Fixed or Partially Covered: To verify more

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
