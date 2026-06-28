
Fix the issue with hi dpi. Make sure the low dpi case still works fine (no matter the dpi it works)

If possible use standard Qt 6 capabilities to fix that.

You can use gh to get the details on the issue in the repo.

Add or create local file PR_response.json : an entry <issue id> : formatted response for Github (later to be sent using gh). !!! Do not respond to or edit the issue for now !!!. + add precsion : This issue will be available in next plugin version for QGIS 4.

- Dialog scaling:
  [#58](https://github.com/gvellut/FreehandRasterGeoreferencer/issues/58)
  reports unreadable dialogs on Windows HiDPI scaling. This is both a usability
  issue and a correctness issue because the hidden missing-file name can cause
  users to replace the wrong raster.


- Dialogs still include fixed widget geometries in `.ui` files. That is fragile
  for HiDPI scaling and directly matches issue #58:
  https://github.com/gvellut/FreehandRasterGeoreferencer/issues/58.



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
6. Add visual/offscreen tests for dialog sizing:
   - instantiate each dialog with `QT_QPA_PLATFORM=offscreen`;
   - render at scale factors such as 1.0, 1.5, and 2.0 where available;
   - assert size hints are sane and no key widgets have zero size;
   - optionally save screenshots in failed tests for inspection.


## Result

- HiDPI dialogs use layouts, not fixed child geometries.
- The missing-file dialog clearly shows the layer name, full missing path, and
  replacement path on Windows HiDPI.