#!/usr/bin/env python3
"""
GeoGenie Phase 2 Integration Validation Script
"""

import os

def validate_integration():
    """Quick validation of key integration points"""
    print("🔍 GeoGenie Phase 2 - Ready for QGIS Testing")
    print("=" * 50)
    
    base_dir = os.path.dirname(__file__)
    
    # Check key files exist
    key_files = {
        "ai_segmentation.py": "AI segmentation module",
        "models/road_segmentation.onnx": "Road segmentation model",
        "test_road_segmentation.py": "Test script",
        "PHASE2_PROGRESS.md": "Progress documentation"
    }
    
    print("📁 File Structure Check:")
    all_present = True
    for file_path, description in key_files.items():
        full_path = os.path.join(base_dir, file_path)
        if os.path.exists(full_path):
            if file_path.endswith('.onnx'):
                size_mb = os.path.getsize(full_path) / (1024*1024)
                print(f"✅ {description}: {file_path} ({size_mb:.1f}MB)")
            else:
                print(f"✅ {description}: {file_path}")
        else:
            print(f"❌ {description}: {file_path} - NOT FOUND")
            all_present = False
    
    # Check algorithm registry integration
    print("\n🔧 Integration Points:")
    try:
        with open(os.path.join(base_dir, "processing_executor.py"), 'r') as f:
            executor_content = f.read()
        
        if 'segment_roads' in executor_content:
            print("✅ Road segmentation algorithm registered")
        else:
            print("❌ Road segmentation algorithm not found in registry")
            all_present = False
            
        with open(os.path.join(base_dir, "geogenie_coordinator.py"), 'r') as f:
            coordinator_content = f.read()
            
        if 'FastAISegmentation' in coordinator_content:
            print("✅ AI segmentation integrated in coordinator")
        else:
            print("❌ AI segmentation not integrated in coordinator")
            all_present = False
            
    except Exception as e:
        print(f"❌ Error checking integration: {e}")
        all_present = False
    
    # Summary
    print("\n" + "=" * 50)
    if all_present:
        print("🎉 VALIDATION PASSED - Ready for QGIS Testing!")
        print("\n📋 Next Steps:")
        print("1. Load GeoGenie plugin in QGIS")
        print("2. Install dependencies (onnxruntime, opencv-python, pillow)")
        print("3. Run test script in QGIS Python console:")
        print("   exec(open('test_road_segmentation.py').read())")
        print("   run_comprehensive_test()")
        print("4. Test natural language: 'Find roads in this satellite image'")
    else:
        print("❌ VALIDATION FAILED - Fix issues before QGIS testing")
    
    return all_present

if __name__ == "__main__":
    validate_integration()