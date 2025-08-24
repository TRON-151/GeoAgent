import os
import sys
import importlib
from qgis.PyQt.QtWidgets import QMessageBox


def check(required_packages):
    """
    Check if required packages are installed for GeoGenie plugin.
    Only checks for essential packages: openai and anthropic
    """
    missing_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        message = "The following Python packages are required to use GeoGenie:\n\n"
        message += "\n".join(missing_packages)
        message += "\n\nWould you like to install them now? After installation please restart QGIS."

        reply = QMessageBox.question(None, 'Missing Dependencies - GeoGenie', message,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            return

        for package in missing_packages:
            try:
                import subprocess
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            except Exception as e:
                QMessageBox.warning(None, 'Installation Error', 
                                   f'Failed to install {package}: {str(e)}')
                return
