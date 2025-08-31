GeoGenie AI Models Directory

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

Example models to try:
1. Building Segmentation:
   - Search for "building segmentation onnx" on Hugging Face
   - Models trained on aerial/satellite imagery
   - Typical input size: 512x512 or 1024x1024

2. Road Segmentation:
   - Search for "road detection onnx" or "road segmentation onnx"
   - Models trained on satellite/aerial data
   - Often use U-Net architecture

For testing without real models, GeoGenie will show an appropriate
error message and guide users to install models.