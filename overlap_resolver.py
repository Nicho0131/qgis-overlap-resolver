from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
                      QgsWkbTypes, QgsCoordinateReferenceSystem, QgsField, QgsFields,
                      QgsVectorFileWriter, QgsMessageLog)
from qgis.utils import iface
from datetime import datetime
import processing
import re
import os
from .overlap_resolver_dialog import OverlapResolverDialog
from .logger import PluginLogger

class OverlapResolver:
    def __init__(self, iface):
        self.iface = iface
        self.dlg = None
        self.input_layers = []
        self.datetime_fields = {}
        self.logger = PluginLogger("Overlap Resolver")
        self.datetime_formats = [
            # Standard ISO formats
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y%m%d%H%M%S",  # Compact ISO format
            "%Y%m%d%H%M",    # Compact ISO format without seconds
            
            # US formats
            "%m-%d-%Y %H:%M:%S",
            "%m-%d-%Y %H:%M",
            "%m-%d-%Y",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
            
            # European formats
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            
            # Surveying specific formats
            "%Y%m%d",        # YYYYMMDD (common in surveying)
            "%d%m%Y",        # DDMMYYYY
            "%m%d%Y",        # MMDDYYYY
            "%Y-%m-%dT%H:%M:%S",  # ISO 8601 with T separator
            "%Y-%m-%dT%H:%M",     # ISO 8601 with T separator (no seconds)
            
            # Civil engineering formats
            "%d-%b-%Y %H:%M:%S",  # DD-MMM-YYYY (e.g., 15-Jan-2024)
            "%d-%b-%Y %H:%M",     # DD-MMM-YYYY (no seconds)
            "%d-%b-%Y",           # DD-MMM-YYYY (date only)
            "%b-%d-%Y %H:%M:%S",  # MMM-DD-YYYY (e.g., Jan-15-2024)
            "%b-%d-%Y %H:%M",     # MMM-DD-YYYY (no seconds)
            "%b-%d-%Y",           # MMM-DD-YYYY (date only)
            
            # GPS/Survey formats
            "%Y-%j %H:%M:%S",     # Year-JulianDay (e.g., 2024-015)
            "%Y-%j %H:%M",        # Year-JulianDay (no seconds)
            "%Y-%j",              # Year-JulianDay (date only)
            
            # Common variations
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
            "%d.%m.%Y %H:%M:%S",  # European with dots
            "%d.%m.%Y %H:%M",     # European with dots (no seconds)
            "%d.%m.%Y",           # European with dots (date only)
            
            # 12-hour formats
            "%Y-%m-%d %I:%M:%S %p",  # 12-hour with AM/PM
            "%Y-%m-%d %I:%M %p",     # 12-hour with AM/PM (no seconds)
            "%m/%d/%Y %I:%M:%S %p",  # US 12-hour
            "%m/%d/%Y %I:%M %p",     # US 12-hour (no seconds)
            "%d/%m/%Y %I:%M:%S %p",  # European 12-hour
            "%d/%m/%Y %I:%M %p",     # European 12-hour (no seconds)
            
            # UTC formats
            "%Y-%m-%d %H:%M:%S UTC",
            "%Y-%m-%d %H:%M UTC",
            "%Y-%m-%dT%H:%M:%SZ",    # ISO 8601 with Z for UTC
            "%Y-%m-%dT%H:%MZ"        # ISO 8601 with Z for UTC (no seconds)
        ]
        
    def initGui(self):
        try:
            self.action = QAction("Overlap Resolver", self.iface.mainWindow())
            self.action.triggered.connect(self.run)
            self.iface.addToolBarIcon(self.action)
            self.iface.addPluginToMenu("Vector", self.action)
            self.logger.info("Plugin initialized successfully")
        except Exception as e:
            self.logger.critical(f"Error initializing plugin: {str(e)}")

    def unload(self):
        try:
            self.iface.removePluginMenu("Vector", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.logger.info("Plugin unloaded successfully")
        except Exception as e:
            self.logger.error(f"Error unloading plugin: {str(e)}")

    def run(self):
        try:
            if not self.dlg:
                self.dlg = OverlapResolverDialog()
            
            # Show the dialog
            self.dlg.show()
            result = self.dlg.exec_()
            
            if result:
                self.process_layers()
        except Exception as e:
            self.logger.critical(f"Error in run method: {str(e)}")

    def validate_layers(self):
        """Validate input layers for proper geometry type and CRS"""
        if not self.input_layers:
            return False, "No input layers selected"

        # Check if all layers are polygon layers
        for layer in self.input_layers:
            if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
                return False, f"Layer '{layer.name()}' is not a polygon layer"
            
            if not layer.isValid():
                return False, f"Layer '{layer.name()}' is not valid"

        # Check if all layers have the same CRS
        first_crs = self.input_layers[0].crs()
        for layer in self.input_layers[1:]:
            if layer.crs() != first_crs:
                return False, "All layers must have the same coordinate reference system"

        return True, ""

    def process_layers(self):
        try:
            # Get input layers from dialog
            self.input_layers = self.dlg.get_input_layers()
            self.logger.info(f"Processing {len(self.input_layers)} layers")
            
            # Validate layers
            is_valid, error_message = self.validate_layers()
            if not is_valid:
                self.logger.warning(error_message)
                QMessageBox.warning(None, "Warning", error_message)
                return

            # Detect datetime fields in all layers
            self.detect_datetime_fields()
            
            if not self.datetime_fields:
                self.logger.warning("No datetime fields found in any layer")
                QMessageBox.warning(None, "Warning", "No datetime fields found in any layer!")
                return

            # Create a temporary layer for overlaps
            overlap_layer = self.detect_overlaps()
            
            if not overlap_layer.isValid():
                self.logger.error("Failed to create overlap layer")
                QMessageBox.critical(None, "Error", "Failed to create overlap layer")
                return

            if overlap_layer.featureCount() == 0:
                self.logger.info("No overlaps found")
                QMessageBox.information(None, "Information", "No overlaps found!")
                return

            # Show overlaps to user
            QgsProject.instance().addMapLayer(overlap_layer)
            self.logger.info(f"Found {overlap_layer.featureCount()} overlapping features")
            
            # Ask for confirmation
            reply = QMessageBox.question(None, 'Confirm',
                                       'Overlaps detected. Would you like to resolve them?',
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.resolve_overlaps()
                
        except Exception as e:
            self.logger.critical(f"Error in process_layers: {str(e)}")
            self.logger.show_log_location()

    def detect_datetime_fields(self):
        """Automatically detect datetime fields in all layers"""
        self.datetime_fields = {}
        
        for layer in self.input_layers:
            try:
                layer_fields = {}
                self.logger.debug(f"Scanning layer '{layer.name()}' for datetime fields")
                
                for field in layer.fields():
                    field_name = field.name()
                    # Check if field name contains date/time related keywords
                    if any(keyword in field_name.lower() for keyword in ['date', 'time', 'dt', 'datetime', 'survey', 'gps', 'epoch']):
                        # Try to detect format from sample values
                        format = self.detect_datetime_format(layer, field_name)
                        if format:
                            layer_fields[field_name] = format
                            self.logger.debug(f"Found datetime field '{field_name}' with format '{format}'")
                
                if layer_fields:
                    self.datetime_fields[layer.id()] = layer_fields
                    self.logger.info(f"Found {len(layer_fields)} datetime fields in layer '{layer.name()}'")
                else:
                    # If no datetime fields found by name, try all fields
                    for field in layer.fields():
                        format = self.detect_datetime_format(layer, field.name())
                        if format:
                            layer_fields[field.name()] = format
                            self.logger.debug(f"Found datetime field '{field.name()}' with format '{format}'")
                    if layer_fields:
                        self.datetime_fields[layer.id()] = layer_fields
                        self.logger.info(f"Found {len(layer_fields)} datetime fields in layer '{layer.name()}'")
            except Exception as e:
                self.logger.error(f"Error detecting datetime fields in layer {layer.name()}: {str(e)}")

    def detect_datetime_format(self, layer, field_name):
        """Detect datetime format from field values"""
        try:
            # Get sample of values (up to 10 features)
            sample_values = []
            for feature in layer.getFeatures():
                value = feature[field_name]
                if value and isinstance(value, str):
                    # Clean the value (remove extra spaces, handle common variations)
                    value = value.strip()
                    # Handle UTC/Z suffixes
                    value = value.replace('Z', ' UTC').replace('z', ' UTC')
                    sample_values.append(value)
                if len(sample_values) >= 10:
                    break

            if not sample_values:
                return None

            # Try each format
            for fmt in self.datetime_formats:
                valid_count = 0
                for value in sample_values:
                    try:
                        datetime.strptime(value, fmt)
                        valid_count += 1
                    except ValueError:
                        continue
                
                # If more than 70% of samples match this format, use it
                if valid_count / len(sample_values) > 0.7:
                    self.logger.debug(f"Detected format '{fmt}' for field '{field_name}' with {valid_count}/{len(sample_values)} matches")
                    return fmt

            return None
        except Exception as e:
            self.logger.error(f"Error detecting datetime format for field {field_name}: {str(e)}")
            return None

    def detect_overlaps(self):
        """Detect overlapping areas between layers"""
        try:
            # Create a temporary layer for overlaps
            overlap_layer = QgsVectorLayer("Polygon?crs=" + self.input_layers[0].crs().authid(),
                                         "Overlaps", "memory")
            
            if not overlap_layer.isValid():
                raise Exception("Failed to create overlap layer")

            # Find overlaps between all input layers
            for i, layer1 in enumerate(self.input_layers):
                for layer2 in self.input_layers[i+1:]:
                    self.logger.debug(f"Checking overlaps between '{layer1.name()}' and '{layer2.name()}'")
                    # Use QGIS processing to find intersections
                    params = {
                        'INPUT': layer1,
                        'OVERLAY': layer2,
                        'OUTPUT': 'memory:'
                    }
                    result = processing.run("native:intersection", params)
                    intersection_layer = result['OUTPUT']
                    
                    if not intersection_layer.isValid():
                        self.logger.warning(f"Invalid intersection result between '{layer1.name()}' and '{layer2.name()}'")
                        continue

                    # Add features to overlap layer
                    overlap_layer.startEditing()
                    feature_count = 0
                    for feature in intersection_layer.getFeatures():
                        overlap_layer.addFeature(feature)
                        feature_count += 1
                    overlap_layer.commitChanges()
                    self.logger.debug(f"Found {feature_count} overlapping features between '{layer1.name()}' and '{layer2.name()}'")
            
            return overlap_layer
        except Exception as e:
            self.logger.critical(f"Error detecting overlaps: {str(e)}")
            raise

    def resolve_overlaps(self):
        """Resolve overlapping areas based on datetime values"""
        try:
            # Create output layer
            output_layer = QgsVectorLayer("Polygon?crs=" + self.input_layers[0].crs().authid(),
                                        "Resolved_Overlaps", "memory")
            
            if not output_layer.isValid():
                raise Exception("Failed to create output layer")

            # Process each feature
            for layer in self.input_layers:
                layer_fields = self.datetime_fields.get(layer.id(), {})
                if not layer_fields:
                    self.logger.warning(f"No datetime fields found in layer: {layer.name()}")
                    QMessageBox.warning(None, "Warning", 
                                      f"No datetime fields found in layer: {layer.name()}")
                    continue

                # Use the first detected datetime field
                datetime_field = next(iter(layer_fields))
                datetime_format = layer_fields[datetime_field]
                self.logger.info(f"Using datetime field '{datetime_field}' with format '{datetime_format}' for layer '{layer.name()}'")

                for feature in layer.getFeatures():
                    # Check if feature overlaps with any other feature
                    overlaps = self.find_overlapping_features(feature, layer)
                    
                    if not overlaps:
                        # No overlaps, add feature as is
                        output_layer.startEditing()
                        output_layer.addFeature(feature)
                        output_layer.commitChanges()
                    else:
                        # Compare datetime values
                        latest_feature = self.get_latest_feature(
                            [feature] + overlaps, 
                            datetime_field, 
                            datetime_format
                        )
                        output_layer.startEditing()
                        output_layer.addFeature(latest_feature)
                        output_layer.commitChanges()
            
            # Save output layer
            output_path = self.dlg.get_output_path()
            if not output_path:
                raise Exception("No output path specified")

            # Ensure the output directory exists
            output_dir = os.path.dirname(output_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                self.logger.debug(f"Created output directory: {output_dir}")

            # Save the layer
            save_result = QgsVectorFileWriter.writeAsVectorFormat(
                output_layer, 
                output_path,
                "UTF-8", 
                output_layer.crs(), 
                "ESRI Shapefile"
            )

            if save_result[0] != QgsVectorFileWriter.NoError:
                raise Exception(f"Error saving output file: {save_result[1]}")

            self.logger.info(f"Successfully saved output to: {output_path}")
            QMessageBox.information(None, "Success", "Overlaps resolved and saved successfully!")
            
        except Exception as e:
            self.logger.critical(f"Error resolving overlaps: {str(e)}")
            self.logger.show_log_location()

    def find_overlapping_features(self, feature, layer):
        """Find features that overlap with the given feature"""
        try:
            overlapping_features = []
            for other_feature in layer.getFeatures():
                if feature.id() != other_feature.id():
                    if feature.geometry().intersects(other_feature.geometry()):
                        overlapping_features.append(other_feature)
            return overlapping_features
        except Exception as e:
            self.logger.error(f"Error finding overlapping features: {str(e)}")
            return []

    def get_latest_feature(self, features, datetime_field, datetime_format):
        """Get the feature with the latest datetime value"""
        try:
            latest_feature = features[0]
            latest_time = self.parse_datetime(latest_feature[datetime_field], datetime_format)
            
            for feature in features[1:]:
                current_time = self.parse_datetime(feature[datetime_field], datetime_format)
                if current_time > latest_time:
                    latest_time = current_time
                    latest_feature = feature
            
            return latest_feature
        except Exception as e:
            self.logger.error(f"Error getting latest feature: {str(e)}")
            return features[0]  # Return first feature as fallback

    def parse_datetime(self, datetime_str, datetime_format):
        """Parse datetime string with error handling"""
        try:
            if not datetime_str:
                return datetime.min
                
            # Clean the value (remove extra spaces, handle common variations)
            datetime_str = datetime_str.strip()
            # Handle UTC/Z suffixes
            datetime_str = datetime_str.replace('Z', ' UTC').replace('z', ' UTC')
            return datetime.strptime(datetime_str, datetime_format)
        except Exception as e:
            self.logger.error(f"Error parsing datetime '{datetime_str}': {str(e)}")
            return datetime.min 