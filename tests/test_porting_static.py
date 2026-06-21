import configparser
import importlib
from pathlib import Path
import re
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "fhgr"


def plugin_sources():
    return "\n".join(path.read_text() for path in PLUGIN.glob("*.py"))


def test_utils_helpers_without_qgis(monkeypatch):
    qgis = types.ModuleType("qgis")
    pyqt = types.ModuleType("qgis.PyQt")
    qtcore = types.ModuleType("qgis.PyQt.QtCore")
    core = types.ModuleType("qgis.core")
    qtcore.qDebug = lambda _message: None
    core.QgsProject = object

    monkeypatch.setitem(sys.modules, "qgis", qgis)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", pyqt)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "qgis.core", core)
    sys.modules.pop("fhgr.utils", None)

    utils = importlib.import_module("fhgr.utils")

    assert utils.imageFormat("scan.tiff") == "tif"
    assert utils.imageFormat("scan.tifF") == "tif"
    assert utils.imageFormat("scan.PNG") == "png"
    assert utils.tryfloat("1.25") == 1.25
    assert utils.tryfloat("not-a-number") is None


def test_metadata_targets_qgis4_only():
    metadata = configparser.ConfigParser()
    metadata.read(PLUGIN / "metadata.txt")
    general = metadata["general"]

    assert general["version"] == "0.9.0"
    assert general["qgisMinimumVersion"] == "4.0"
    assert general["qgisMaximumVersion"] == "4.99"
    assert general["icon"] == "icons/icon.png"
    assert "supportsQt6" not in general


def test_no_legacy_qgis3_qt5_artifacts_remain():
    source = plugin_sources()

    forbidden_literals = [
        "PyQt5",
        "PyQt6",
        "resources_rc",
        "exec_(",
        "QgsWkbTypes",
        "QgsMapLayer.PluginLayer",
        "Qgis.Info",
        "Qgis.Warning",
        "Qgis.Critical",
    ]
    for literal in forbidden_literals:
        assert literal not in source

    assert not re.search(r"from\s+\.\s*ui_", source)
    assert not re.search(r"import\s+\.\s*ui_", source)


def test_properties_dialog_uses_qt6_tab_stop_api():
    ui = (PLUGIN / "propertiesdialog.ui").read_text()

    assert "tabStopWidth" not in ui
    assert "tabStopDistance" in ui
    assert "setTabStopDistance" not in (PLUGIN / "propertiesdialog.py").read_text()


def test_plugin_package_contains_runtime_assets():
    required = [
        PLUGIN / "__init__.py",
        PLUGIN / "metadata.txt",
        PLUGIN / "freehandrastergeoreferencerdialog.ui",
        PLUGIN / "exportgeorefrasterdialog.ui",
        PLUGIN / "loaderrordialog.ui",
        PLUGIN / "propertiesdialog.ui",
        PLUGIN / "icons" / "icon.png",
    ]

    for path in required:
        assert path.exists(), path
