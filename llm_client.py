# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LLM Client
                                 A QGIS plugin
 LLM integration layer for GeoGenie
                             -------------------
        begin                : 2025-01-18
        copyright            : (C) 2025 by Ahmad Abubakar Ahmad
        email                : ahmad.abubakar@uni-muenster.de
 ***************************************************************************/
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from qgis.core import QgsMessageLog, Qgis

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class LLMProvider:
    """Provider constants"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic" 
    GEMINI = "gemini"
    OLLAMA = "ollama"


class LLMClient:
    """
    Unified LLM client for multiple providers: OpenAI, Anthropic, Gemini, Ollama
    
    Handles function calling for QGIS processing algorithm extraction
    from natural language prompts across different AI providers.
    """
    
    def __init__(self, provider: str = LLMProvider.OPENAI, model: str = None, **api_keys):
        """
        Initialize LLM client with provider support
        
        Args:
            provider: AI provider (openai, anthropic, gemini, ollama)
            model: Model name to use  
            **api_keys: API keys and configuration
        """
        self.provider = provider.lower()
        self.model = model
        self.api_keys = api_keys
        
        # Provider clients
        self.openai_client = None
        self.claude_client = None
        self.gemini_client = None
        self.ollama_url = api_keys.get('ollama_url', 'http://localhost:11434')
        
        # Initialize the selected provider
        self._initialize_provider()
        
        # Token counter
        self.token_counter = None
        if TIKTOKEN_AVAILABLE:
            try:
                self.token_counter = tiktoken.encoding_for_model(
                    model if self.is_openai_model(model) else "gpt-3.5-turbo"
                )
            except:
                self.token_counter = tiktoken.get_encoding("cl100k_base")
    
    def _initialize_provider(self):
        """Initialize the selected provider client"""
        try:
            if self.provider == LLMProvider.OPENAI:
                self._init_openai()
            elif self.provider == LLMProvider.ANTHROPIC:
                self._init_anthropic()
            elif self.provider == LLMProvider.GEMINI:
                self._init_gemini()
            elif self.provider == LLMProvider.OLLAMA:
                self._init_ollama()
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Failed to initialize {self.provider} provider: {str(e)}", 'GeoGenie', Qgis.Critical)
            raise
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not available. Install with: pip install openai>=1.0.0")
        
        api_key = self.api_keys.get('openai_api_key')
        if not api_key:
            raise ValueError("OpenAI API key required")
        
        self.openai_client = openai.OpenAI(api_key=api_key)
        if not self.model:
            self.model = "gpt-3.5-turbo"
        QgsMessageLog.logMessage(f"OpenAI client initialized with model: {self.model}", 'GeoGenie', Qgis.Info)
    
    def _init_anthropic(self):
        """Initialize Anthropic client"""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic package not available. Install with: pip install anthropic>=0.18.0")
        
        api_key = self.api_keys.get('anthropic_api_key') or self.api_keys.get('claude_api_key')
        if not api_key:
            raise ValueError("Anthropic/Claude API key required")
        
        self.claude_client = anthropic.Anthropic(api_key=api_key)
        if not self.model:
            self.model = "claude-3-5-sonnet-20241022"
        QgsMessageLog.logMessage(f"Anthropic client initialized with model: {self.model}", 'GeoGenie', Qgis.Info)
    
    def _init_gemini(self):
        """Initialize Gemini client"""
        if not GEMINI_AVAILABLE:
            raise ImportError("Google GenerativeAI package not available. Install with: pip install google-generativeai")
        
        api_key = self.api_keys.get('gemini_api_key')
        if not api_key:
            raise ValueError("Gemini API key required")
        
        genai.configure(api_key=api_key)
        if not self.model:
            self.model = "gemini-pro"
        QgsMessageLog.logMessage(f"Gemini client initialized with model: {self.model}", 'GeoGenie', Qgis.Info)
    
    def _init_ollama(self):
        """Initialize Ollama client"""
        if not REQUESTS_AVAILABLE:
            raise ImportError("Requests package not available. Install with: pip install requests")
        
        # Test Ollama connection
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            response.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Ollama server at {self.ollama_url}: {str(e)}")
        
        if not self.model:
            self.model = "llama2"
        QgsMessageLog.logMessage(f"Ollama client initialized with URL: {self.ollama_url}, model: {self.model}", 'GeoGenie', Qgis.Info)
    
    def is_openai_model(self, model: str) -> bool:
        """Check if model is an OpenAI model"""
        openai_models = [
            'gpt-3.5-turbo', 'gpt-3.5-turbo-0301', 'gpt-4', 'gpt-4-turbo',
            'gpt-4o', 'text-davinci-003', 'text-davinci-002'
        ]
        return model in openai_models
    
    def is_claude_model(self, model: str) -> bool:
        """Check if model is a Claude model"""
        claude_models = [
            'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022',
            'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 
            'claude-3-haiku-20240307'
        ]
        return model in claude_models
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if self.token_counter:
            try:
                return len(self.token_counter.encode(text))
            except:
                pass
        
        # Fallback estimation (rough approximation)
        return len(text.split()) * 1.3
    
    def extract_algorithm_request(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract QGIS processing algorithm request from natural language prompt
        
        Args:
            prompt: Natural language prompt from user
            context: QGIS context (layers, CRS, etc.)
            
        Returns:
            Dictionary with algorithm info and parameters
        """
        try:
            # Build function calling schema
            functions = self._build_algorithm_functions()
            
            # Create system prompt with context
            system_prompt = self._build_system_prompt(context)
            
            # Combine system prompt with user prompt
            full_prompt = f"{system_prompt}\n\nUser request: {prompt}"
            
            # Check token count
            token_count = self.count_tokens(full_prompt)
            QgsMessageLog.logMessage(f"Token count: {token_count}", 'GeoGenie', Qgis.Info)
            
            # Call appropriate model
            if self.is_claude_model(self.model) and self.claude_client:
                return self._call_claude_function(full_prompt, functions)
            elif self.is_openai_model(self.model) and self.openai_client:
                return self._call_openai_function(full_prompt, functions)
            elif self.provider == LLMProvider.GEMINI:
                return self._call_gemini_function(full_prompt, functions)
            else:
                raise Exception(f"Model {self.model} not supported or API key not provided")
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in LLM extraction: {str(e)}", 'GeoGenie', Qgis.Critical)
            return {
                'success': False,
                'error': str(e),
                'algorithm': None,
                'parameters': {},
                'confidence': 0.0
            }
    
    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt with QGIS context"""
        
        # Extract context information
        active_layers = context.get('active_layers', [])
        project_crs = context.get('project_crs', 'Unknown')
        canvas_extent = context.get('canvas_extent', 'Unknown')
        available_algorithms = context.get('available_algorithms', [])
        
        system_prompt = f"""You are GeoGenie, an AI assistant for QGIS geospatial analysis. Your task is to interpret natural language requests and convert them into specific QGIS processing algorithm calls.

CURRENT QGIS CONTEXT:
- Project CRS: {project_crs}
- Canvas Extent: {canvas_extent}
- Active Layers: {', '.join([layer['name'] for layer in active_layers]) if active_layers else 'None'}

AVAILABLE LAYERS:
"""
        
        for layer in active_layers:
            system_prompt += f"  - {layer['name']} ({layer['type']}, {layer.get('geometry_type', 'N/A')}, {layer.get('feature_count', 'N/A')} features)\n"
        
        system_prompt += f"""
AVAILABLE ALGORITHMS: {', '.join(available_algorithms)}

INSTRUCTIONS:
1. Analyze the user's natural language request
2. Identify which QGIS processing algorithm best matches their needs
3. Extract or infer the required parameters from the request and context
4. Use active layer names from the context when the user refers to "this layer", "current layer", etc.
5. If parameters are missing, use reasonable defaults or ask for clarification
6. Always return a structured response using the available functions

Remember: Only use algorithms from the available list. If the request cannot be fulfilled with available algorithms, explain the limitation.
"""
        
        return system_prompt
    
    def _build_algorithm_functions(self) -> List[Dict[str, Any]]:
        """Build function calling schema for QGIS algorithms"""
        
        from .processing_executor import AlgorithmRegistry
        
        functions = []
        
        for alg_name, alg_info in AlgorithmRegistry.SAFE_ALGORITHMS.items():
            function_def = {
                "name": f"execute_{alg_name}",
                "description": alg_info["description"],
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": alg_info["required_params"]
                }
            }
            
            # Add parameter definitions
            for param in alg_info["required_params"] + alg_info["optional_params"]:
                param_type = alg_info["param_types"].get(param, "string")
                
                if param_type == "layer":
                    function_def["parameters"]["properties"][param] = {
                        "type": "string",
                        "description": f"Name of the input layer for parameter {param}"
                    }
                elif param_type == "number":
                    function_def["parameters"]["properties"][param] = {
                        "type": "number",
                        "description": f"Numeric value for parameter {param}"
                    }
                elif param_type == "int":
                    function_def["parameters"]["properties"][param] = {
                        "type": "integer", 
                        "description": f"Integer value for parameter {param}"
                    }
                elif param_type == "boolean":
                    function_def["parameters"]["properties"][param] = {
                        "type": "boolean",
                        "description": f"Boolean value for parameter {param}"
                    }
                elif param_type == "crs":
                    function_def["parameters"]["properties"][param] = {
                        "type": "string",
                        "description": f"CRS identifier (e.g., 'EPSG:4326') for parameter {param}"
                    }
                else:
                    function_def["parameters"]["properties"][param] = {
                        "type": "string",
                        "description": f"String value for parameter {param}"
                    }
            
            functions.append(function_def)
        
        return functions
    
    def _call_openai_function(self, prompt: str, functions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call OpenAI with function calling"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                functions=functions,
                function_call="auto",
                temperature=0.1,
                max_tokens=1000
            )
            
            message = response.choices[0].message
            
            if message.function_call:
                # Parse function call
                function_name = message.function_call.name
                function_args = json.loads(message.function_call.arguments)
                
                # Extract algorithm name from function name
                algorithm_name = function_name.replace("execute_", "")
                
                return {
                    'success': True,
                    'algorithm': algorithm_name,
                    'parameters': function_args,
                    'confidence': 0.9,
                    'reasoning': message.content or f"Executing {algorithm_name} algorithm"
                }
            else:
                # No function call - return explanation
                return {
                    'success': False,
                    'error': "Could not determine appropriate algorithm",
                    'algorithm': None,
                    'parameters': {},
                    'confidence': 0.0,
                    'reasoning': message.content
                }
                
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def _call_claude_function(self, prompt: str, functions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call Claude with function calling (simulated)"""
        
        # Claude doesn't have native function calling, so we'll use structured prompts
        
        function_descriptions = "\n".join([
            f"- {func['name']}: {func['description']}"
            for func in functions
        ])
        
        structured_prompt = f"""{prompt}

AVAILABLE FUNCTIONS:
{function_descriptions}

Please respond with a JSON object in this exact format:
{{
    "algorithm": "algorithm_name",
    "parameters": {{
        "param1": "value1",
        "param2": "value2"
    }},
    "reasoning": "explanation of why this algorithm was chosen"
}}

If no suitable algorithm is available, respond with:
{{
    "algorithm": null,
    "parameters": {{}},
    "reasoning": "explanation of why no algorithm fits"
}}"""
        
        try:
            response = self.claude_client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.1,
                messages=[{"role": "user", "content": structured_prompt}]
            )
            
            response_text = response.content[0].text
            
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    
                    if result.get('algorithm'):
                        # Remove 'execute_' prefix if present
                        algorithm_name = result['algorithm']
                        if algorithm_name.startswith('execute_'):
                            algorithm_name = algorithm_name[8:]  # Remove 'execute_' prefix
                        
                        # Map parameter names from Claude response to QGIS expected names
                        raw_params = result.get('parameters', {})
                        mapped_params = self._map_parameter_names(algorithm_name, raw_params)
                        
                        return {
                            'success': True,
                            'algorithm': algorithm_name,
                            'parameters': mapped_params,
                            'confidence': 0.8,
                            'reasoning': result.get('reasoning', '')
                        }
                    else:
                        return {
                            'success': False,
                            'error': "No suitable algorithm found",
                            'algorithm': None,
                            'parameters': {},
                            'confidence': 0.0,
                            'reasoning': result.get('reasoning', 'Unknown reason')
                        }
                        
                except json.JSONDecodeError:
                    pass
            
            # Fallback if JSON parsing fails
            return {
                'success': False,
                'error': "Could not parse algorithm request",
                'algorithm': None,
                'parameters': {},
                'confidence': 0.0,
                'reasoning': response_text
            }
            
        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")
    
    def _call_gemini_function(self, prompt: str, functions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call Gemini API with function calling"""
        try:
            if not GEMINI_AVAILABLE:
                raise ImportError("Google GenerativeAI not available")
            
            # Create Gemini model
            model = genai.GenerativeModel(self.model)
            
            # Convert functions to Gemini format (use registry keys, not execute_ names)
            function_descriptions = []
            for func in functions:
                # Extract the actual algorithm name by removing 'execute_' prefix
                func_name = func['name']
                if func_name.startswith('execute_'):
                    func_name = func_name[8:]  # Remove 'execute_' prefix
                
                desc = f"Function: {func_name} - {func.get('description', '')}\n"
                desc += f"Parameters: {func.get('parameters', {}).get('properties', {}).keys()}"
                function_descriptions.append(desc)
            
            gemini_prompt = f"""
{prompt}

Available QGIS functions:
{chr(10).join(function_descriptions)}

Please respond with a JSON object containing:
- algorithm: the function name to use
- parameters: dictionary with parameter values
- confidence: float 0-1 indicating confidence
- reasoning: explanation of your choice

Example response:
{{
    "algorithm": "buffer",
    "parameters": {{"INPUT": "layer_name", "DISTANCE": 100}},
    "confidence": 0.9,
    "reasoning": "User wants to create a 100m buffer around a layer"
}}
"""
            
            # Generate response
            response = model.generate_content(gemini_prompt)
            response_text = response.text.strip()
            
            QgsMessageLog.logMessage(f"Gemini response: {response_text}", 'GeoGenie', Qgis.Info)
            
            # Parse JSON response
            try:
                import json
                result = json.loads(response_text)
                
                # Map parameters if needed
                if result.get('algorithm') and result.get('parameters'):
                    result['parameters'] = self._map_parameter_names(
                        result['algorithm'], result['parameters']
                    )
                
                return {
                    'success': True,
                    'algorithm': result.get('algorithm'),
                    'parameters': result.get('parameters', {}),
                    'confidence': result.get('confidence', 0.8),
                    'reasoning': result.get('reasoning', 'Processed with Gemini')
                }
                
            except json.JSONDecodeError:
                # Try to extract JSON from text
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        if result.get('algorithm') and result.get('parameters'):
                            result['parameters'] = self._map_parameter_names(
                                result['algorithm'], result['parameters']
                            )
                        
                        return {
                            'success': True,
                            'algorithm': result.get('algorithm'),
                            'parameters': result.get('parameters', {}),
                            'confidence': result.get('confidence', 0.7),
                            'reasoning': result.get('reasoning', response_text)
                        }
                    except json.JSONDecodeError:
                        pass
            
            # Fallback if JSON parsing fails
            return {
                'success': False,
                'error': "Could not parse algorithm request from Gemini",
                'algorithm': None,
                'parameters': {},
                'confidence': 0.0,
                'reasoning': response_text
            }
            
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    def _map_parameter_names(self, algorithm_name: str, raw_params: Dict[str, Any]) -> Dict[str, Any]:
        """Map parameter names from natural language to QGIS expected format"""
        
        # Parameter name mappings for each algorithm
        parameter_mappings = {
            'buffer': {
                'input_layer': 'INPUT',
                'layer': 'INPUT',
                'input': 'INPUT',
                'distance': 'DISTANCE',
                'buffer_distance': 'DISTANCE',
                'segments': 'SEGMENTS',
                'dissolve': 'DISSOLVE'
            },
            'clip': {
                'input_layer': 'INPUT',
                'input': 'INPUT',
                'layer': 'INPUT',
                'overlay_layer': 'OVERLAY',
                'overlay': 'OVERLAY',
                'clip_layer': 'OVERLAY'
            },
            'reproject': {
                'input_layer': 'INPUT',
                'input': 'INPUT',
                'layer': 'INPUT',
                'target_crs': 'TARGET_CRS',
                'crs': 'TARGET_CRS',
                'target_projection': 'TARGET_CRS'
            },
            'dissolve': {
                'input_layer': 'INPUT',
                'input': 'INPUT',
                'layer': 'INPUT',
                'field': 'FIELD',
                'dissolve_field': 'FIELD'
            },
            'intersection': {
                'input_layer': 'INPUT',
                'input': 'INPUT',
                'layer': 'INPUT',
                'overlay_layer': 'OVERLAY',
                'overlay': 'OVERLAY'
            }
        }
        
        mapped_params = {}
        algorithm_mapping = parameter_mappings.get(algorithm_name, {})
        
        for param_name, param_value in raw_params.items():
            # Check if there's a mapping for this parameter
            mapped_name = algorithm_mapping.get(param_name.lower(), param_name.upper())
            mapped_params[mapped_name] = param_value
        
        return mapped_params
    
    def generate_explanation(self, algorithm_name: str, parameters: Dict[str, Any], 
                           result: Dict[str, Any]) -> str:
        """Generate human-readable explanation of the algorithm execution"""
        
        from .processing_executor import AlgorithmRegistry
        
        alg_info = AlgorithmRegistry.get_algorithm_info(algorithm_name)
        if not alg_info:
            return f"Executed {algorithm_name} algorithm successfully."
        
        explanation_prompt = f"""Generate a brief, user-friendly explanation of what was accomplished:

Algorithm: {alg_info['name']} - {alg_info['description']}
Parameters used: {parameters}
Result: {result.get('statistics', {})}

Provide a 1-2 sentence explanation in plain language that a GIS user would understand."""
        
        try:
            if self.is_claude_model(self.model) and self.claude_client:
                response = self.claude_client.messages.create(
                    model=self.model,
                    max_tokens=200,
                    temperature=0.3,
                    messages=[{"role": "user", "content": explanation_prompt}]
                )
                return response.content[0].text
                
            elif self.is_openai_model(self.model) and self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": explanation_prompt}],
                    temperature=0.3,
                    max_tokens=200
                )
                return response.choices[0].message.content
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error generating explanation: {str(e)}", 
                                   'GeoGenie', Qgis.Warning)
        
        # Fallback explanation
        return f"Successfully executed {alg_info['name']} algorithm with the provided parameters."