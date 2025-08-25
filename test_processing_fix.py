#!/usr/bin/env python3
"""
Test script to verify the processing executor fixes work correctly
Run this in QGIS Python console after the fixes are applied
"""

import sys
import traceback

def test_processing_imports():
    """Test that all imports work correctly"""
    try:
        print("Testing imports...")
        
        # Test processing executor imports
        from processing_executor import ProcessingExecutor, ProcessingTask, AlgorithmRegistry
        print("✅ ProcessingExecutor imports successful")
        
        # Test QGIS task imports
        from qgis.core import QgsTask, QgsApplication, QgsProcessingContext
        print("✅ QGIS Task imports successful")
        
        # Test algorithm registry
        algorithms = AlgorithmRegistry.get_available_algorithms()
        print(f"✅ Available algorithms: {algorithms}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False

def test_processing_executor():
    """Test ProcessingExecutor creation"""
    try:
        print("\nTesting ProcessingExecutor creation...")
        
        from processing_executor import ProcessingExecutor
        
        # Create executor
        executor = ProcessingExecutor()
        print("✅ ProcessingExecutor created successfully")
        
        # Test task manager
        from qgis.core import QgsApplication
        task_manager = QgsApplication.taskManager()
        print(f"✅ Task manager available: {task_manager is not None}")
        
        return True
        
    except Exception as e:
        print(f"❌ ProcessingExecutor creation error: {e}")
        traceback.print_exc()
        return False

def test_buffer_parameters():
    """Test buffer algorithm parameter validation"""
    try:
        print("\nTesting buffer parameters...")
        
        from processing_executor import AlgorithmRegistry
        
        # Get buffer algorithm info
        buffer_info = AlgorithmRegistry.get_algorithm_info('buffer')
        if buffer_info:
            print("✅ Buffer algorithm info retrieved")
            print(f"   Required params: {buffer_info['required_params']}")
            print(f"   Optional params: {buffer_info['optional_params']}")
        else:
            print("❌ Buffer algorithm info not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Buffer parameter test error: {e}")
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all tests"""
    print("=== GeoGenie Processing Fix Tests ===")
    
    tests = [
        ("Import Tests", test_processing_imports),
        ("ProcessingExecutor Tests", test_processing_executor),
        ("Buffer Parameter Tests", test_buffer_parameters)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print(f"\n=== Test Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All tests passed! The fixes should work.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")

if __name__ == "__main__":
    run_all_tests()