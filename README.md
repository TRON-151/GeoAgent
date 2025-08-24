# GeoGenie

GeoGenie is a QGIS plugin that provides natural language processing for geospatial analysis using OpenAI GPT and Anthropic Claude models.

**Phase 1 Features:**
- Natural language to QGIS processing workflow
- Support for buffer, clip, reproject, dissolve, and intersection algorithms
- Parameter validation and user confirmation dialogs
- Real-time progress feedback
- Memory layer creation for algorithm outputs

## Installation

### Dependencies

GeoGenie requires only two essential packages:

```bash
pip install openai>=1.0.0
pip install anthropic>=0.18.0
```

### QGIS Installation

1. Download the plugin and place it in your QGIS plugins directory
2. Enable the plugin in QGIS Plugin Manager
3. The plugin will automatically prompt to install missing dependencies

### macOS + QGIS 3

In a macOS shell window, run:

```bash
/Applications/QGIS.app/Contents/MacOS/bin/python3 -m pip install openai>=1.0.0 anthropic>=0.18.0
```

## Usage

1. Launch the GeoGenie plugin from the QGIS toolbar
2. Enter your OpenAI or Claude API key
3. Type natural language requests like:
   - "Create a 100 meter buffer around the schools layer"
   - "Clip the buildings layer with the city boundary"
   - "Reproject the roads layer to EPSG:4326"

The plugin will interpret your request, validate parameters, and execute the corresponding QGIS processing algorithm.

## API Keys

- OpenAI API key: Get from https://platform.openai.com/account/api-keys
- Claude API key: Get from https://console.anthropic.com/

API keys are stored locally and encrypted for security.