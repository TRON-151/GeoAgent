# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Context Manager
                                 A QGIS plugin
 Context injection system for GeoGenie
                             -------------------
        begin                : 2025-01-18
        copyright            : (C) 2025 by Ahmad Abubakar Ahmad
        email                : ahmad.abubakar@uni-muenster.de
 ***************************************************************************/
"""

from typing import Dict, Any, List, Optional
from qgis.core import (
    QgsProject,
    QgsMapLayer,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsLayerTreeLayer,
    QgsLayerTree,
    QgsMessageLog,
    QgsGeometry,
    QgsFeature,
    Qgis
)
from qgis.gui import QgsMapCanvas
from qgis.utils import iface


class ContextManager:
    """
    Manages QGIS context information for LLM prompts
    
    Extracts current state of QGIS project including:
    - Active layers and their properties
    - Project CRS
    - Canvas extent
    - Selected features
    - Layer statistics
    """
    
    def __init__(self):
        self.project = QgsProject.instance()
        self.canvas = iface.mapCanvas() if iface else None
    
    def build_context(self) -> Dict[str, Any]:
        """
        Build comprehensive context object for LLM prompts
        
        Returns:
            Dictionary containing current QGIS context information
        """
        try:
            context = {
                'project_info': self._get_project_info(),
                'active_layers': self._get_active_layers(),
                'project_crs': self._get_project_crs(),
                'canvas_extent': self._get_canvas_extent(),
                'selected_features': self._get_selected_features(),
                'layer_tree_info': self._get_layer_tree_info(),
                'available_algorithms': self._get_available_algorithms()
            }
            
            # Log context size for debugging
            context_size = len(str(context))
            QgsMessageLog.logMessage(f"Context size: {context_size} characters", 
                                   'GeoGenie', Qgis.Info)
            
            return context
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error building context: {str(e)}", 
                                   'GeoGenie', Qgis.Critical)
            return self._get_minimal_context()
    
    def _get_project_info(self) -> Dict[str, Any]:
        """Get basic project information"""
        return {
            'title': self.project.title() or 'Untitled Project',
            'filename': self.project.fileName() or 'Unsaved Project',
            'is_dirty': self.project.isDirty(),
            'layer_count': len(self.project.mapLayers())
        }
    
    def _get_active_layers(self) -> List[Dict[str, Any]]:
        """
        Get information about active/visible layers
        
        Returns:
            List of layer information dictionaries
        """
        layers_info = []
        
        try:
            # Get all layers in the project
            layers = self.project.mapLayers().values()
            
            for layer in layers:
                if not layer.isValid():
                    continue
                
                layer_info = {
                    'name': layer.name(),
                    'id': layer.id(),
                    'type': self._get_layer_type_string(layer),
                    'is_visible': self._is_layer_visible(layer),
                    'crs': layer.crs().authid(),
                    'extent': layer.extent().toString()
                }
                
                # Add type-specific information
                if isinstance(layer, QgsVectorLayer):
                    layer_info.update(self._get_vector_layer_info(layer))
                elif isinstance(layer, QgsRasterLayer):
                    layer_info.update(self._get_raster_layer_info(layer))
                
                layers_info.append(layer_info)
            
            # Sort by visibility (visible layers first) and then by name
            layers_info.sort(key=lambda x: (not x['is_visible'], x['name'].lower()))
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error getting layer info: {str(e)}", 
                                   'GeoGenie', Qgis.Warning)
        
        return layers_info
    
    def _get_vector_layer_info(self, layer: QgsVectorLayer) -> Dict[str, Any]:
        """Get additional information for vector layers"""
        info = {}
        
        try:
            info.update({
                'geometry_type': layer.geometryType().name if layer.geometryType() else 'Unknown',
                'feature_count': layer.featureCount(),
                'fields': [field.name() for field in layer.fields()],
                'selected_count': layer.selectedFeatureCount(),
                'is_editable': layer.isEditable(),
                'provider': layer.providerType()
            })
            
            # Get basic statistics for numeric fields (limit to first 5 fields)
            numeric_fields = []
            fields = layer.fields()
            for i in range(min(5, len(fields))):
                field = fields[i]
                if field.type() in [2, 6, 10]:  # Integer, Double, LongLong
                    numeric_fields.append(field.name())
            
            if numeric_fields:
                info['numeric_fields'] = numeric_fields
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error getting vector layer info: {str(e)}", 
                                   'GeoGenie', Qgis.Warning)
        
        return info
    
    def _get_raster_layer_info(self, layer: QgsRasterLayer) -> Dict[str, Any]:
        """Get additional information for raster layers"""
        info = {}
        
        try:
            info.update({
                'band_count': layer.bandCount(),
                'width': layer.width(),
                'height': layer.height(),
                'pixel_size_x': layer.rasterUnitsPerPixelX(),
                'pixel_size_y': layer.rasterUnitsPerPixelY(),
                'provider': layer.providerType()
            })
            
            # Get band information
            bands_info = []
            for i in range(1, min(layer.bandCount() + 1, 4)):  # Limit to first 3 bands
                band_name = layer.bandName(i)
                bands_info.append({
                    'band': i,
                    'name': band_name
                })
            
            if bands_info:
                info['bands'] = bands_info
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error getting raster layer info: {str(e)}", 
                                   'GeoGenie', Qgis.Warning)
        
        return info
    
    def _get_layer_type_string(self, layer: QgsMapLayer) -> str:
        """Get human-readable layer type"""
        if isinstance(layer, QgsVectorLayer):
            geom_type = layer.geometryType()
            if geom_type == 0:
                return 'Point Vector'
            elif geom_type == 1:
                return 'Line Vector'
            elif geom_type == 2:
                return 'Polygon Vector'
            else:
                return 'Vector'
        elif isinstance(layer, QgsRasterLayer):
            return 'Raster'
        else:
            return 'Other'
    
    def _is_layer_visible(self, layer: QgsMapLayer) -> bool:
        """Check if layer is visible in layer tree"""
        try:
            root = self.project.layerTreeRoot()
            layer_node = root.findLayer(layer.id())
            return layer_node.isVisible() if layer_node else False
        except:
            return True  # Default to visible if we can't determine
    
    def _get_project_crs(self) -> str:
        """Get project CRS information"""
        try:
            crs = self.project.crs()
            return crs.authid() or crs.description() or 'Unknown'
        except:
            return 'Unknown'
    
    def _get_canvas_extent(self) -> str:
        """Get current canvas extent"""
        try:
            if self.canvas:
                extent = self.canvas.extent()
                return f"X: {extent.xMinimum():.2f} - {extent.xMaximum():.2f}, Y: {extent.yMinimum():.2f} - {extent.yMaximum():.2f}"
            return 'Unknown'
        except:
            return 'Unknown'
    
    def _get_selected_features(self) -> Dict[str, int]:
        """Get count of selected features per layer"""
        selection_info = {}
        
        try:
            layers = self.project.mapLayers().values()
            
            for layer in layers:
                if isinstance(layer, QgsVectorLayer):
                    selected_count = layer.selectedFeatureCount()
                    if selected_count > 0:
                        selection_info[layer.name()] = selected_count
                        
        except Exception as e:
            QgsMessageLog.logMessage(f"Error getting selection info: {str(e)}", 
                                   'GeoGenie', Qgis.Warning)
        
        return selection_info
    
    def _get_layer_tree_info(self) -> Dict[str, Any]:
        """Get layer tree structure information"""
        info = {
            'groups': [],
            'layer_order': []
        }
        
        try:
            root = self.project.layerTreeRoot()
            
            # Get groups
            for group in root.findGroups():
                info['groups'].append({
                    'name': group.name(),
                    'is_visible': group.isVisible(),
                    'layer_count': len(group.findLayers())
                })
            
            # Get layer order (top to bottom in TOC)
            for layer_node in root.findLayers():
                layer = layer_node.layer()
                if layer:
                    info['layer_order'].append({
                        'name': layer.name(),
                        'is_visible': layer_node.isVisible()
                    })
                    
        except Exception as e:
            QgsMessageLog.logMessage(f"Error getting layer tree info: {str(e)}", 
                                   'GeoGenie', Qgis.Warning)
        
        return info
    
    def _get_available_algorithms(self) -> List[str]:
        """Get list of available GeoGenie algorithms"""
        from .processing_executor import AlgorithmRegistry
        return AlgorithmRegistry.get_available_algorithms()
    
    def _get_minimal_context(self) -> Dict[str, Any]:
        """Get minimal context in case of errors"""
        return {
            'project_info': {'title': 'Unknown Project', 'layer_count': 0},
            'active_layers': [],
            'project_crs': 'Unknown',
            'canvas_extent': 'Unknown',
            'selected_features': {},
            'layer_tree_info': {'groups': [], 'layer_order': []},
            'available_algorithms': []
        }
    
    def get_layer_by_name(self, layer_name: str) -> Optional[QgsMapLayer]:
        """
        Get layer by name (case-insensitive)
        
        Args:
            layer_name: Name of the layer to find
            
        Returns:
            QgsMapLayer if found, None otherwise
        """
        try:
            layers = self.project.mapLayers().values()
            
            # First try exact match
            for layer in layers:
                if layer.name() == layer_name:
                    return layer
            
            # Then try case-insensitive match
            for layer in layers:
                if layer.name().lower() == layer_name.lower():
                    return layer
            
            # Finally try partial match
            for layer in layers:
                if layer_name.lower() in layer.name().lower():
                    return layer
                    
        except Exception as e:
            QgsMessageLog.logMessage(f"Error finding layer '{layer_name}': {str(e)}", 
                                   'GeoGenie', Qgis.Warning)
        
        return None
    
    def validate_layer_for_algorithm(self, layer_name: str, 
                                   expected_type: str = None) -> Dict[str, Any]:
        """
        Validate that a layer exists and is suitable for an algorithm
        
        Args:
            layer_name: Name of the layer
            expected_type: Expected layer type ('vector', 'raster', 'point', 'line', 'polygon')
            
        Returns:
            Validation result dictionary
        """
        layer = self.get_layer_by_name(layer_name)
        
        if not layer:
            return {
                'valid': False,
                'error': f"Layer '{layer_name}' not found",
                'layer': None
            }
        
        if not layer.isValid():
            return {
                'valid': False,
                'error': f"Layer '{layer_name}' is not valid",
                'layer': layer
            }
        
        # Check type if specified
        if expected_type:
            layer_type_ok = True
            
            if expected_type == 'vector' and not isinstance(layer, QgsVectorLayer):
                layer_type_ok = False
            elif expected_type == 'raster' and not isinstance(layer, QgsRasterLayer):
                layer_type_ok = False
            elif expected_type in ['point', 'line', 'polygon']:
                if not isinstance(layer, QgsVectorLayer):
                    layer_type_ok = False
                else:
                    geom_type = layer.geometryType()
                    type_map = {'point': 0, 'line': 1, 'polygon': 2}
                    if geom_type != type_map.get(expected_type, -1):
                        layer_type_ok = False
            
            if not layer_type_ok:
                return {
                    'valid': False,
                    'error': f"Layer '{layer_name}' is not a {expected_type} layer",
                    'layer': layer
                }
        
        return {
            'valid': True,
            'error': None,
            'layer': layer
        }
    
    def get_context_summary(self) -> str:
        """Get a brief text summary of the current context"""
        context = self.build_context()
        
        layer_count = len(context['active_layers'])
        visible_layers = [l for l in context['active_layers'] if l['is_visible']]
        
        summary = f"QGIS Project Context:\n"
        summary += f"- Project: {context['project_info']['title']}\n"
        summary += f"- CRS: {context['project_crs']}\n"
        summary += f"- Total layers: {layer_count}\n"
        summary += f"- Visible layers: {len(visible_layers)}\n"
        
        if visible_layers:
            summary += "- Layer names: " + ", ".join([l['name'] for l in visible_layers[:5]])
            if len(visible_layers) > 5:
                summary += f" (and {len(visible_layers)-5} more)"
        
        return summary
    
    def ensure_spatial_indexes(self) -> Dict[str, bool]:
        """
        Proactively create spatial indexes for all vector layers in the project
        
        Returns:
            Dictionary mapping layer names to index creation success status
        """
        results = {}
        
        try:
            layers = self.project.mapLayers().values()
            
            for layer in layers:
                if isinstance(layer, QgsVectorLayer) and layer.isValid():
                    layer_name = layer.name()
                    
                    if not layer.hasSpatialIndex():
                        QgsMessageLog.logMessage(f"Creating spatial index for: {layer_name}", 'GeoGenie', Qgis.Info)
                        success = layer.createSpatialIndex()
                        results[layer_name] = success
                        
                        if success:
                            QgsMessageLog.logMessage(f"✅ Spatial index created for: {layer_name}", 'GeoGenie', Qgis.Info)
                        else:
                            QgsMessageLog.logMessage(f"⚠️ Failed to create spatial index for: {layer_name}", 'GeoGenie', Qgis.Warning)
                    else:
                        QgsMessageLog.logMessage(f"Spatial index already exists for: {layer_name}", 'GeoGenie', Qgis.Info)
                        results[layer_name] = True
                        
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in bulk spatial index creation: {str(e)}", 'GeoGenie', Qgis.Warning)
        
        return results