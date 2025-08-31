# -*- coding: utf-8 -*-
"""
GeoGenie Plugin Initialization

This file initializes the GeoGenie plugin for QGIS. It tells QGIS how to load
and start the plugin when users activate it.

Author: Ahmad Abubakar Ahmad
Email: aabubaka@uni-muenster.de
Date: 2025-08-31
"""


def classFactory(iface):
    """
    Load GeoGenie plugin class.
    
    This function is called by QGIS when the plugin is loaded.
    
    Args:
        iface: QGIS interface instance
        
    Returns:
        GeoGenie plugin instance
    """
    from .geogenie import GeoGenie
    return GeoGenie(iface)
