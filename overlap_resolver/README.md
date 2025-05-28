# QGIS Overlap Resolver Plugin

This QGIS plugin helps resolve overlapping polygons in multiple shapefiles by keeping the most recent features based on datetime attributes.

## Features

- Load multiple polygon shapefiles
- Detect and visualize overlapping areas
- Resolve overlaps based on datetime attributes
- Export resolved shapefile with user-defined parameters

## Requirements

- QGIS 3.0 or later
- No additional Python packages required
- No virtual environment needed

### Note on Dependencies
This plugin uses QGIS's built-in Python environment and modules. All required dependencies (`qgis`, `PyQt5`, `processing`) come bundled with QGIS installation. You don't need to install any additional Python packages or set up a virtual environment.

## Installation

1. Download the plugin files
2. Create a new directory in your QGIS plugins folder:
   - Windows: `C:\Users\<username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\overlap_resolver`
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/overlap_resolver`
   - macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/overlap_resolver`
3. Copy all plugin files to this directory
4. Restart QGIS
5. Enable the plugin in QGIS Plugin Manager

## Usage

1. Click the "Overlap Resolver" button in the Vector toolbar
2. Add input shapefiles using the "Add Layer" button
3. Select the datetime field to use for resolving overlaps
4. Choose an output location and filename
5. Click OK to process
6. Review the detected overlaps
7. Confirm to resolve overlaps and save the result

## Development

### Development Environment
- QGIS 3.0 or later
- Python 3.x (comes with QGIS)
- PyQt5 (comes with QGIS)

### Building from Source
1. Clone the repository
2. Copy the files to your QGIS plugins directory
3. Restart QGIS
4. Enable the plugin in QGIS Plugin Manager

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 