# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GeoGenie Coordinator
                                 A QGIS plugin
 Main coordination class for GeoGenie Phase 1 functionality
                             -------------------
        begin                : 2025-01-18
        copyright            : (C) 2025 by Ahmad Abubakar Ahmad
        email                : ahmad.abubakar@uni-muenster.de
 ***************************************************************************/
"""

from typing import Dict, Any, Optional
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtWidgets import QMessageBox, QProgressDialog
from qgis.core import QgsMessageLog, QgsProject, Qgis
from qgis.utils import iface

from .context_manager import ContextManager
from .llm_client import LLMClient
from .parameter_validator import ParameterValidator
from .parameter_dialog import ParameterConfirmationDialog
from .processing_executor import ProcessingExecutor, AlgorithmRegistry


class GeoGenieCoordinator(QObject):
    """
    Main coordinator for GeoGenie Phase 1 functionality
    
    Orchestrates the complete workflow:
    1. Context injection
    2. LLM processing 
    3. Parameter validation
    4. User confirmation
    5. Algorithm execution
    """
    
    # Signals
    processing_started = pyqtSignal(str)  # algorithm name
    processing_progress = pyqtSignal(int, str)  # progress, message
    processing_completed = pyqtSignal(dict)  # result
    processing_error = pyqtSignal(str)  # error message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize components
        self.context_manager = ContextManager()
        self.parameter_validator = ParameterValidator(self.context_manager)
        
        # LLM client (will be initialized with API keys)
        self.llm_client = None
        
        # Processing executor
        self.processing_executor = None
        
        # Progress dialog
        self.progress_dialog = None
        
        # Current operation state
        self.current_operation = None
        
        QgsMessageLog.logMessage("GeoGenie Coordinator initialized", 'GeoGenie', Qgis.Info)
    
    def initialize_llm_client(self, openai_api_key: str = None, claude_api_key: str = None, 
                            model: str = "gpt-3.5-turbo"):
        """Initialize LLM client with API keys"""
        try:
            self.llm_client = LLMClient(
                openai_api_key=openai_api_key,
                claude_api_key=claude_api_key,
                model=model
            )
            QgsMessageLog.logMessage(f"LLM client initialized with model: {model}", 'GeoGenie', Qgis.Info)
            return True
        except Exception as e:
            QgsMessageLog.logMessage(f"Error initializing LLM client: {str(e)}", 'GeoGenie', Qgis.Critical)
            return False
    
    def process_natural_language_request(self, prompt: str, parent_widget=None) -> bool:
        """
        Process a natural language request through the complete GeoGenie workflow
        
        Args:
            prompt: Natural language prompt from user
            parent_widget: Parent widget for dialogs
            
        Returns:
            True if processing started successfully, False otherwise
        """
        try:
            # Check if LLM client is initialized
            if not self.llm_client:
                self._show_error("LLM client not initialized. Please check your API key configuration.", parent_widget)
                return False
            
            QgsMessageLog.logMessage(f"Processing request: {prompt}", 'GeoGenie', Qgis.Info)
            
            # Step 1: Build context
            self._show_progress("Building QGIS context...", 0)
            context = self.context_manager.build_context()
            
            if not context['active_layers']:
                self._show_warning("No active layers found in the project. Please load some data first.", parent_widget)
                return False
            
            # Step 2: Extract algorithm request using LLM
            self._show_progress("Processing with AI...", 20)
            llm_result = self.llm_client.extract_algorithm_request(prompt, context)
            
            if not llm_result['success']:
                error_msg = f"Could not understand the request: {llm_result.get('error', 'Unknown error')}"
                if llm_result.get('reasoning'):
                    error_msg += f"\n\nAI Response: {llm_result['reasoning']}"
                self._show_error(error_msg, parent_widget)
                return False
            
            algorithm_name = llm_result['algorithm']
            extracted_params = llm_result['parameters']
            
            QgsMessageLog.logMessage(f"Extracted algorithm: {algorithm_name} with params: {extracted_params}", 
                                   'GeoGenie', Qgis.Info)
            
            # Step 3: Validate parameters
            self._show_progress("Validating parameters...", 40)
            validation_result = self.parameter_validator.validate_algorithm_parameters(
                algorithm_name, extracted_params
            )
            
            # Step 4: Show confirmation dialog
            self._show_progress("Preparing confirmation dialog...", 60)
            algorithm_info = AlgorithmRegistry.get_algorithm_info(algorithm_name)
            context_summary = self.context_manager.get_context_summary()
            
            # Use validated parameters instead of raw extracted parameters
            validated_params = validation_result.get('parameters', extracted_params)
            
            dialog = ParameterConfirmationDialog(
                algorithm_name=algorithm_name,
                algorithm_info=algorithm_info,
                parameters=validated_params,
                validation_result=validation_result,
                context_summary=context_summary,
                parent=parent_widget
            )
            
            # Connect dialog signals
            dialog.parameters_confirmed.connect(
                lambda params: self._execute_algorithm(algorithm_name, params, llm_result.get('reasoning', ''))
            )
            dialog.execution_cancelled.connect(self._hide_progress)
            
            # Hide progress and show dialog
            self._hide_progress()
            dialog.show()
            
            return True
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            QgsMessageLog.logMessage(error_msg, 'GeoGenie', Qgis.Critical)
            self._show_error(error_msg, parent_widget)
            return False
    
    def _execute_algorithm(self, algorithm_name: str, parameters: Dict[str, Any], reasoning: str = ""):
        """Execute the validated algorithm with confirmed parameters"""
        
        try:
            # Get algorithm info
            algorithm_info = AlgorithmRegistry.get_algorithm_info(algorithm_name)
            if not algorithm_info:
                self._show_error(f"Algorithm {algorithm_name} not found in registry")
                return
            
            algorithm_id = algorithm_info['algorithm_id']
            
            QgsMessageLog.logMessage(f"Executing algorithm: {algorithm_id} with parameters: {parameters}", 
                                   'GeoGenie', Qgis.Info)
            
            # Create and setup processing executor
            self.processing_executor = ProcessingExecutor()
            
            # Connect executor signals
            self.processing_executor.progress_updated.connect(self._on_processing_progress)
            self.processing_executor.algorithm_finished.connect(self._on_processing_completed)
            self.processing_executor.error_occurred.connect(self._on_processing_error)
            
            # Start processing
            self.current_operation = {
                'algorithm_name': algorithm_name,
                'algorithm_id': algorithm_id,
                'parameters': parameters,
                'reasoning': reasoning,
                'start_time': None
            }
            
            # Show progress dialog
            self._show_progress(f"Executing {algorithm_info['name']}...", 0, cancellable=True)
            
            # Start algorithm execution
            self.processing_started.emit(algorithm_name)
            self.processing_executor.run_algorithm(algorithm_id, parameters)
            
        except Exception as e:
            error_msg = f"Error starting algorithm execution: {str(e)}"
            QgsMessageLog.logMessage(error_msg, 'GeoGenie', Qgis.Critical)
            self._show_error(error_msg)
    
    def _on_processing_progress(self, progress: int, message: str):
        """Handle processing progress updates"""
        self._show_progress(message, progress)
        self.processing_progress.emit(progress, message)
    
    def _on_processing_completed(self, result: Dict[str, Any]):
        """Handle successful algorithm completion"""
        
        QgsMessageLog.logMessage(f"🎉 Processing completed signal received with result: {result}", 'GeoGenie', Qgis.Info)
        
        try:
            self._hide_progress()
            
            if not result.get('success', True):
                error_msg = result.get('error', 'Unknown processing error')
                self._show_error(f"Processing failed: {error_msg}")
                self.processing_error.emit(error_msg)
                return
            
            QgsMessageLog.logMessage("Adding result layers to map...", 'GeoGenie', Qgis.Info)
            # Add result layers to map
            self._add_result_layers_to_map(result)
            
            # Generate explanation using LLM
            if self.llm_client and self.current_operation:
                try:
                    explanation = self.llm_client.generate_explanation(
                        self.current_operation['algorithm_name'],
                        self.current_operation['parameters'],
                        result
                    )
                    result['explanation'] = explanation
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error generating explanation: {str(e)}", 
                                           'GeoGenie', Qgis.Warning)
                    result['explanation'] = f"Successfully executed {self.current_operation['algorithm_name']} algorithm."
            
            # Show success message
            self._show_success_message(result)
            
            # Emit completion signal
            self.processing_completed.emit(result)
            
            # Clean up
            self.current_operation = None
            
        except Exception as e:
            error_msg = f"Error handling processing completion: {str(e)}"
            QgsMessageLog.logMessage(error_msg, 'GeoGenie', Qgis.Critical)
            self._show_error(error_msg)
    
    def _on_processing_error(self, error_message: str):
        """Handle processing errors"""
        
        self._hide_progress()
        self._show_error(f"Processing error: {error_message}")
        self.processing_error.emit(error_message)
        
        # Clean up
        self.current_operation = None
    
    def _add_result_layers_to_map(self, result: Dict[str, Any]):
        """Add result layers to the map canvas"""
        
        try:
            output_layers = result.get('output_layers', [])
            
            for layer_info in output_layers:
                # Check if we have a layer object directly
                if 'layer_object' in layer_info:
                    # We have the actual layer object from processing
                    layer = layer_info['layer_object']
                    original_name = layer_info.get('layer_name', 'temp_output')
                    
                    # Generate a proper GeoGenie layer name
                    layer_name = self._generate_result_layer_name(layer_info, result)
                    
                    # Set the proper name on the layer
                    layer.setName(layer_name)
                    
                    QgsMessageLog.logMessage(f"Adding layer object directly: {layer_name}", 'GeoGenie', Qgis.Info)
                    
                    if layer.isValid():
                        # Add the existing layer object to the project
                        QgsProject.instance().addMapLayer(layer)
                        QgsMessageLog.logMessage(f"✅ Successfully added result layer: {layer_name} ({layer.featureCount()} features)", 'GeoGenie', Qgis.Info)
                        
                        # Force refresh the map canvas
                        if iface:
                            iface.mapCanvas().refresh()
                            QgsMessageLog.logMessage("Map canvas refreshed", 'GeoGenie', Qgis.Info)
                    else:
                        QgsMessageLog.logMessage(f"❌ Layer object is invalid: {layer_name}", 'GeoGenie', Qgis.Warning)
                        
                else:
                    # Fallback to path-based loading (original method)
                    layer_path = layer_info.get('path')
                    if layer_path:
                        # Generate layer name
                        layer_name = self._generate_result_layer_name(layer_info, result)
                        
                        # Load layer with improved handling
                        QgsMessageLog.logMessage(f"Attempting to load layer from path: {layer_path}", 'GeoGenie', Qgis.Info)
                        
                        if layer_info.get('type') == 'vector':
                            from qgis.core import QgsVectorLayer
                            # Try different providers for memory layers
                            if layer_path.startswith('memory:'):
                                layer = QgsVectorLayer(layer_path, layer_name, 'memory')
                            else:
                                layer = QgsVectorLayer(layer_path, layer_name, 'ogr')
                        else:
                            from qgis.core import QgsRasterLayer
                            layer = QgsRasterLayer(layer_path, layer_name)
                        
                        if layer.isValid():
                            QgsProject.instance().addMapLayer(layer)
                            QgsMessageLog.logMessage(f"✅ Successfully added result layer: {layer_name} (path: {layer_path})", 'GeoGenie', Qgis.Info)
                            
                            # Force refresh the map canvas
                            if iface:
                                iface.mapCanvas().refresh()
                        else:
                            QgsMessageLog.logMessage(f"❌ Failed to load result layer: {layer_path} - Layer invalid", 'GeoGenie', Qgis.Warning)
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error adding result layers: {str(e)}", 'GeoGenie', Qgis.Warning)
    
    def _generate_result_layer_name(self, layer_info: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Generate appropriate name for result layer"""
        
        try:
            from datetime import datetime
            
            algorithm_name = self.current_operation['algorithm_name'] if self.current_operation else 'result'
            timestamp = datetime.now().strftime("%H%M%S")
            
            # Get parameter info for context
            param_context = ""
            if self.current_operation and self.current_operation['parameters']:
                # Add key parameter to name for context
                params = self.current_operation['parameters']
                if 'DISTANCE' in params:
                    param_context = f"_{params['DISTANCE']}"
                elif 'FIELD' in params:
                    param_context = f"_{params['FIELD']}"
            
            layer_name = f"GeoGenie_{algorithm_name}{param_context}_{timestamp}"
            
            return layer_name
            
        except:
            return f"GeoGenie_result_{datetime.now().strftime('%H%M%S')}"
    
    def _show_progress(self, message: str, progress: int, cancellable: bool = False):
        """Show progress dialog"""
        
        if not self.progress_dialog:
            self.progress_dialog = QProgressDialog()
            self.progress_dialog.setWindowTitle("GeoGenie Processing")
            self.progress_dialog.setModal(True)
            
            if cancellable:
                self.progress_dialog.canceled.connect(self._cancel_processing)
            else:
                self.progress_dialog.setCancelButton(None)
        
        self.progress_dialog.setLabelText(message)
        self.progress_dialog.setValue(progress)
        self.progress_dialog.show()
    
    def _hide_progress(self):
        """Hide progress dialog"""
        if self.progress_dialog:
            self.progress_dialog.hide()
            self.progress_dialog = None
    
    def _cancel_processing(self):
        """Cancel current processing operation"""
        if self.processing_executor:
            self.processing_executor.cancel_execution()
        self._hide_progress()
        QgsMessageLog.logMessage("Processing cancelled by user", 'GeoGenie', Qgis.Info)
    
    def _show_error(self, message: str, parent=None):
        """Show error message"""
        QMessageBox.critical(parent or iface.mainWindow() if iface else None, "GeoGenie Error", message)
    
    def _show_warning(self, message: str, parent=None):
        """Show warning message"""
        QMessageBox.warning(parent or iface.mainWindow() if iface else None, "GeoGenie Warning", message)
    
    def _show_success_message(self, result: Dict[str, Any]):
        """Show success message with results"""
        
        try:
            message = "✅ Algorithm executed successfully!\n\n"
            
            # Add explanation if available
            if result.get('explanation'):
                message += f"Result: {result['explanation']}\n\n"
            
            # Add statistics if available
            stats = result.get('statistics', {})
            if stats:
                message += "Statistics:\n"
                for param, stat_info in stats.items():
                    if isinstance(stat_info, dict):
                        feature_count = stat_info.get('feature_count')
                        if feature_count is not None:
                            message += f"• Output features: {feature_count}\n"
                        
                        geom_type = stat_info.get('geometry_type')
                        if geom_type:
                            message += f"• Geometry type: {geom_type}\n"
                
            # Add layer info
            output_layers = result.get('output_layers', [])
            if output_layers:
                message += f"\nAdded {len(output_layers)} new layer(s) to the map."
            
            QMessageBox.information(iface.mainWindow() if iface else None, "GeoGenie Success", message)
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error showing success message: {str(e)}", 'GeoGenie', Qgis.Warning)
            QMessageBox.information(iface.mainWindow() if iface else None, "GeoGenie Success", 
                                  "Algorithm executed successfully!")
    
    def get_available_algorithms(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available algorithms"""
        return AlgorithmRegistry.SAFE_ALGORITHMS
    
    def get_context_summary(self) -> str:
        """Get current QGIS context summary"""
        return self.context_manager.get_context_summary()
    
    def cleanup(self):
        """Clean up resources"""
        if self.processing_executor:
            self.processing_executor.cancel_execution()
            self.processing_executor = None
        
        self._hide_progress()
        self.current_operation = None
        
        QgsMessageLog.logMessage("GeoGenie Coordinator cleaned up", 'GeoGenie', Qgis.Info)