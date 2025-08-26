#!/usr/bin/env python3
"""
GeoGenie Dependencies Installer
===============================

This script installs all required dependencies for GeoGenie plugin.
Run this script in the QGIS Python Console for automatic installation.

Usage:
1. Open QGIS Python Console (Plugins > Python Console)
2. Copy and paste this entire script
3. Press Enter to execute

Dependencies to install:
- openai>=1.0.0
- anthropic>=0.18.0
- google-generativeai
- requests

Author: Ahmad Abubakar Ahmad
Date: 2025-08-25
"""

import sys
import subprocess
import os
from pathlib import Path

def install_package(package):
    """Install a package using pip"""
    try:
        print(f"📦 Installing {package}...")
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', package
        ], capture_output=True, text=True, check=True)
        
        print(f"✅ {package} installed successfully!")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}")
        print(f"   Error: {e.stderr.strip()}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error installing {package}: {str(e)}")
        return False

def check_package(package_name, import_name=None):
    """Check if a package is installed and importable"""
    if import_name is None:
        import_name = package_name.replace('-', '_')
    
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False

def main():
    """Main installation function"""
    print("🚀 GeoGenie Dependencies Installer")
    print("=" * 40)
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print()
    
    # Define packages to install
    packages = [
        ('openai', 'openai>=1.0.0'),
        ('anthropic', 'anthropic>=0.18.0'),
        ('google.generativeai', 'google-generativeai'),
        ('requests', 'requests')
    ]
    
    installed_count = 0
    total_count = len(packages)
    
    print("📋 Checking and installing dependencies...")
    print()
    
    for import_name, package_spec in packages:
        print(f"Checking {import_name}...")
        
        if check_package(import_name.split('.')[0], import_name):
            print(f"✅ {import_name} is already installed")
        else:
            print(f"⚠️  {import_name} not found, installing...")
            if install_package(package_spec):
                installed_count += 1
            else:
                print(f"❌ Failed to install {package_spec}")
        print()
    
    print("=" * 40)
    print("📊 Installation Summary:")
    print(f"   • Total packages checked: {total_count}")
    print(f"   • Packages installed: {installed_count}")
    
    # Final verification
    print()
    print("🔍 Final verification...")
    all_good = True
    for import_name, package_spec in packages:
        if check_package(import_name.split('.')[0], import_name):
            print(f"✅ {import_name}: OK")
        else:
            print(f"❌ {import_name}: FAILED")
            all_good = False
    
    print()
    if all_good:
        print("🎉 All dependencies installed successfully!")
        print("   You can now use GeoGenie plugin.")
    else:
        print("⚠️  Some dependencies failed to install.")
        print("   Please try manual installation:")
        for import_name, package_spec in packages:
            if not check_package(import_name.split('.')[0], import_name):
                print(f"   pip install {package_spec}")
    
    print("=" * 40)

if __name__ == "__main__":
    main()

# For QGIS Python Console execution
print("Running GeoGenie Dependencies Installer...")
main()