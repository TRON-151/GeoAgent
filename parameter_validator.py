# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Parameter Validator
                                 A QGIS plugin
 Parameter validation system for GeoGenie
                             -------------------
        begin                : 2025-01-18
        copyright            : (C) 2025 by Ahmad Abubakar Ahmad
        email                : ahmad.abubakar@uni-muenster.de
 ***************************************************************************/
"""

import re
from typing import Dict, Any, List, Optional, Union, Tuple
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsMessageLog,
    QgsVectorLayer,
    QgsRasterLayer,
    Qgis
)


class ParameterValidator:
    """
    Validates and processes parameters for QGIS processing algorithms
    
    Handles type checking, format validation, and parameter transformation
    for safe algorithm execution.
    """
    
    def __init__(self, context_manager=None):
        """
        Initialize parameter validator
        
        Args:
            context_manager: ContextManager instance for layer validation
        """
        self.context_manager = context_manager
    
    def validate_algorithm_parameters(self, algorithm_name: str, 
                                    parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters for a specific algorithm
        
        Args:
            algorithm_name: Name of the algorithm
            parameters: Dictionary of parameters to validate
            
        Returns:
            Validation result with validated parameters and errors
        """
        from .processing_executor import AlgorithmRegistry
        
        try:
            # Get algorithm info
            alg_info = AlgorithmRegistry.get_algorithm_info(algorithm_name)
            if not alg_info:
                return {
                    'valid': False,
                    'errors': [f"Unknown algorithm: {algorithm_name}"],
                    'parameters': parameters,
                    'warnings': []
                }
            
            # Initialize result
            result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'parameters': {},
                'missing_required': [],
                'algorithm_info': alg_info
            }
            
            # Check required parameters
            for req_param in alg_info['required_params']:
                if req_param not in parameters or parameters[req_param] is None:
                    result['missing_required'].append(req_param)
                    result['valid'] = False
                    result['errors'].append(f"Missing required parameter: {req_param}")
            
            # Validate each parameter
            for param_name, param_value in parameters.items():
                if param_value is None:
                    continue
                
                # Get expected parameter type
                param_type = alg_info['param_types'].get(param_name, 'string')
                
                # Validate parameter
                validation_result = self._validate_parameter(
                    param_name, param_value, param_type, alg_info
                )
                
                if validation_result['valid']:
                    result['parameters'][param_name] = validation_result['value']
                    if validation_result.get('warning'):
                        result['warnings'].append(validation_result['warning'])
                else:
                    result['valid'] = False
                    result['errors'].append(validation_result['error'])
            
            # Add default values for missing optional parameters
            self._add_default_parameters(result, alg_info)
            
            # Add OUTPUT parameter if missing (required for most algorithms)
            self._add_output_parameter(result, algorithm_name)
            
            # Validate parameter combinations
            combination_errors = self._validate_parameter_combinations(
                algorithm_name, result['parameters']
            )
            if combination_errors:
                result['errors'].extend(combination_errors)
                result['valid'] = False
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error validating parameters: {str(e)}", 
                                   'GeoGenie', Qgis.Critical)
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'parameters': parameters,
                'warnings': []
            }
        
        return result
    
    def _validate_parameter(self, param_name: str, param_value: Any, 
                          param_type: str, alg_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single parameter"""
        
        try:
            if param_type == 'layer':
                return self._validate_layer_parameter(param_name, param_value)
            elif param_type == 'number':
                return self._validate_number_parameter(param_name, param_value)
            elif param_type == 'int':
                return self._validate_int_parameter(param_name, param_value)
            elif param_type == 'boolean':
                return self._validate_boolean_parameter(param_name, param_value)
            elif param_type == 'crs':
                return self._validate_crs_parameter(param_name, param_value)
            elif param_type == 'enum':
                return self._validate_enum_parameter(param_name, param_value, alg_info)
            elif param_type == 'field':
                return self._validate_field_parameter(param_name, param_value)
            elif param_type == 'field_list':
                return self._validate_field_list_parameter(param_name, param_value)
            else:
                return self._validate_string_parameter(param_name, param_value)
                
        except Exception as e:
            return {
                'valid': False,
                'error': f"Error validating {param_name}: {str(e)}",
                'value': param_value
            }
    
    def _validate_layer_parameter(self, param_name: str, param_value: Any) -> Dict[str, Any]:
        """Validate layer parameter"""
        
        if not isinstance(param_value, str):
            return {
                'valid': False,
                'error': f"{param_name}: Layer name must be a string",
                'value': param_value
            }
        
        # If we have a context manager, validate the layer exists
        if self.context_manager:
            validation = self.context_manager.validate_layer_for_algorithm(param_value)
            
            if not validation['valid']:
                return {
                    'valid': False,
                    'error': f"{param_name}: {validation['error']}",
                    'value': param_value
                }
            
            # Return the layer ID for processing
            layer = validation['layer']
            return {
                'valid': True,
                'value': layer.id(),  # Use layer ID for processing
                'warning': None
            }
        else:
            # Without context manager, just pass through the name
            return {
                'valid': True,
                'value': param_value,
                'warning': f"Could not verify layer '{param_value}' exists"
            }
    
    def _validate_number_parameter(self, param_name: str, param_value: Any) -> Dict[str, Any]:
        """Validate numeric parameter"""
        
        try:
            if isinstance(param_value, (int, float)):
                value = float(param_value)
            elif isinstance(param_value, str):
                value = float(param_value)
            else:
                return {
                    'valid': False,
                    'error': f"{param_name}: Must be a number",
                    'value': param_value
                }
            
            # Check for reasonable bounds (algorithm-specific validation could be added)
            if param_name.lower() == 'distance':
                if value < 0:
                    return {
                        'valid': False,
                        'error': f"{param_name}: Distance cannot be negative",
                        'value': param_value
                    }
                if value > 1000000:  # 1 million map units
                    return {
                        'valid': True,
                        'value': value,
                        'warning': f"{param_name}: Very large distance value ({value})"
                    }
            
            return {
                'valid': True,
                'value': value,
                'warning': None
            }
            
        except ValueError:
            return {
                'valid': False,
                'error': f"{param_name}: Invalid number format",
                'value': param_value
            }
    
    def _validate_int_parameter(self, param_name: str, param_value: Any) -> Dict[str, Any]:
        """Validate integer parameter"""
        
        try:
            if isinstance(param_value, int):
                value = param_value
            elif isinstance(param_value, float):
                if param_value.is_integer():
                    value = int(param_value)
                else:
                    return {
                        'valid': False,
                        'error': f"{param_name}: Must be a whole number",
                        'value': param_value
                    }
            elif isinstance(param_value, str):
                value = int(float(param_value))  # Allow "5.0" -> 5
            else:
                return {
                    'valid': False,
                    'error': f"{param_name}: Must be an integer",
                    'value': param_value
                }
            
            # Check bounds for specific parameters
            if param_name.lower() == 'segments':
                if value < 1:
                    return {
                        'valid': False,
                        'error': f"{param_name}: Segments must be at least 1",
                        'value': param_value
                    }
                if value > 100:
                    return {
                        'valid': True,
                        'value': value,
                        'warning': f"{param_name}: Very high segment count ({value})"
                    }
            
            return {
                'valid': True,
                'value': value,
                'warning': None
            }
            
        except (ValueError, OverflowError):
            return {
                'valid': False,
                'error': f"{param_name}: Invalid integer format",
                'value': param_value
            }
    
    def _validate_boolean_parameter(self, param_name: str, param_value: Any) -> Dict[str, Any]:
        """Validate boolean parameter"""
        
        if isinstance(param_value, bool):
            return {
                'valid': True,
                'value': param_value,
                'warning': None
            }
        elif isinstance(param_value, str):
            value_lower = param_value.lower().strip()
            if value_lower in ['true', 'yes', '1', 'on']:
                return {
                    'valid': True,
                    'value': True,
                    'warning': None
                }
            elif value_lower in ['false', 'no', '0', 'off']:
                return {
                    'valid': True,
                    'value': False,
                    'warning': None
                }
            else:
                return {
                    'valid': False,
                    'error': f"{param_name}: Invalid boolean value '{param_value}'",
                    'value': param_value
                }
        elif isinstance(param_value, (int, float)):
            return {
                'valid': True,
                'value': bool(param_value),
                'warning': None
            }
        else:
            return {
                'valid': False,
                'error': f"{param_name}: Must be a boolean value",
                'value': param_value
            }
    
    def _validate_crs_parameter(self, param_name: str, param_value: Any) -> Dict[str, Any]:
        """Validate CRS parameter"""
        
        if not isinstance(param_value, str):
            return {
                'valid': False,
                'error': f"{param_name}: CRS must be a string",
                'value': param_value
            }
        
        try:
            # Try to create CRS from the string
            crs = QgsCoordinateReferenceSystem(param_value)
            
            if not crs.isValid():
                return {
                    'valid': False,
                    'error': f"{param_name}: Invalid CRS '{param_value}'",
                    'value': param_value
                }
            
            return {
                'valid': True,
                'value': crs.authid() or param_value,
                'warning': None
            }
            
        except Exception:
            return {
                'valid': False,
                'error': f"{param_name}: Could not parse CRS '{param_value}'",
                'value': param_value
            }
    
    def _validate_enum_parameter(self, param_name: str, param_value: Any, 
                                alg_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate enumeration parameter"""
        
        # For now, just validate as integer (most QGIS enums are integers)
        try:
            if isinstance(param_value, int):
                value = param_value
            elif isinstance(param_value, str):
                value = int(param_value)
            else:
                return {
                    'valid': False,
                    'error': f"{param_name}: Enum value must be an integer",
                    'value': param_value
                }
            
            # Basic range check
            if value < 0 or value > 10:  # Reasonable enum range
                return {
                    'valid': True,
                    'value': value,
                    'warning': f"{param_name}: Unusual enum value ({value})"
                }
            
            return {
                'valid': True,
                'value': value,
                'warning': None
            }
            
        except ValueError:
            return {
                'valid': False,
                'error': f"{param_name}: Invalid enum format",
                'value': param_value
            }
    
    def _validate_field_parameter(self, param_name: str, param_value: Any) -> Dict[str, Any]:
        """Validate field name parameter"""
        
        if not isinstance(param_value, str):
            return {
                'valid': False,
                'error': f"{param_name}: Field name must be a string",
                'value': param_value
            }
        
        # Basic field name validation
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', param_value):
            return {
                'valid': True,  # Allow non-standard field names, but warn
                'value': param_value,
                'warning': f"{param_name}: Field name '{param_value}' may not be valid"
            }
        
        return {
            'valid': True,
            'value': param_value,
            'warning': None
        }
    
    def _validate_field_list_parameter(self, param_name: str, param_value: Any) -> Dict[str, Any]:
        """Validate field list parameter"""
        
        if isinstance(param_value, str):
            # Convert comma-separated string to list
            fields = [f.strip() for f in param_value.split(',') if f.strip()]
        elif isinstance(param_value, list):
            fields = [str(f) for f in param_value]
        else:
            return {
                'valid': False,
                'error': f"{param_name}: Field list must be a string or list",
                'value': param_value
            }
        
        # Validate each field name
        warnings = []
        for field in fields:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', field):
                warnings.append(f"Field name '{field}' may not be valid")
        
        return {
            'valid': True,
            'value': fields,
            'warning': '; '.join(warnings) if warnings else None
        }
    
    def _validate_string_parameter(self, param_name: str, param_value: Any) -> Dict[str, Any]:
        """Validate string parameter"""
        
        return {
            'valid': True,
            'value': str(param_value),
            'warning': None
        }
    
    def _add_default_parameters(self, result: Dict[str, Any], alg_info: Dict[str, Any]):
        """Add default values for missing optional parameters"""
        
        for param_name in alg_info['optional_params']:
            if param_name not in result['parameters']:
                default_value = alg_info['param_defaults'].get(param_name)
                if default_value is not None:
                    result['parameters'][param_name] = default_value
                    result['warnings'].append(
                        f"Using default value for {param_name}: {default_value}"
                    )
    
    def _add_output_parameter(self, result: Dict[str, Any], algorithm_name: str):
        """Add OUTPUT parameter if missing (most algorithms need this)"""
        
        if 'OUTPUT' not in result['parameters']:
            # Create a temporary output path using memory provider
            result['parameters']['OUTPUT'] = 'memory:temp_output'
            result['warnings'].append("Added temporary output location: memory:temp_output")
    
    def _validate_parameter_combinations(self, algorithm_name: str, 
                                       parameters: Dict[str, Any]) -> List[str]:
        """Validate parameter combinations for specific algorithms"""
        
        errors = []
        
        try:
            if algorithm_name == 'buffer':
                # Buffer-specific validation
                if 'DISTANCE' in parameters:
                    distance = parameters['DISTANCE']
                    if distance == 0:
                        errors.append("Buffer distance cannot be zero")
            
            elif algorithm_name == 'clip':
                # Clip-specific validation
                if 'INPUT' in parameters and 'OVERLAY' in parameters:
                    if parameters['INPUT'] == parameters['OVERLAY']:
                        errors.append("Input and overlay layers cannot be the same")
            
            elif algorithm_name == 'intersection':
                # Intersection-specific validation
                if 'INPUT' in parameters and 'OVERLAY' in parameters:
                    if parameters['INPUT'] == parameters['OVERLAY']:
                        errors.append("Input and overlay layers cannot be the same")
            
            # Add more algorithm-specific validations as needed
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in parameter combination validation: {str(e)}", 
                                   'GeoGenie', Qgis.Warning)
        
        return errors
    
    def get_parameter_suggestions(self, algorithm_name: str, 
                                partial_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get suggestions for missing or invalid parameters
        
        Args:
            algorithm_name: Name of the algorithm
            partial_params: Partially filled parameters
            
        Returns:
            Dictionary with suggestions and recommendations
        """
        from .processing_executor import AlgorithmRegistry
        
        suggestions = {
            'missing_required': [],
            'recommended_values': {},
            'layer_suggestions': {},
            'warnings': []
        }
        
        try:
            alg_info = AlgorithmRegistry.get_algorithm_info(algorithm_name)
            if not alg_info:
                return suggestions
            
            # Find missing required parameters
            for req_param in alg_info['required_params']:
                if req_param not in partial_params:
                    suggestions['missing_required'].append({
                        'parameter': req_param,
                        'type': alg_info['param_types'].get(req_param, 'string'),
                        'description': f"Required parameter for {algorithm_name}"
                    })
            
            # Suggest default values
            for param, default in alg_info['param_defaults'].items():
                if param not in partial_params:
                    suggestions['recommended_values'][param] = default
            
            # Suggest layers if context manager available
            if self.context_manager:
                context = self.context_manager.build_context()
                active_layers = context['active_layers']
                
                for req_param in alg_info['required_params']:
                    param_type = alg_info['param_types'].get(req_param, 'string')
                    
                    if param_type == 'layer' and req_param not in partial_params:
                        # Suggest appropriate layers
                        suitable_layers = []
                        for layer in active_layers:
                            if layer['is_visible'] and layer['type'] in ['Point Vector', 'Line Vector', 'Polygon Vector']:
                                suitable_layers.append(layer['name'])
                        
                        if suitable_layers:
                            suggestions['layer_suggestions'][req_param] = suitable_layers[:3]  # Top 3 suggestions
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error generating parameter suggestions: {str(e)}", 
                                   'GeoGenie', Qgis.Warning)
        
        return suggestions