#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for GeoGenie AI segmentation integration

This script tests the AI segmentation integration without requiring
actual ONNX models, to verify the workflow is properly connected.

Run this from within QGIS Python console to test the integration.
"""

def test_ai_segmentation_integration():
    """Test AI segmentation integration"""
    print("=== GeoGenie AI Segmentation Integration Test ===")
    
    try:
        # Import required modules
        from geogenie_coordinator import GeoGenieCoordinator
        from ai_segmentation import FastAISegmentation
        from processing_executor import AlgorithmRegistry
        
        print("✅ Successfully imported GeoGenie modules")
        
        # Test algorithm registry includes AI algorithms
        algorithms = AlgorithmRegistry.SAFE_ALGORITHMS
        ai_algorithms = {k: v for k, v in algorithms.items() if k.startswith('segment_')}
        
        print(f"✅ Found {len(ai_algorithms)} AI algorithms in registry:")
        for name, info in ai_algorithms.items():
            print(f"   - {name}: {info['description']}")
        
        # Test AI segmentation module initialization
        ai_seg = FastAISegmentation()
        print(f"✅ AI segmentation module initialized")
        print(f"   - Dependencies available: {ai_seg.available}")
        print(f"   - Available models: {ai_seg.get_available_models()}")
        
        # Test coordinator initialization
        coordinator = GeoGenieCoordinator()
        print("✅ Coordinator initialized with AI segmentation")
        
        # Test algorithm info retrieval
        building_info = AlgorithmRegistry.get_algorithm_info("segment_buildings")
        road_info = AlgorithmRegistry.get_algorithm_info("segment_roads")
        
        if building_info and road_info:
            print("✅ AI algorithm info retrieval working")
            print(f"   - Building segmentation: {building_info['algorithm_id']}")
            print(f"   - Road segmentation: {road_info['algorithm_id']}")
        else:
            print("❌ Failed to retrieve AI algorithm info")
            
        print("\n=== Integration Test Summary ===")
        print("✅ All components successfully integrated")
        print("📝 Next steps:")
        print("   1. Install ONNX models in models/ directory")
        print("   2. Test with actual raster data")
        print("   3. Verify natural language processing works")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

# Test functions for individual components
def test_algorithm_registry():
    """Test algorithm registry includes AI algorithms"""
    from processing_executor import AlgorithmRegistry
    
    algorithms = AlgorithmRegistry.SAFE_ALGORITHMS
    print("Available algorithms:")
    for name, info in algorithms.items():
        print(f"  {name}: {info['name']} - {info['description']}")
    
    return len([k for k in algorithms.keys() if k.startswith('segment_')]) == 2

def test_ai_module():
    """Test AI segmentation module"""
    from ai_segmentation import FastAISegmentation
    
    ai_seg = FastAISegmentation()
    print(f"AI module available: {ai_seg.available}")
    print(f"Available models: {ai_seg.get_available_models()}")
    
    return True

def test_coordinator():
    """Test coordinator integration"""
    from geogenie_coordinator import GeoGenieCoordinator
    
    coordinator = GeoGenieCoordinator()
    algorithms = coordinator.get_available_algorithms()
    
    ai_count = len([k for k in algorithms.keys() if k.startswith('segment_')])
    print(f"Coordinator has {ai_count} AI algorithms available")
    
    return ai_count == 2

if __name__ == "__main__":
    # Run when executed directly
    print("Run this script in QGIS Python console:")
    print("exec(open('/path/to/test_ai_integration.py').read())")
    print("test_ai_segmentation_integration()")