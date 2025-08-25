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

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import (
    QgsProcessingFeedback, 
    QgsProcessingContext,
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsMessageLog,
    Qgis,
    QgsTask,
    QgsApplication
)
import processing
from typing import Dict, Any, Optional, List


class ProcessingTaskFeedback(QgsProcessingFeedback):
    """Task-safe feedback handler for processing operations"""
    
    def __init__(self, task: QgsTask):
        super().__init__()
        self.task = task
        
    def setProgress(self, progress):
        super().setProgress(progress)
        if self.task and not self.task.isCanceled():
            self.task.setProgress(progress)
    
    def isCanceled(self) -> bool:
        return self.task.isCanceled() if self.task else super().isCanceled()
    
    def pushInfo(self, info):
        super().pushInfo(info)
        QgsMessageLog.logMessage(info, 'GeoGenie', Qgis.Info)
    
    def pushWarning(self, warning):
        super().pushWarning(warning)
        QgsMessageLog.logMessage(warning, 'GeoGenie', Qgis.Warning)
    
    def pushCommandInfo(self, info):
        super().pushCommandInfo(info)
        QgsMessageLog.logMessage(f"Command: {info}", 'GeoGenie', Qgis.Info)


class ProcessingTask(QgsTask):
    """
    QGIS Task for safe background processing algorithm execution
    
    Uses QGIS Task framework for proper threading and memory management.
    """
    
    def __init__(self, algorithm_id: str, parameters: Dict[str, Any], 
                 context: Optional[QgsProcessingContext] = None, description: str = "Processing"):
        super().__init__(description, QgsTask.CanCancel)
        
        # Copy data for thread safety
        self.algorithm_id = algorithm_id
        self.parameters = parameters.copy()  # Make a copy to avoid thread issues
        self.context = context or QgsProcessingContext()
        self.result = None
        self.error_message = None
        
        # Set up context safely
        self.context.setProject(QgsProject.instance())
        
    def run(self) -> bool:
        """Execute the algorithm in background task"""
        try:
            # Create feedback handler that works with task progress
            feedback = ProcessingTaskFeedback(self)
            
            # Validate algorithm exists
            if not self._validate_algorithm():
                return False
            
            # Update progress
            self.setProgress(10)
            
            # Create spatial indexes for input layers to improve performance
            self._create_spatial_indexes()
            
            # Update progress after spatial indexing
            self.setProgress(20)
            
            # Execute the algorithm
            result = processing.run(
                self.algorithm_id,
                self.parameters,
                context=self.context,
                feedback=feedback
            )
            
            # Check if task was cancelled
            if self.isCanceled():
                return False
            
            # Update progress
            self.setProgress(90)
            
            # Process results safely
            self.result = self._process_results(result)
            
            # Final progress update
            self.setProgress(100)
            
            return True
            
        except Exception as e:
            self.error_message = f"Error executing {self.algorithm_id}: {str(e)}"
            QgsMessageLog.logMessage(self.error_message, 'GeoGenie', Qgis.Critical)
            return False
    
    def finished(self, success: bool):
        """Called when task finishes (runs in main thread)"""
        if success and self.result:
            # Task completed successfully
            pass
        elif self.error_message:
            # Task failed with error
            pass
        # Results will be handled by ProcessingExecutor
    
    def _validate_algorithm(self) -> bool:
        """Validate that the algorithm exists and is available"""
        try:
            registry = QgsApplication.processingRegistry()
            
            if not registry.algorithmById(self.algorithm_id):
                self.error_message = f"Algorithm '{self.algorithm_id}' not found"
                QgsMessageLog.logMessage(self.error_message, 'GeoGenie', Qgis.Critical)
                return False
            
            return True
            
        except Exception as e:
            self.error_message = f"Error validating algorithm: {str(e)}"
            QgsMessageLog.logMessage(self.error_message, 'GeoGenie', Qgis.Critical)
            return False
    
    def _create_spatial_indexes(self):
        """Create spatial indexes for input layers to improve performance"""
        try:
            from qgis.core import QgsProject
            
            # Get all input layer parameters
            input_params = ['INPUT', 'OVERLAY', 'LAYER', 'SOURCE_LAYER', 'TARGET_LAYER']
            
            for param_name in input_params:
                if param_name in self.parameters:
                    layer_id = self.parameters[param_name]
                    
                    # Get the layer from the project
                    layer = QgsProject.instance().mapLayer(layer_id)
                    
                    if layer and hasattr(layer, 'createSpatialIndex'):
                        # Check if layer already has a spatial index
                        if not layer.hasSpatialIndex():
                            QgsMessageLog.logMessage(f"Creating spatial index for layer: {layer.name()}", 'GeoGenie', Qgis.Info)
                            
                            # Create spatial index
                            success = layer.createSpatialIndex()
                            
                            if success:
                                QgsMessageLog.logMessage(f"✅ Spatial index created for: {layer.name()}", 'GeoGenie', Qgis.Info)
                            else:
                                QgsMessageLog.logMessage(f"⚠️ Failed to create spatial index for: {layer.name()}", 'GeoGenie', Qgis.Warning)
                        else:
                            QgsMessageLog.logMessage(f"Spatial index already exists for: {layer.name()}", 'GeoGenie', Qgis.Info)
                            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error creating spatial indexes: {str(e)}", 'GeoGenie', Qgis.Warning)
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """Get the processing result"""
        return self.result
    
    def get_error(self) -> Optional[str]:
        """Get error message if task failed"""
        return self.error_message
    
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
                if isinstance(value, str):
                    # Handle string paths (memory layers or file paths)
                    layer_path = value
                    if not value.startswith('memory:') and not value.startswith('/') and not ':' in value:
                        # It's likely a memory layer ID, add the memory: prefix
                        layer_path = f"memory:{value}"
                    
                    processed_result['output_layers'].append({
                        'parameter': key,
                        'path': layer_path,
                        'type': 'vector'
                    })
                elif hasattr(value, 'source') and hasattr(value, 'name'):
                    # Handle QgsVectorLayer or QgsRasterLayer objects directly
                    layer_source = value.source()
                    layer_name = value.name()
                    
                    QgsMessageLog.logMessage(f"Found layer object: {layer_name}, source: {layer_source}", 'GeoGenie', Qgis.Info)
                    
                    # Store the layer object directly for immediate use
                    processed_result['output_layers'].append({
                        'parameter': key,
                        'path': layer_source,
                        'layer_object': value,  # Store the actual layer object
                        'layer_name': layer_name,
                        'type': 'vector' if 'Vector' in str(type(value)) else 'raster'
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
    

class ProcessingExecutor(QObject):
    """
    Safe processing algorithm executor using QGIS Task framework
    
    Manages background execution of QGIS processing algorithms with proper
    threading, progress feedback, and memory management.
    """
    
    # Signals
    progress_updated = pyqtSignal(int, str)  # progress percentage, status message
    algorithm_finished = pyqtSignal(dict)    # result dictionary
    error_occurred = pyqtSignal(str)         # error message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_task = None
        
    def run_algorithm(self, algorithm_id: str, parameters: Dict[str, Any], 
                     context: Optional[QgsProcessingContext] = None):
        """
        Execute algorithm using QGIS Task framework
        
        Args:
            algorithm_id: QGIS processing algorithm ID (e.g., 'native:buffer')
            parameters: Algorithm parameters dictionary
            context: Processing context (optional)
        """
        try:
            # Cancel any existing task
            if self.current_task:
                self.cancel_execution()
            
            # Create description
            algorithm_info = AlgorithmRegistry.get_algorithm_by_id(algorithm_id)
            description = algorithm_info['name'] if algorithm_info else algorithm_id
            
            # Create task
            self.current_task = ProcessingTask(
                algorithm_id=algorithm_id,
                parameters=parameters,
                context=context,
                description=f"GeoGenie: {description}"
            )
            
            # Connect task signals
            self.current_task.progressChanged.connect(self._on_progress_changed)
            self.current_task.taskCompleted.connect(self._on_task_completed)
            self.current_task.taskTerminated.connect(self._on_task_terminated)
            
            # Submit task to task manager
            QgsApplication.taskManager().addTask(self.current_task)
            
            # Emit initial progress
            self.progress_updated.emit(0, f"Starting {description}...")
            
        except Exception as e:
            error_msg = f"Error starting algorithm: {str(e)}"
            QgsMessageLog.logMessage(error_msg, 'GeoGenie', Qgis.Critical)
            self.error_occurred.emit(error_msg)
    
    def _on_progress_changed(self):
        """Handle task progress updates"""
        if self.current_task:
            progress = self.current_task.progress()
            message = f"Processing... {progress:.1f}%"
            self.progress_updated.emit(int(progress), message)
    
    def _on_task_completed(self):
        """Handle task completion"""
        QgsMessageLog.logMessage("Task completed signal received", 'GeoGenie', Qgis.Info)
        
        if self.current_task:
            result = self.current_task.get_result()
            error = self.current_task.get_error()
            
            QgsMessageLog.logMessage(f"Task result: {result}", 'GeoGenie', Qgis.Info)
            QgsMessageLog.logMessage(f"Task error: {error}", 'GeoGenie', Qgis.Info)
            
            if result:
                QgsMessageLog.logMessage("Emitting algorithm_finished signal", 'GeoGenie', Qgis.Info)
                self.algorithm_finished.emit(result)
            else:
                QgsMessageLog.logMessage("Emitting error_occurred signal", 'GeoGenie', Qgis.Info)
                self.error_occurred.emit(error or "Unknown processing error")
            
            self.current_task = None
        else:
            QgsMessageLog.logMessage("No current task found in completion handler", 'GeoGenie', Qgis.Warning)
    
    def _on_task_terminated(self):
        """Handle task termination/cancellation"""
        self.error_occurred.emit("Processing was cancelled or terminated")
        self.current_task = None
    
    def cancel_execution(self):
        """Cancel the running task"""
        if self.current_task:
            self.current_task.cancel()
            self.current_task = None


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