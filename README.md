# QGIS Overlap Resolver Plugin

A QGIS plugin for resolving overlapping polygons in shapefiles, with support for datetime-based resolution and user-defined priorities.

## Features

- Detect overlaps between multiple shapefile layers
- Resolve overlaps based on:
  - Datetime values (keeps the most recent data)
  - Layer priorities (user-defined order)
- Handles survey progression and subdivisions
- Preserves unchanged areas between surveys
- Automatic datetime field detection
- Support for multiple datetime formats

## Installation

### From QGIS Plugin Manager
1. Open QGIS
2. Go to Plugins > Manage and Install Plugins
3. Search for "Overlap Resolver"
4. Click Install

### Manual Installation
1. Download the latest release from the [Releases](https://github.com/yourusername/qgis-overlap-resolver/releases) page
2. Extract the ZIP file
3. Copy the `overlap_resolver` folder to your QGIS plugins directory:
   - Windows: `C:\Users\<username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
4. Restart QGIS
5. Enable the plugin in Plugins > Manage and Install Plugins

## Usage

1. Open QGIS and load your shapefile layers
2. Go to Vector > Overlap Resolver
3. Add your layers using the "Add Layer" button
4. Choose resolution method:
   - Datetime: Select the date column for each layer
   - Priority: Set layer priorities using drag and drop
5. Set output path
6. Click OK to process

### Resolution Methods

#### Datetime-based Resolution
- Automatically detects datetime fields in your layers
- Keeps the most recent survey data
- Preserves unchanged areas
- Handles subdivisions appropriately

#### Priority-based Resolution
- Set layer priorities using drag and drop
- Higher priority layers override lower priority ones
- Maintains survey progression
- Preserves unchanged areas

## Requirements

- QGIS 3.x
- Python 3.x

## Development

### Building from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/qgis-overlap-resolver.git
   ```
2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Make your changes
4. Test the plugin in QGIS

### Project Structure
```
overlap_resolver/
├── overlap_resolver.py          # Main plugin code
├── overlap_resolver_dialog.py   # Plugin dialog
├── overlap_resolver_dialog.ui   # Qt Designer UI file
├── logger.py                    # Logging functionality
├── resources.py                 # Compiled resources
├── resources.qrc               # Resource definitions
└── metadata.txt                # Plugin metadata
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

If you encounter any issues or have questions, please:
1. Check the [documentation](docs/)
2. Search [existing issues](https://github.com/yourusername/qgis-overlap-resolver/issues)
3. Create a new issue if needed

## Acknowledgments

- QGIS Development Team
- All contributors and users of this plugin 