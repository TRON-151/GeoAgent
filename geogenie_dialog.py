# -*- coding: utf-8 -*-
"""
geogenie_dialog.py

Main user interface for GeoGenie plugin.

This file creates the dock widget that users see in QGIS. It handles the chat interface,
settings tabs, and user interactions. Users can type natural language questions here
and see AI responses and processing results.

What this dialog provides:
- Chat tab for natural language questions
- Settings tab for API key configuration  
- Progress feedback during processing
- Results display and error messages
- Integration with different AI providers

Author: Ahmad Abubakar Ahmad
Email: aabubaka@uni-muenster.de
Date: 2025-08-31
"""

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'geogenie_dialog_base.ui'))


class GeoGenieDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(GeoGenieDockWidget, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
