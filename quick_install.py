"""
GeoGenie Quick Dependencies Installer
====================================

Copy and paste this entire script into QGIS Python Console and press Enter.
This will install all required dependencies for GeoGenie.
"""

import sys, subprocess
packages = ['openai>=1.0.0', 'anthropic>=0.18.0', 'google-generativeai', 'requests']
print("🚀 Installing GeoGenie dependencies...")
for pkg in packages:
    print(f"📦 Installing {pkg}...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], check=True, capture_output=True)
        print(f"✅ {pkg} installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {pkg}: {e}")
print("🎉 Installation complete! Restart QGIS and try GeoGenie again.")