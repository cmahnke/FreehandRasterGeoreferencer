from pathlib import Path

from qgis.PyQt.uic import loadUi


def load_ui(widget, filename):
    loadUi(str(Path(__file__).with_name(filename)), widget)
