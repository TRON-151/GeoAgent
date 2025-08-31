#!/usr/bin/env python3
"""
test_dependencies.py

Dependency checker for GeoGenie plugin.

This script checks if all required Python packages are installed and working
correctly. Run this to verify your GeoGenie installation.

Usage in QGIS Python console:
exec(open('/path/to/test_dependencies.py').read())

Author: Ahmad Abubakar Ahmad
Email: aabubaka@uni-muenster.de
Date: 2025-08-31
"""

import sys
import subprocess

print("=== GeoGenie Dependency Test ===")
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print()

# Test each package individually
for package_name in ['openai', 'anthropic']:
    print(f"Testing {package_name}...")
    try:
        if package_name == 'openai':
            import openai
            print(f"✅ {package_name}: {openai.__version__}")
        elif package_name == 'anthropic':
            import anthropic
            print(f"✅ {package_name}: {anthropic.__version__}")
    except ImportError as e:
        print(f"❌ {package_name}: {str(e)}")
        # Try to get more info
        try:
            result = subprocess.run([sys.executable, '-m', 'pip', 'show', package_name], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_line = [line for line in result.stdout.split('\n') if line.startswith('Version:')]
                if version_line:
                    print(f"   Pip shows: {version_line[0]}")
                location_line = [line for line in result.stdout.split('\n') if line.startswith('Location:')]
                if location_line:
                    print(f"   {location_line[0]}")
            else:
                print(f"   Not installed via pip")
                
            # Also try pip list
            result2 = subprocess.run([sys.executable, '-m', 'pip', 'list', '|', 'grep', package_name], 
                                   capture_output=True, text=True, timeout=10, shell=True)
            if result2.stdout.strip():
                print(f"   Pip list: {result2.stdout.strip()}")
        except Exception as ex:
            print(f"   Could not check pip status: {ex}")
    print()

print("=== Path Information ===")
print("sys.path contents:")
for i, path in enumerate(sys.path):
    print(f"  {i}: {path}")

print()
print("=== Installation Commands ===")
print("To install missing packages, run:")
print(f"{sys.executable} -m pip install openai>=1.0.0 anthropic>=0.18.0")