#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Road Segmentation Model Test Script for GeoGenie

Tests the Deepness road segmentation model integration in GeoGenie.
This script validates model loading, inference, and integration workflow.

Usage: Run in QGIS Python console
"""

import os
import sys
import numpy as np

def test_model_loading():
    """Test basic ONNX model loading"""
    print("=== Testing Road Segmentation Model Loading ===")
    
    try:
        # Test ONNX runtime import
        import onnxruntime as ort
        print("✅ ONNX Runtime available")
        
        # Test model loading
        plugin_dir = os.path.dirname(__file__)
        model_path = os.path.join(plugin_dir, "models", "road_segmentation.onnx")
        
        if not os.path.exists(model_path):
            print(f"❌ Model not found: {model_path}")
            return False
        
        print(f"✅ Model file found: {os.path.basename(model_path)} ({os.path.getsize(model_path) / 1024 / 1024:.1f} MB)")
        
        # Load ONNX session
        session = ort.InferenceSession(model_path)
        print("✅ ONNX session created successfully")
        
        # Check model inputs/outputs
        input_info = session.get_inputs()[0]
        output_info = session.get_outputs()[0]
        
        print(f"✅ Model Input: {input_info.name} - Shape: {input_info.shape} - Type: {input_info.type}")
        print(f"✅ Model Output: {output_info.name} - Shape: {output_info.shape} - Type: {output_info.type}")
        
        # Validate expected format
        expected_input_shape = [1, 3, 512, 512]  # NCHW format
        if input_info.shape == expected_input_shape or input_info.shape[1:] == expected_input_shape[1:]:
            print("✅ Input shape matches expected format (1, 3, 512, 512)")
        else:
            print(f"⚠️ Unexpected input shape: {input_info.shape}, expected: {expected_input_shape}")
        
        return session
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        return False

def test_inference_pipeline(session):
    """Test inference with synthetic data"""
    print("\n=== Testing Inference Pipeline ===")
    
    try:
        import cv2
        print("✅ OpenCV available")
        
        # Create synthetic RGB image (512x512)
        synthetic_image = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
        print("✅ Created synthetic test image (512x512x3)")
        
        # Preprocess for model input
        # Convert to float and normalize
        img_float = synthetic_image.astype(np.float32) / 255.0
        
        # Convert HWC to CHW and add batch dimension
        img_input = img_float.transpose(2, 0, 1)[np.newaxis, ...]  # Shape: (1, 3, 512, 512)
        print(f"✅ Preprocessed input shape: {img_input.shape}")
        
        # Run inference
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        
        result = session.run([output_name], {input_name: img_input})
        prediction = result[0]
        
        print(f"✅ Inference successful - Output shape: {prediction.shape}")
        print(f"✅ Output value range: {prediction.min():.3f} to {prediction.max():.3f}")
        
        # Validate output format
        if len(prediction.shape) == 4 and prediction.shape[0] == 1:
            print("✅ Output has correct batch dimension")
        
        # Convert to binary mask
        binary_mask = (prediction > 0.5).astype(np.uint8)
        road_pixels = np.sum(binary_mask)
        total_pixels = binary_mask.size
        
        print(f"✅ Binary conversion successful")
        print(f"   - Road pixels: {road_pixels} ({road_pixels/total_pixels*100:.1f}%)")
        print(f"   - Non-road pixels: {total_pixels - road_pixels} ({(total_pixels-road_pixels)/total_pixels*100:.1f}%)")
        
        return prediction
        
    except Exception as e:
        print(f"❌ Inference failed: {e}")
        return None

def test_ai_segmentation_integration():
    """Test GeoGenie AI segmentation module integration"""
    print("\n=== Testing GeoGenie AI Segmentation Integration ===")
    
    try:
        from ai_segmentation import FastAISegmentation
        
        # Initialize AI segmentation module
        ai_seg = FastAISegmentation()
        print(f"✅ FastAISegmentation initialized")
        print(f"   - Dependencies available: {ai_seg.available}")
        print(f"   - Available models: {list(ai_seg.get_available_models().keys())}")
        
        if not ai_seg.is_available():
            print("❌ AI segmentation not available - check dependencies")
            return False
        
        if 'roads' not in ai_seg.get_available_models():
            print("❌ Road model not detected in AI segmentation module")
            return False
        
        print("✅ Road segmentation model properly integrated")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def test_algorithm_registry():
    """Test algorithm registry includes road segmentation"""
    print("\n=== Testing Algorithm Registry Integration ===")
    
    try:
        from processing_executor import AlgorithmRegistry
        
        # Check if road segmentation is in registry
        algorithms = AlgorithmRegistry.SAFE_ALGORITHMS
        
        if 'segment_roads' in algorithms:
            road_algo = algorithms['segment_roads']
            print("✅ Road segmentation found in algorithm registry")
            print(f"   - Algorithm ID: {road_algo['algorithm_id']}")
            print(f"   - Description: {road_algo['description']}")
            print(f"   - Required params: {road_algo['required_params']}")
            print(f"   - Default confidence: {road_algo['param_defaults'].get('CONFIDENCE', 'N/A')}")
            return True
        else:
            print("❌ Road segmentation not found in algorithm registry")
            return False
            
    except Exception as e:
        print(f"❌ Registry test failed: {e}")
        return False

def run_comprehensive_test():
    """Run all tests in sequence"""
    print("🔬 GeoGenie Road Segmentation Comprehensive Test")
    print("=" * 60)
    
    results = []
    
    # Test 1: Model loading
    session = test_model_loading()
    results.append(("Model Loading", session is not False))
    
    # Test 2: Inference pipeline
    if session:
        prediction = test_inference_pipeline(session)
        results.append(("Inference Pipeline", prediction is not None))
    else:
        results.append(("Inference Pipeline", False))
    
    # Test 3: AI segmentation integration
    integration_ok = test_ai_segmentation_integration()
    results.append(("AI Segmentation Integration", integration_ok))
    
    # Test 4: Algorithm registry
    registry_ok = test_algorithm_registry()
    results.append(("Algorithm Registry", registry_ok))
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:<30} {status}")
        if success:
            passed += 1
    
    print(f"\nOverall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Road segmentation is ready for use.")
        print("\n📋 Next Steps:")
        print("   1. Test with actual satellite imagery in QGIS")
        print("   2. Validate natural language integration: 'Find roads in this image'")
        print("   3. Performance testing with large rasters")
    else:
        print("⚠️ Some tests failed. Review the output above for details.")
    
    return passed == total

# Example usage patterns for end users
def example_usage():
    """Show example usage patterns"""
    print("\n📖 EXAMPLE USAGE PATTERNS")
    print("=" * 40)
    print("In QGIS with GeoGenie loaded:")
    print()
    print("1. Natural Language:")
    print('   "Find roads in this satellite image"')
    print('   "Extract road network from Google Earth layer"')
    print('   "Show me all roads with high confidence"')
    print()
    print("2. Direct API:")
    print("   from geogenie_coordinator import GeoGenieCoordinator")
    print("   coordinator = GeoGenieCoordinator()")
    print("   coordinator.process_natural_language_request('Find roads in this image')")
    print()
    print("3. AI Module Direct:")
    print("   from ai_segmentation import FastAISegmentation")
    print("   ai_seg = FastAISegmentation()")
    print("   result = ai_seg.segment_features(raster_layer, 'roads', confidence=0.4)")

if __name__ == "__main__":
    print("This script should be run in QGIS Python console.")
    print("Usage:")
    print("exec(open('/path/to/test_road_segmentation.py').read())")
    print("run_comprehensive_test()")