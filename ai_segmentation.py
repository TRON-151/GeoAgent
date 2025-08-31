# -*- coding: utf-8 -*-
"""
ai_segmentation.py

This module provides AI-powered feature detection for the GeoGenie QGIS plugin.
It can automatically find roads and buildings in satellite images using neural networks.

What it does:
- Detects roads in satellite imagery
- Finds buildings in aerial photos
- Converts AI results to QGIS vector features
- Handles coordinate transformations automatically

Requirements:
- ONNX Runtime for running neural networks
- OpenCV for image processing
- Neural network models (downloaded from Deepness project)

Author: Ahmad Abubakar Ahmad
Email: aabubaka@uni-muenster.de
Date: 2025-08-31
"""

import os
import numpy as np
from typing import Dict, Any, Optional, Tuple
from qgis.core import (
    QgsVectorLayer, QgsRasterLayer, QgsGeometry, QgsFeature, 
    QgsPointXY, QgsProject, QgsMessageLog, Qgis, QgsWkbTypes,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsRectangle, QgsRasterInterface
)
from qgis.PyQt.QtCore import QObject, pyqtSignal
import tempfile
import json

# Import dependencies with fallback handling for optional AI libraries
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


class FastAISegmentation(QObject):
    """
    AI feature detection for satellite and aerial imagery.
    
    This class finds roads and buildings in satellite images using pre-trained neural networks.
    It converts raster images into vector features that can be used in QGIS.
    
    What it can detect:
    - Roads from satellite imagery
    - Buildings from aerial photos
    
    How it works:
    - Loads ONNX neural network models
    - Processes images in 512x512 pixel chunks
    - Converts AI predictions to QGIS vector features
    - Reports progress during processing
    """
    
    # Signal definitions for progress reporting and communication with parent components
    processing_started = pyqtSignal(str)        # Emitted when segmentation starts (model_type)
    processing_progress = pyqtSignal(int, str)  # Progress updates (percentage, message)
    processing_completed = pyqtSignal(dict)     # Completed with results dictionary
    processing_error = pyqtSignal(str)          # Error message when processing fails
    
    def __init__(self, parent=None):
        """
        Set up the AI detection system.
        
        This checks for required libraries and loads available AI models.
        If libraries are missing, AI features will be disabled.
        
        Args:
            parent: Parent object for Qt
        """
        super().__init__(parent)
        
        # Check for required AI dependencies before initialization
        self.available = ONNX_AVAILABLE and OPENCV_AVAILABLE and PILLOW_AVAILABLE
        
        if not self.available:
            missing = []
            if not ONNX_AVAILABLE:
                missing.append("onnxruntime")
            if not OPENCV_AVAILABLE:
                missing.append("opencv-python")
            if not PILLOW_AVAILABLE:
                missing.append("pillow")
            
            QgsMessageLog.logMessage(
                f"AI Segmentation unavailable. Missing: {', '.join(missing)}",
                "GeoGenie", Qgis.Warning
            )
            return
        
        # Model configuration
        self.models = {}
        self.model_configs = {
            "buildings": {
                "file": "building_segmentation.onnx",
                "input_size": (512, 512),
                "confidence_threshold": 0.5,
                "description": "Building footprint extraction"
            },
            "roads": {
                "file": "road_segmentation.onnx", 
                "input_size": (512, 512),
                "confidence_threshold": 0.4,
                "description": "Road network detection (Deepness model - optimized for wide roads, crossroads, roundabouts)"
            }
        }
        
        # Initialize models
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize ONNX models if available"""
        plugin_dir = os.path.dirname(__file__)
        models_dir = os.path.join(plugin_dir, "models")
        
        if not os.path.exists(models_dir):
            os.makedirs(models_dir)
            QgsMessageLog.logMessage(
                f"Created models directory: {models_dir}",
                "GeoGenie", Qgis.Info
            )
        
        # Load available models
        for model_name, config in self.model_configs.items():
            model_path = os.path.join(models_dir, config["file"])
            
            if os.path.exists(model_path):
                try:
                    session = ort.InferenceSession(model_path)
                    self.models[model_name] = session
                    QgsMessageLog.logMessage(
                        f"Loaded AI model: {model_name}",
                        "GeoGenie", Qgis.Info
                    )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Failed to load model {model_name}: {str(e)}",
                        "GeoGenie", Qgis.Warning
                    )
            else:
                QgsMessageLog.logMessage(
                    f"Model not found: {model_path}",
                    "GeoGenie", Qgis.Warning
                )
    
    def is_available(self) -> bool:
        """
        Check if AI segmentation functionality is available.
        
        Returns:
            bool: True if all dependencies are installed and at least one model is loaded
        """
        return self.available and len(self.models) > 0
    
    def get_available_models(self) -> Dict[str, str]:
        """
        Get dictionary of currently loaded and available AI models.
        
        Returns:
            Dict[str, str]: Dictionary mapping model names to their descriptions
                           e.g., {'roads': 'Road network extraction', 'buildings': 'Building footprint extraction'}
        """
        available = {}
        for name, session in self.models.items():
            if session is not None:
                available[name] = self.model_configs[name]["description"]
        return available
    
    def segment_features(self, raster_layer: QgsRasterLayer, model_type: str, 
                        confidence: float = None, extent: QgsRectangle = None) -> Dict[str, Any]:
        """
        Extract geographic features from satellite imagery using AI models.
        
        This function processes raster imagery to find roads or buildings. It reads the image,
        runs it through a neural network model, and creates vector features from the results.
        
        Args:
            raster_layer: The satellite or aerial image to process
            model_type: What to detect - "roads" or "buildings"
            confidence: How confident the detection must be (0.0 to 1.0)
            extent: Area to process, uses current map view if not specified
            
        Returns:
            Dictionary containing the results and feature count
        """
        
        if not self.is_available():
            raise ValueError("AI segmentation not available")
        
        if model_type not in self.models:
            raise ValueError(f"Model '{model_type}' not available. Available: {list(self.models.keys())}")
        
        if not isinstance(raster_layer, QgsRasterLayer) or not raster_layer.isValid():
            raise ValueError("Invalid raster layer provided")
        
        # Set default confidence
        if confidence is None:
            confidence = self.model_configs[model_type]["confidence_threshold"]
        
        # Signal processing start
        self.processing_started.emit(model_type)
        self.processing_progress.emit(10, f"Preparing {model_type} segmentation...")
        
        try:
            # Determine which area to process
            actual_extent = extent or raster_layer.extent()
            QgsMessageLog.logMessage(f"Using extent: {actual_extent.toString()}", "GeoGenie", Qgis.Info)
            QgsMessageLog.logMessage(f"Layer CRS: {raster_layer.crs().authid()}", "GeoGenie", Qgis.Info)
            
            # Step 1: Read image data from raster layer
            self.processing_progress.emit(30, "Converting raster data...")
            img_array = self._raster_to_array(raster_layer, extent)
            
            # Step 2: Run the AI model to detect features
            self.processing_progress.emit(50, "Running AI inference...")
            prediction = self._run_inference(model_type, img_array)
            
            # Step 3: Convert AI results to QGIS vector features
            self.processing_progress.emit(80, "Converting to vector features...")
            vector_layer = self._mask_to_vector(
                prediction, confidence, raster_layer.crs(), 
                actual_extent, model_type
            )
            
            # Prepare result
            feature_count = vector_layer.featureCount()
            result = {
                "output_layer": vector_layer,
                "model_type": model_type,
                "confidence": confidence,
                "feature_count": feature_count,
                "success": True
            }
            
            self.processing_progress.emit(100, f"Complete: {feature_count} features found")
            self.processing_completed.emit(result)
            
            return result
            
        except Exception as e:
            error_msg = f"AI segmentation failed: {str(e)}"
            QgsMessageLog.logMessage(error_msg, "GeoGenie", Qgis.Critical)
            self.processing_error.emit(error_msg)
            raise
    
    def _raster_to_array(self, raster_layer: QgsRasterLayer, extent: QgsRectangle = None) -> np.ndarray:
        """Convert raster layer to numpy array using modern QGIS API"""
        
        # Use provided extent or layer extent
        if extent is None:
            extent = raster_layer.extent()
            
        QgsMessageLog.logMessage(f"Reading raster with extent: {extent.toString()}", "GeoGenie", Qgis.Info)
        
        # Get raster dimensions
        provider = raster_layer.dataProvider()
        
        # Calculate pixel dimensions
        x_size = int((extent.width() / raster_layer.rasterUnitsPerPixelX()))
        y_size = int((extent.height() / raster_layer.rasterUnitsPerPixelY()))
        
        # Limit size for performance (max 2048x2048)
        max_size = 2048
        if x_size > max_size or y_size > max_size:
            scale_factor = max_size / max(x_size, y_size)
            x_size = int(x_size * scale_factor)
            y_size = int(y_size * scale_factor)
        
        QgsMessageLog.logMessage(f"Reading raster data: {x_size}x{y_size} pixels", "GeoGenie", Qgis.Info)
        
        # Read raster data using modern QGIS API
        try:
            if raster_layer.bandCount() >= 3:
                # RGB image - read each band
                bands = []
                for band_num in [1, 2, 3]:  # R, G, B
                    block = provider.block(band_num, extent, x_size, y_size)
                    if block.isValid():
                        # Convert QgsRasterBlock to numpy array
                        band_data = self._block_to_array(block, x_size, y_size)
                        bands.append(band_data)
                    else:
                        QgsMessageLog.logMessage(f"Invalid raster block for band {band_num}", "GeoGenie", Qgis.Warning)
                        # Create dummy band data
                        band_data = np.zeros((y_size, x_size), dtype=np.uint8)
                        bands.append(band_data)
                
                if len(bands) == 3:
                    img_array = np.stack(bands, axis=-1)  # Shape: (height, width, 3)
                else:
                    QgsMessageLog.logMessage("Failed to read RGB bands, using grayscale", "GeoGenie", Qgis.Warning)
                    # Fallback to first band only
                    block = provider.block(1, extent, x_size, y_size)
                    gray_data = self._block_to_array(block, x_size, y_size)
                    img_array = np.stack([gray_data, gray_data, gray_data], axis=-1)
            else:
                # Single band (grayscale) - convert to RGB
                block = provider.block(1, extent, x_size, y_size)
                if block.isValid():
                    gray_data = self._block_to_array(block, x_size, y_size)
                    img_array = np.stack([gray_data, gray_data, gray_data], axis=-1)
                else:
                    QgsMessageLog.logMessage("Invalid raster block for single band", "GeoGenie", Qgis.Critical)
                    # Create dummy data
                    gray_data = np.zeros((y_size, x_size), dtype=np.uint8)
                    img_array = np.stack([gray_data, gray_data, gray_data], axis=-1)
            
            # Ensure proper data type and range
            img_array = np.clip(img_array, 0, 255).astype(np.uint8)
            
            QgsMessageLog.logMessage(f"Converted raster to array: {img_array.shape}, dtype: {img_array.dtype}", "GeoGenie", Qgis.Info)
            return img_array
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in raster conversion: {str(e)}", "GeoGenie", Qgis.Critical)
            raise
    
    def _block_to_array(self, block, width, height):
        """Convert QgsRasterBlock to numpy array"""
        try:
            # Method 1: Try using block data directly
            if hasattr(block, 'data'):
                # Get raw data
                data = block.data()
                # Convert to numpy array
                if hasattr(data, 'data'):  # QByteArray
                    import struct
                    # Assume uint8 data for now
                    values = struct.unpack(f'<{width*height}B', data.data()[:width*height])
                    array = np.array(values, dtype=np.uint8).reshape(height, width)
                    return array
            
            # Method 2: Use value() method to read pixel by pixel (slower but reliable)
            array = np.zeros((height, width), dtype=np.float32)
            for row in range(height):
                for col in range(width):
                    value = block.value(row, col)
                    if not block.isNoData(value):
                        array[row, col] = value
                    # else: leave as 0 for nodata
            
            # Convert to uint8 (assuming data is in 0-255 range, adjust if needed)
            array = np.clip(array, 0, 255).astype(np.uint8)
            return array
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error converting block to array: {str(e)}", "GeoGenie", Qgis.Warning)
            # Return zeros as fallback
            return np.zeros((height, width), dtype=np.uint8)
    
    def _run_inference(self, model_type: str, img_array: np.ndarray) -> np.ndarray:
        """
        Run the AI model on the image to detect features.
        
        This function prepares the image for the neural network and runs the detection.
        
        Args:
            model_type: Type of model to use ("roads" or "buildings")
            img_array: Image data as numpy array
            
        Returns:
            Prediction mask showing where features were detected
        """
        
        session = self.models[model_type]
        config = self.model_configs[model_type]
        
        # Resize to model input size
        target_size = config["input_size"]
        original_size = img_array.shape[:2]
        
        QgsMessageLog.logMessage(f"Input image shape: {img_array.shape}, target size: {target_size}", "GeoGenie", Qgis.Info)
        QgsMessageLog.logMessage(f"Input image dtype: {img_array.dtype}, min: {img_array.min()}, max: {img_array.max()}", "GeoGenie", Qgis.Info)
        
        # Make sure image is RGB and resize to model requirements (512x512)
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_resized = cv2.resize(img_array, target_size, interpolation=cv2.INTER_LINEAR)
        else:
            # Convert grayscale or other formats to RGB
            img_rgb = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB) if len(img_array.shape) == 3 else np.stack([img_array]*3, axis=-1)
            img_resized = cv2.resize(img_rgb, target_size, interpolation=cv2.INTER_LINEAR)
        
        QgsMessageLog.logMessage(f"Resized image shape: {img_resized.shape}", "GeoGenie", Qgis.Info)
        
        # Convert pixel values from 0-255 range to 0-1 range for the AI model
        input_data = img_resized.astype(np.float32) / 255.0
        
        # Rearrange data format for neural network (channels first, add batch dimension)
        input_data = np.expand_dims(input_data.transpose(2, 0, 1), axis=0)
        
        QgsMessageLog.logMessage(f"Model input shape: {input_data.shape}, dtype: {input_data.dtype}", "GeoGenie", Qgis.Info)
        QgsMessageLog.logMessage(f"Model input range: {input_data.min():.3f} to {input_data.max():.3f}", "GeoGenie", Qgis.Info)
        
        # Get input/output names
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        
        # Run inference
        QgsMessageLog.logMessage(f"Running inference with input name: {input_name}, output name: {output_name}", "GeoGenie", Qgis.Info)
        result = session.run([output_name], {input_name: input_data})
        prediction = result[0]
        
        QgsMessageLog.logMessage(f"Model output shape: {prediction.shape}, dtype: {prediction.dtype}", "GeoGenie", Qgis.Info)
        QgsMessageLog.logMessage(f"Model output range: {prediction.min():.3f} to {prediction.max():.3f}", "GeoGenie", Qgis.Info)
        
        # Handle multi-class output if present
        if len(prediction.shape) == 4:  # NCHW format
            QgsMessageLog.logMessage(f"Multi-class output detected: {prediction.shape}", "GeoGenie", Qgis.Info)
            # For road segmentation, we might need to take the road class
            # Assuming class 0 = background, class 1 = road (check model documentation)
            if prediction.shape[1] > 1:  # Multiple classes
                # Take the road class probability (typically class 1)
                prediction = prediction[0, 1]  # First batch, road class
                QgsMessageLog.logMessage(f"Selected road class, shape: {prediction.shape}", "GeoGenie", Qgis.Info)
            else:
                prediction = prediction[0, 0]  # First batch, single channel
        elif len(prediction.shape) == 3:  # CHW format
            if prediction.shape[0] > 1:  # Multiple classes
                prediction = prediction[1]  # Road class
            else:
                prediction = prediction[0]  # Single channel
        
        # Resize back to original size if needed
        if prediction.shape != original_size:
            QgsMessageLog.logMessage(f"Resizing prediction from {prediction.shape} to {original_size}", "GeoGenie", Qgis.Info)
            prediction = cv2.resize(prediction, (original_size[1], original_size[0]), interpolation=cv2.INTER_LINEAR)
        
        QgsMessageLog.logMessage(f"Final prediction shape: {prediction.shape}, range: {prediction.min():.3f} to {prediction.max():.3f}", "GeoGenie", Qgis.Info)
        return prediction
    
    def _mask_to_vector(self, mask: np.ndarray, confidence: float, 
                       crs: QgsCoordinateReferenceSystem, extent: QgsRectangle, 
                       model_type: str) -> QgsVectorLayer:
        """Convert segmentation mask to vector layer"""
        
        QgsMessageLog.logMessage(f"Converting mask to vector: mask shape={mask.shape}, confidence={confidence}", "GeoGenie", Qgis.Info)
        QgsMessageLog.logMessage(f"Extent for coordinate transformation: {extent.toString()}", "GeoGenie", Qgis.Info)
        
        # Threshold mask
        binary_mask = (mask > confidence).astype(np.uint8)
        pixels_above_threshold = np.sum(binary_mask > 0)
        QgsMessageLog.logMessage(f"Pixels above confidence threshold: {pixels_above_threshold} out of {mask.size}", "GeoGenie", Qgis.Info)
        
        # Find contours
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        QgsMessageLog.logMessage(f"Found {len(contours)} contours", "GeoGenie", Qgis.Info)
        
        # Create memory vector layer
        layer_name = f"AI_{model_type}_{confidence:.1f}"
        
        if model_type == "roads":
            geom_type = "LineString"
        else:
            geom_type = "Polygon"
        
        vector_layer = QgsVectorLayer(f"{geom_type}?crs={crs.authid()}", layer_name, "memory")
        provider = vector_layer.dataProvider()
        
        # Add attributes
        from qgis.core import QgsField
        from qgis.PyQt.QtCore import QVariant
        
        provider.addAttributes([
            QgsField("id", QVariant.Int),
            QgsField("confidence", QVariant.Double),
            QgsField("area", QVariant.Double),
            QgsField("model_type", QVariant.String)
        ])
        vector_layer.updateFields()
        
        # Convert contours to features
        features = []
        mask_height, mask_width = mask.shape
        
        for i, contour in enumerate(contours):
            if len(contour) < 3:  # Skip small contours
                QgsMessageLog.logMessage(f"Skipping contour {i}: too few points ({len(contour)})", "GeoGenie", Qgis.Info)
                continue
            
            # Convert pixel coordinates to map coordinates
            points = []
            for j, point in enumerate(contour):
                x_pixel, y_pixel = point[0]
                
                # Convert pixel to map coordinates
                x_ratio = x_pixel / mask_width
                y_ratio = y_pixel / mask_height
                x_map = extent.xMinimum() + x_ratio * extent.width()
                y_map = extent.yMaximum() - y_ratio * extent.height()
                
                points.append(QgsPointXY(x_map, y_map))
                
            
            if len(points) < 3:
                QgsMessageLog.logMessage(f"Skipping contour {i}: not enough valid points ({len(points)})", "GeoGenie", Qgis.Info)
                continue
            
            # Create geometry
            if geom_type == "LineString":
                geometry = QgsGeometry.fromPolylineXY(points)
            else:
                # Close polygon
                if points[0] != points[-1]:
                    points.append(points[0])
                geometry = QgsGeometry.fromPolygonXY([points])
            
            # Check geometry validity (compatible with different QGIS versions)
            try:
                if geometry.isNull():
                    QgsMessageLog.logMessage(f"Skipping contour {i}: null geometry", "GeoGenie", Qgis.Info)
                    continue
                # Try modern QGIS API first
                if hasattr(geometry, 'isValid') and callable(geometry.isValid):
                    try:
                        # Try with no parameters first
                        is_valid = geometry.isValid()
                    except TypeError:
                        # If that fails, try with default parameters
                        try:
                            is_valid = geometry.isValid(0)  # 0 = default validation
                        except:
                            is_valid = True  # Assume valid if we can't check
                    
                    if not is_valid:
                        QgsMessageLog.logMessage(f"Skipping contour {i}: invalid geometry", "GeoGenie", Qgis.Info)
                        continue
                # Additional check: make sure geometry has reasonable size
                if geom_type == "Polygon" and geometry.area() <= 0:
                    QgsMessageLog.logMessage(f"Skipping contour {i}: polygon with zero area", "GeoGenie", Qgis.Info)
                    continue
                elif geom_type == "LineString" and geometry.length() <= 0:
                    QgsMessageLog.logMessage(f"Skipping contour {i}: linestring with zero length", "GeoGenie", Qgis.Info)
                    continue
                    
            except Exception as e:
                QgsMessageLog.logMessage(f"Geometry validation error: {str(e)}", "GeoGenie", Qgis.Warning)
                continue
            
            # Create feature
            feature = QgsFeature()
            feature.setGeometry(geometry)
            
            # Calculate appropriate measurement (area for polygons, length for lines)
            measurement = geometry.area() if geom_type == "Polygon" else geometry.length()
            
            feature.setAttributes([
                i + 1,  # id
                float(confidence),  # confidence
                measurement,  # area/length
                model_type  # model_type
            ])
            
            features.append(feature)
        
        # Add features to layer
        provider.addFeatures(features)
        vector_layer.updateExtents()
        
        QgsMessageLog.logMessage(
            f"Created {len(features)} {model_type} features",
            "GeoGenie", Qgis.Info
        )
        
        return vector_layer


def create_test_model_placeholder():
    """Create placeholder model files for testing"""
    plugin_dir = os.path.dirname(__file__)
    models_dir = os.path.join(plugin_dir, "models")
    
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
    
    # Create placeholder info file
    info_file = os.path.join(models_dir, "README.txt")
    with open(info_file, 'w') as f:
        f.write("""GeoGenie AI Models Directory

Place your ONNX model files here:
- building_segmentation.onnx (for building detection)
- road_segmentation.onnx (for road detection)

Models should accept RGB input of shape (1, 3, H, W) and 
output segmentation masks of shape (1, 1, H, W) or (H, W).

You can download suitable models from:
- Hugging Face Model Hub
- ONNX Model Zoo
- Custom trained models

Ensure models are licensed for your use case.
""")
    
    return models_dir