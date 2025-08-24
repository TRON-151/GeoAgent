# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Processing Executor
                                 A QGIS plugin
 Algorithm execution engine for GeoGenie
                             -------------------
        begin                : 2025-01-18
        copyright            : (C) 2025 by Ahmad Abubakar Ahmad
        email                : ahmad.abubakar@uni-muenster.de
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal, QObject
from qgis.core import (
    QgsProcessingFeedback, 
    QgsProcessingContext,
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsMessageLog,
    Qgis
)
import processing
from typing import Dict, Any, Optional, List


class ProcessingFeedbackHandler(QgsProcessingFeedback):
    """Custom feedback handler for processing operations"""
    
    def __init__(self, progress_callback=None):
        super().__init__()
        self.progress_callback = progress_callback
        
    def setProgress(self, progress):
        super().setProgress(progress)
        if self.progress_callback:
            self.progress_callback(progress)
    
    def pushInfo(self, info):
        super().pushInfo(info)
        QgsMessageLog.logMessage(info, 'GeoGenie', Qgis.Info)
    
    def pushWarning(self, warning):
        super().pushWarning(warning)
        QgsMessageLog.logMessage(warning, 'GeoGenie', Qgis.Warning)
    
    def pushCommandInfo(self, info):
        super().pushCommandInfo(info)
        QgsMessageLog.logMessage(f"Command: {info}", 'GeoGenie', Qgis.Info)


class ProcessingExecutor(QThread):
    """
    Asynchronous QGIS processing algorithm executor
    
    Handles execution of QGIS processing algorithms in background thread
    with progress feedback and result handling.
    """
    
    # Signals
    progress_updated = pyqtSignal(int, str)  # progress percentage, status message
    algorithm_finished = pyqtSignal(dict)    # result dictionary
    error_occurred = pyqtSignal(str)         # error message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.algorithm_id = None
        self.parameters = None
        self.context = None
        self.feedback = None
        
    def run_algorithm(self, algorithm_id: str, parameters: Dict[str, Any], 
                     context: Optional[QgsProcessingContext] = None):
        """
        Set up algorithm execution parameters
        
        Args:
            algorithm_id: QGIS processing algorithm ID (e.g., 'native:buffer')
            parameters: Algorithm parameters dictionary
            context: Processing context (optional)
        """
        self.algorithm_id = algorithm_id
        self.parameters = parameters
        self.context = context or QgsProcessingContext()
        
        # Set up project context
        self.context.setProject(QgsProject.instance())
        
        # Start the thread
        self.start()
    
    def run(self):
        """Execute the algorithm in background thread"""
        try:
            # Create feedback handler
            self.feedback = ProcessingFeedbackHandler(
                progress_callback=self._on_progress_changed
            )
            
            # Emit initial progress
            self.progress_updated.emit(0, f"Starting {self.algorithm_id}...")
            
            # Validate algorithm exists
            if not self._validate_algorithm():
                return
            
            # Execute the algorithm
            self.progress_updated.emit(10, "Executing algorithm...")
            
            result = processing.run(
                self.algorithm_id,
                self.parameters,
                context=self.context,
                feedback=self.feedback
            )
            
            # Check if operation was cancelled
            if self.feedback.isCanceled():
                self.error_occurred.emit("Operation was cancelled")
                return
            
            # Process results
            self.progress_updated.emit(90, "Processing results...")
            processed_result = self._process_results(result)
            
            # Emit completion
            self.progress_updated.emit(100, "Algorithm completed successfully")
            self.algorithm_finished.emit(processed_result)
            
        except Exception as e:
            error_msg = f"Error executing {self.algorithm_id}: {str(e)}"
            QgsMessageLog.logMessage(error_msg, 'GeoGenie', Qgis.Critical)
            self.error_occurred.emit(error_msg)
    
    def _validate_algorithm(self) -> bool:
        """Validate that the algorithm exists and is available"""
        try:
            from qgis.core import QgsApplication
            registry = QgsApplication.processingRegistry()
            
            if not registry.algorithmById(self.algorithm_id):
                error_msg = f"Algorithm '{self.algorithm_id}' not found"
                self.error_occurred.emit(error_msg)
                return False
            
            return True
            
        except Exception as e:
            error_msg = f"Error validating algorithm: {str(e)}"
            self.error_occurred.emit(error_msg)
            return False
    
    def _on_progress_changed(self, progress: float):
        """Handle progress updates from feedback"""
        self.progress_updated.emit(int(progress), f"Processing... {progress:.1f}%")
    
    def _process_results(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and enhance algorithm results
        
        Args:
            result: Raw algorithm result dictionary
            
        Returns:
            Enhanced result dictionary with additional metadata
        """
        processed_result = {
            'success': True,
            'algorithm_id': self.algorithm_id,
            'parameters': self.parameters,
            'raw_result': result,
            'output_layers': [],
            'statistics': {}
        }
        
        # Extract output layers
        for key, value in result.items():
            if key.startswith('OUTPUT') or key == 'OUTPUT':
                if isinstance(value, str) and (value.startswith('memory:') or 
                                              value.endswith(('.shp', '.gpkg', '.geojson'))):
                    processed_result['output_layers'].append({
                        'parameter': key,
                        'path': value,
                        'type': 'vector'
                    })
        
        # Add layer statistics if available
        if processed_result['output_layers']:
            try:
                self._add_layer_statistics(processed_result)
            except Exception as e:
                QgsMessageLog.logMessage(f"Error calculating statistics: {str(e)}", 
                                       'GeoGenie', Qgis.Warning)
        
        return processed_result
    
    def _add_layer_statistics(self, result: Dict[str, Any]):
        """Add basic statistics for output layers"""
        for layer_info in result['output_layers']:
            try:
                if layer_info['type'] == 'vector':
                    # Try to load the layer to get statistics
                    layer = QgsVectorLayer(layer_info['path'], 'temp', 'ogr')
                    if layer.isValid():
                        result['statistics'][layer_info['parameter']] = {
                            'feature_count': layer.featureCount(),
                            'geometry_type': layer.geometryType().name if layer.geometryType() else 'Unknown',
                            'crs': layer.crs().authid(),
                            'extent': layer.extent().toString()
                        }
            except Exception as e:
                QgsMessageLog.logMessage(f"Error getting layer statistics: {str(e)}", 
                                       'GeoGenie', Qgis.Warning)
    
    def cancel_execution(self):
        """Cancel the running algorithm"""
        if self.feedback:
            self.feedback.cancel()
        
        if self.isRunning():
            self.terminate()
            self.wait(3000)  # Wait up to 3 seconds for clean termination


class AlgorithmRegistry:
    """Registry of safe QGIS processing algorithms with parameter schemas"""
    
    SAFE_ALGORITHMS = {
        "buffer": {
            "algorithm_id": "native:buffer",
            "name": "Buffer",
            "description": "Create buffer zones around geometries",
            "required_params": ["INPUT", "DISTANCE"],
            "optional_params": ["SEGMENTS", "END_CAP_STYLE", "JOIN_STYLE", "MITER_LIMIT", "DISSOLVE", "OUTPUT"],
            "param_types": {
                "INPUT": "layer",
                "DISTANCE": "number",
                "SEGMENTS": "int",
                "END_CAP_STYLE": "enum",
                "JOIN_STYLE": "enum", 
                "MITER_LIMIT": "number",
                "DISSOLVE": "boolean",
                "OUTPUT": "output"
            },
            "param_defaults": {
                "SEGMENTS": 5,
                "END_CAP_STYLE": 0,  # Round
                "JOIN_STYLE": 0,     # Round
                "MITER_LIMIT": 2.0,
                "DISSOLVE": False,
                "OUTPUT": "memory:temp_output"
            }
        },
        
        "clip": {
            "algorithm_id": "native:clip",
            "name": "Clip",
            "description": "Clip vector layer by overlay layer",
            "required_params": ["INPUT", "OVERLAY"],
            "optional_params": ["OUTPUT"],
            "param_types": {
                "INPUT": "layer",
                "OVERLAY": "layer",
                "OUTPUT": "output"
            },
            "param_defaults": {
                "OUTPUT": "memory:temp_output"
            }
        },
        
        "reproject": {
            "algorithm_id": "native:reprojectlayer", 
            "name": "Reproject Layer",
            "description": "Reproject layer to different CRS",
            "required_params": ["INPUT", "TARGET_CRS"],
            "optional_params": ["OPERATION", "OUTPUT"],
            "param_types": {
                "INPUT": "layer",
                "TARGET_CRS": "crs",
                "OPERATION": "string",
                "OUTPUT": "output"
            },
            "param_defaults": {
                "OUTPUT": "memory:temp_output"
            }
        },
        
        "dissolve": {
            "algorithm_id": "native:dissolve",
            "name": "Dissolve",
            "description": "Dissolve geometries based on attributes",
            "required_params": ["INPUT"],
            "optional_params": ["FIELD", "OUTPUT"],
            "param_types": {
                "INPUT": "layer",
                "FIELD": "field",
                "OUTPUT": "output"
            },
            "param_defaults": {
                "OUTPUT": "memory:temp_output"
            }
        },
        
        "intersection": {
            "algorithm_id": "native:intersection",
            "name": "Intersection", 
            "description": "Calculate intersection between two layers",
            "required_params": ["INPUT", "OVERLAY"],
            "optional_params": ["INPUT_FIELDS", "OVERLAY_FIELDS", "OUTPUT"],
            "param_types": {
                "INPUT": "layer",
                "OVERLAY": "layer", 
                "INPUT_FIELDS": "field_list",
                "OVERLAY_FIELDS": "field_list",
                "OUTPUT": "output"
            },
            "param_defaults": {
                "OUTPUT": "memory:temp_output"
            }
        }
    }
    
    @classmethod
    def get_algorithm_info(cls, algorithm_name: str) -> Optional[Dict[str, Any]]:
        """Get algorithm information by name"""
        return cls.SAFE_ALGORITHMS.get(algorithm_name.lower())
    
    @classmethod
    def get_available_algorithms(cls) -> List[str]:
        """Get list of available algorithm names"""
        return list(cls.SAFE_ALGORITHMS.keys())
    
    @classmethod
    def is_algorithm_safe(cls, algorithm_id: str) -> bool:
        """Check if algorithm ID is in the safe list"""
        for alg_info in cls.SAFE_ALGORITHMS.values():
            if alg_info["algorithm_id"] == algorithm_id:
                return True
        return False
    
    @classmethod
    def get_algorithm_by_id(cls, algorithm_id: str) -> Optional[Dict[str, Any]]:
        """Get algorithm info by algorithm ID"""
        for alg_info in cls.SAFE_ALGORITHMS.values():
            if alg_info["algorithm_id"] == algorithm_id:
                return alg_info
        return None