# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Parameter Dialog
                                 A QGIS plugin
 Parameter confirmation dialog for GeoGenie
                             -------------------
        begin                : 2025-01-18
        copyright            : (C) 2025 by Ahmad Abubakar Ahmad
        email                : ahmad.abubakar@uni-muenster.de
 ***************************************************************************/
"""

from typing import Dict, Any, Optional
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QTextEdit,
    QGroupBox, QScrollArea, QWidget, QFrame, QSizePolicy, QMessageBox
)
from qgis.PyQt.QtGui import QFont, QPalette
from qgis.core import QgsMessageLog, Qgis


class ParameterConfirmationDialog(QDialog):
    """
    Dialog for confirming and editing algorithm parameters before execution
    """
    
    parameters_confirmed = pyqtSignal(dict)
    execution_cancelled = pyqtSignal()
    
    def __init__(self, algorithm_name: str, algorithm_info: Dict[str, Any],
                 parameters: Dict[str, Any], validation_result: Dict[str, Any],
                 context_summary: str = "", parent=None):
        super().__init__(parent)
        
        self.algorithm_name = algorithm_name
        self.algorithm_info = algorithm_info
        self.parameters = parameters.copy()
        self.validation_result = validation_result
        self.context_summary = context_summary
        self.parameter_widgets = {}
        
        self.setWindowTitle(f"Confirm Parameters - {algorithm_info['name']}")
        self.setModal(True)
        self.resize(600, 500)
        
        self._setup_ui()
        self._populate_parameters()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Algorithm info
        info_group = QGroupBox("Algorithm Information")
        info_layout = QVBoxLayout()
        
        name_label = QLabel(f"<b>{self.algorithm_info['name']}</b>")
        info_layout.addWidget(name_label)
        
        desc_label = QLabel(self.algorithm_info['description'])
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)
        
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)
        
        # Parameters section
        params_group = QGroupBox("Parameters")
        self.params_layout = QFormLayout()
        params_group.setLayout(self.params_layout)
        main_layout.addWidget(params_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.execute_btn = QPushButton("Execute")
        self.cancel_btn = QPushButton("Cancel")
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.execute_btn)
        
        main_layout.addLayout(button_layout)
    
    def _populate_parameters(self):
        """Populate parameter widgets"""
        for param_name in self.algorithm_info['required_params'] + self.algorithm_info['optional_params']:
            if param_name in self.parameters:
                param_value = self.parameters[param_name]
                param_type = self.algorithm_info['param_types'].get(param_name, 'string')
                
                widget = self._create_parameter_widget(param_name, param_type, param_value)
                if widget:
                    self.parameter_widgets[param_name] = {
                        'widget': widget,
                        'type': param_type
                    }
                    
                    label = QLabel(param_name)
                    if param_name in self.algorithm_info['required_params']:
                        label.setText(f"{param_name} *")
                        label.setStyleSheet("font-weight: bold;")
                    
                    self.params_layout.addRow(label, widget)
    
    def _create_parameter_widget(self, param_name: str, param_type: str, param_value: Any):
        """Create appropriate widget for parameter"""
        try:
            if param_type == 'number':
                widget = QDoubleSpinBox()
                widget.setRange(-999999999, 999999999)
                widget.setValue(float(param_value) if param_value is not None else 0.0)
                return widget
            elif param_type == 'int':
                widget = QSpinBox()
                widget.setRange(-999999999, 999999999)
                widget.setValue(int(param_value) if param_value is not None else 0)
                return widget
            elif param_type == 'boolean':
                widget = QCheckBox()
                widget.setChecked(bool(param_value) if param_value is not None else False)
                return widget
            else:
                widget = QLineEdit()
                widget.setText(str(param_value) if param_value is not None else "")
                return widget
        except Exception as e:
            widget = QLineEdit()
            widget.setText(str(param_value) if param_value is not None else "")
            return widget
    
    def _connect_signals(self):
        """Connect signals"""
        self.execute_btn.clicked.connect(self._confirm_execution)
        self.cancel_btn.clicked.connect(self.reject)
    
    def _confirm_execution(self):
        """Confirm execution with current parameters"""
        try:
            final_params = self._extract_parameter_values()
            self.parameters_confirmed.emit(final_params)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error confirming parameters: {str(e)}")
    
    def _extract_parameter_values(self) -> Dict[str, Any]:
        """Extract current values from widgets"""
        current_params = {}
        
        for param_name, widget_info in self.parameter_widgets.items():
            widget = widget_info['widget']
            param_type = widget_info['type']
            
            try:
                if param_type == 'number':
                    current_params[param_name] = widget.value()
                elif param_type == 'int':
                    current_params[param_name] = widget.value()
                elif param_type == 'boolean':
                    current_params[param_name] = widget.isChecked()
                else:
                    text = widget.text().strip()
                    if text:
                        current_params[param_name] = text
            except Exception as e:
                QgsMessageLog.logMessage(f"Error extracting {param_name}: {str(e)}", 'GeoGenie', Qgis.Warning)
        
        return current_params