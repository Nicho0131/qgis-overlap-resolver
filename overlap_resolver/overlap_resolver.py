from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QProgressDialog
from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
                      QgsWkbTypes, QgsCoordinateReferenceSystem, QgsField, QgsFields,
                      QgsVectorFileWriter, QgsMessageLog, QgsSpatialIndex)
from qgis.utils import iface
from datetime import datetime
import processing
import re
import os
from .overlap_resolver_dialog import OverlapResolverDialog
from .logger import PluginLogger
from multiprocessing import Pool, cpu_count
from functools import partial
import math

class OverlapResolver:
    def __init__(self, iface):
        self.iface = iface
        self.dlg = None
        self.input_layers = []
        self.datetime_fields = {}
        self.logger = PluginLogger("Overlap Resolver")
        self.progress_dialog = None
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
            # Create the action
            self.action = QAction("Overlap Resolver", self.iface.mainWindow())
            self.action.triggered.connect(self.run)
            
            # Add to Vector menu
            self.iface.addPluginToVectorMenu("&Vector", self.action)
            
            # Add to toolbar
            self.iface.addToolBarIcon(self.action)
            
            self.logger.info("Plugin initialized successfully")
        except Exception as e:
            self.logger.critical(f"Error initializing plugin: {str(e)}")

    def unload(self):
        try:
            # Remove from Vector menu
            self.iface.removePluginVectorMenu("&Vector", self.action)
            
            # Remove from toolbar
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

            # Fix invalid geometries
            self.fix_invalid_geometries()

            # Get resolution method
            resolution_method = self.dlg.get_resolution_method()
            
            if resolution_method == "datetime":
                # Detect datetime fields in all layers
                self.detect_datetime_fields()
                
                if not self.datetime_fields:
                    self.logger.warning("No datetime fields found in any layer")
                    QMessageBox.warning(None, "Warning", "No datetime fields found in any layer!")
                    return

            # Create a temporary layer for overlaps
            overlap_layer = self.detect_overlaps()
            
            # Check if operation was cancelled
            if overlap_layer is None:
                self.logger.info("Operation cancelled by user")
                return

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

    def fix_invalid_geometries(self):
        """Fix invalid geometries in input layers"""
        try:
            for i, layer in enumerate(self.input_layers):
                # Check if layer has invalid geometries
                params = {
                    'INPUT': layer,
                    'METHOD': 0,  # 0 = fix geometries
                    'OUTPUT': 'memory:'
                }
                result = processing.run("native:fixgeometries", params)
                fixed_layer = result['OUTPUT']
                
                if fixed_layer.isValid():
                    self.input_layers[i] = fixed_layer
                    self.logger.info(f"Fixed geometries in layer: {layer.name()}")
                else:
                    self.logger.warning(f"Failed to fix geometries in layer: {layer.name()}")
        except Exception as e:
            self.logger.error(f"Error fixing geometries: {str(e)}")

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

    def create_progress_dialog(self, title, label, maximum):
        """Create and return a progress dialog"""
        progress = QProgressDialog(label, "Cancel", 0, maximum, self.iface.mainWindow())
        progress.setWindowTitle(title)
        progress.setWindowModality(2)  # WindowModal
        progress.setMinimumDuration(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        return progress

    def process_feature_batch(self, batch_data):
        """Process a batch of features in parallel"""
        layer1_id, feature1_id, feature1_geom_wkt, spatial_indices_data, other_layers_data = batch_data
        results = []
        
        # Convert WKT back to geometry
        feature1_geom = QgsGeometry.fromWkt(feature1_geom_wkt)
        feature1_bbox = feature1_geom.boundingBox()
        
        # Recreate spatial indices
        spatial_indices = {}
        for layer_id, index_data in spatial_indices_data.items():
            index = QgsSpatialIndex()
            for bbox in index_data:
                index.insertFeature(QgsFeature(bbox['id']), bbox['bbox'])
            spatial_indices[layer_id] = index
        
        for layer2_data in other_layers_data:
            layer2_id = layer2_data['id']
            potential_overlaps = spatial_indices[layer2_id].intersects(feature1_bbox)
            
            for fid in potential_overlaps:
                # Skip same feature
                if f"{layer1_id}_{feature1_id}" == f"{layer2_id}_{fid}":
                    continue
                
                # Get feature2 geometry from the data
                feature2_geom = QgsGeometry.fromWkt(layer2_data['features'][fid])
                
                if feature1_geom.intersects(feature2_geom):
                    intersection = feature1_geom.intersection(feature2_geom)
                    
                    if not intersection.isEmpty():
                        intersection_area = intersection.area()
                        feature2_area = feature2_geom.area()
                        
                        results.append({
                            'feature1_id': f"{layer1_id}_{feature1_id}",
                            'feature2_id': f"{layer2_id}_{fid}",
                            'layer2_id': layer2_id,
                            'intersection_wkt': intersection.asWkt(),
                            'intersection_area': intersection_area,
                            'feature2_area': feature2_area,
                            'is_subdivision': intersection_area > 0.95 * feature2_area
                        })
        
        return results

    def detect_overlaps(self):
        """Detect overlapping areas between layers, considering survey progression"""
        try:
            # Create a temporary layer for overlaps
            overlap_layer = QgsVectorLayer("Polygon?crs=" + self.input_layers[0].crs().authid(),
                                         "Overlaps", "memory")
            
            if not overlap_layer.isValid():
                raise Exception("Failed to create overlap layer")

            # Dictionary to store overlapping features and their relationships
            self.overlapping_features = {}
            self.feature_areas = {}

            # First pass: calculate areas and create spatial indices
            total_features = sum(layer.featureCount() for layer in self.input_layers)
            processed_features = 0
            
            progress = self.create_progress_dialog(
                "Processing Features",
                "Creating spatial indices...",
                total_features
            )

            # Create spatial indices for each layer
            spatial_indices = {}
            layer_data = {}
            
            for layer in self.input_layers:
                # Create spatial index
                index = QgsSpatialIndex()
                layer_data[layer.id()] = {
                    'id': layer.id(),
                    'crs': layer.crs().authid(),
                    'features': {}
                }
                
                # Add features to spatial index and store data
                for feature in layer.getFeatures():
                    # Add to spatial index
                    index.insertFeature(feature)
                    
                    # Store feature data
                    feature_id = f"{layer.id()}_{feature.id()}"
                    self.overlapping_features[feature_id] = []
                    self.feature_areas[feature_id] = feature.geometry().area()
                    
                    # Store feature data for processing
                    layer_data[layer.id()]['features'][feature.id()] = {
                        'id': feature.id(),
                        'geometry': feature.geometry(),
                        'attributes': feature.attributes()
                    }
                    
                    processed_features += 1
                    progress.setValue(processed_features)
                    
                    if progress.wasCanceled():
                        progress.close()
                        return None
                
                spatial_indices[layer.id()] = index

            # Second pass: detect overlaps using spatial indices
            processed_features = 0
            all_results = []
            
            progress = self.create_progress_dialog(
                "Detecting Overlaps",
                "Processing features...",
                total_features
            )

            # Process each layer
            for layer1_id, layer1_data in layer_data.items():
                index1 = spatial_indices[layer1_id]
                
                # Process each feature in the layer
                for feature1_id, feature1_data in layer1_data['features'].items():
                    feature1_geom = feature1_data['geometry']
                    feature1_bbox = feature1_geom.boundingBox()
                    
                    # Get potential overlapping features using spatial index
                    for layer2_id, layer2_data in layer_data.items():
                        index2 = spatial_indices[layer2_id]
                        
                        # Get potential overlaps from spatial index
                        potential_overlaps = index2.intersects(feature1_bbox)
                        
                        for fid in potential_overlaps:
                            # Skip same feature
                            if f"{layer1_id}_{feature1_id}" == f"{layer2_id}_{fid}":
                                continue
                            
                            feature2_data = layer2_data['features'][fid]
                            feature2_geom = feature2_data['geometry']
                            
                            # Quick check using bounding boxes
                            if feature1_bbox.intersects(feature2_geom.boundingBox()):
                                # Detailed check using actual geometries
                                if feature1_geom.intersects(feature2_geom):
                                    intersection = feature1_geom.intersection(feature2_geom)
                                    
                                    if not intersection.isEmpty():
                                        intersection_area = intersection.area()
                                        feature2_area = feature2_geom.area()
                                        
                                        # Only process if the intersection is significant
                                        if intersection_area > 0.0001:  # Minimum area threshold
                                            all_results.append({
                                                'feature1_id': f"{layer1_id}_{feature1_id}",
                                                'feature2_id': f"{layer2_id}_{fid}",
                                                'layer2_id': layer2_id,
                                                'intersection': intersection,
                                                'intersection_area': intersection_area,
                                                'feature2_area': feature2_area,
                                                'is_subdivision': intersection_area > 0.95 * feature2_area
                                            })
                    
                    processed_features += 1
                    progress.setValue(processed_features)
                    
                    if progress.wasCanceled():
                        progress.close()
                        return None

            # Process results in batches
            batch_size = 100
            for i in range(0, len(all_results), batch_size):
                batch = all_results[i:i + batch_size]
                
                overlap_layer.startEditing()
                for result in batch:
                    feature1_id = result['feature1_id']
                    feature2_id = result['feature2_id']
                    
                    # Find the actual layer and feature objects
                    layer2 = next(layer for layer in self.input_layers if layer.id() == result['layer2_id'])
                    
                    # Handle both numeric and hexadecimal feature IDs
                    try:
                        # Try to convert to integer first
                        feature2_fid = int(feature2_id.split('_')[1])
                    except ValueError:
                        # If that fails, use the ID as is
                        feature2_fid = feature2_id.split('_')[1]
                    
                    feature2 = layer2.getFeature(feature2_fid)
                    
                    self.overlapping_features[feature1_id].append({
                        'layer': layer2,
                        'feature': feature2,
                        'intersection_area': result['intersection_area'],
                        'feature_area': result['feature2_area'],
                        'is_subdivision': result['is_subdivision']
                    })
                    
                    # Add to overlap layer
                    overlap_feature = QgsFeature()
                    overlap_feature.setGeometry(result['intersection'])
                    overlap_layer.addFeature(overlap_feature)
                
                overlap_layer.commitChanges()

            return overlap_layer
        except Exception as e:
            self.logger.critical(f"Error detecting overlaps: {str(e)}")
            raise

    def resolve_overlaps(self):
        """Resolve overlapping areas based on selected method"""
        try:
            # Create output layer
            output_layer = QgsVectorLayer("Polygon?crs=" + self.input_layers[0].crs().authid(),
                                        "Resolved_Overlaps", "memory")
            
            if not output_layer.isValid():
                raise Exception("Failed to create output layer")

            resolution_method = self.dlg.get_resolution_method()
            
            # Process in batches
            batch_size = 100
            total_features = sum(layer.featureCount() for layer in self.input_layers)
            processed_features = 0
            
            progress = self.create_progress_dialog(
                "Resolving Overlaps",
                "Processing features...",
                total_features
            )

            # First, create a layer to store all areas that should be removed
            areas_to_remove = QgsVectorLayer("Polygon?crs=" + self.input_layers[0].crs().authid(),
                                           "Areas_To_Remove", "memory")
            
            if not areas_to_remove.isValid():
                raise Exception("Failed to create areas to remove layer")

            # Process layers based on priority
            if resolution_method == "datetime":
                self.prepare_areas_to_remove_by_datetime(areas_to_remove, batch_size, total_features, processed_features, progress)
            else:
                self.prepare_areas_to_remove_by_priority(areas_to_remove, batch_size, total_features, processed_features, progress)
            
            if progress.wasCanceled():
                return

            # Now process each layer and remove the overlapping areas
            progress = self.create_progress_dialog(
                "Creating Final Layer",
                "Removing overlaps and merging features...",
                total_features
            )

            for layer in self.input_layers:
                features = list(layer.getFeatures())
                for feature in features:
                    # Get the feature's geometry
                    geom = feature.geometry()
                    
                    # Remove any areas that overlap with higher priority features
                    if not geom.isEmpty():
                        # Create a difference geometry by removing all overlapping areas
                        diff_geom = geom
                        for area_feature in areas_to_remove.getFeatures():
                            diff_geom = diff_geom.difference(area_feature.geometry())
                        
                        # Only add the feature if it still has geometry after removing overlaps
                        if not diff_geom.isEmpty():
                            new_feature = QgsFeature()
                            new_feature.setGeometry(diff_geom)
                            new_feature.setAttributes(feature.attributes())
                            output_layer.startEditing()
                            output_layer.addFeature(new_feature)
                            output_layer.commitChanges()
                    
                    processed_features += 1
                    progress.setValue(processed_features)
                    
                    if progress.wasCanceled():
                        return

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

    def prepare_areas_to_remove_by_datetime(self, areas_to_remove, batch_size, total_features, processed_features, progress):
        """Prepare areas to remove based on datetime values"""
        try:
            # Sort layers by datetime (newest first)
            sorted_layers = []
            for layer in self.input_layers:
                layer_fields = self.datetime_fields.get(layer.id(), {})
                if layer_fields:
                    datetime_field = next(iter(layer_fields))
                    datetime_format = layer_fields[datetime_field]
                    # Get the most recent datetime in the layer
                    latest_time = datetime.min
                    for feature in layer.getFeatures():
                        current_time = self.parse_datetime(feature[datetime_field], datetime_format)
                        if current_time > latest_time:
                            latest_time = current_time
                    sorted_layers.append((layer, latest_time))
                else:
                    # If no datetime field, treat as oldest
                    sorted_layers.append((layer, datetime.min))
            
            sorted_layers.sort(key=lambda x: x[1], reverse=True)
            
            # Process each layer in order of datetime
            for i, (layer, _) in enumerate(sorted_layers):
                # Skip the first (newest) layer as it has highest priority
                if i == 0:
                    continue
                
                # Get all features from higher priority layers
                higher_priority_geoms = []
                for higher_layer, _ in sorted_layers[:i]:
                    for feature in higher_layer.getFeatures():
                        higher_priority_geoms.append(feature.geometry())
                
                # For each feature in current layer
                for feature in layer.getFeatures():
                    geom = feature.geometry()
                    
                    # Find intersections with higher priority features
                    for higher_geom in higher_priority_geoms:
                        if geom.intersects(higher_geom):
                            intersection = geom.intersection(higher_geom)
                            if not intersection.isEmpty():
                                # Add intersection to areas to remove
                                remove_feature = QgsFeature()
                                remove_feature.setGeometry(intersection)
                                areas_to_remove.startEditing()
                                areas_to_remove.addFeature(remove_feature)
                                areas_to_remove.commitChanges()
                    
                    processed_features += 1
                    progress.setValue(processed_features)
                    
                    if progress.wasCanceled():
                        return
                        
        except Exception as e:
            self.logger.error(f"Error in prepare_areas_to_remove_by_datetime: {str(e)}")
            raise

    def prepare_areas_to_remove_by_priority(self, areas_to_remove, batch_size, total_features, processed_features, progress):
        """Prepare areas to remove based on layer priorities"""
        try:
            priorities = self.dlg.get_layer_priorities()
            
            # Sort layers by priority
            sorted_layers = sorted(self.input_layers, 
                                 key=lambda layer: priorities.get(layer.id(), float('inf')))
            
            # Process each layer in order of priority
            for i, layer in enumerate(sorted_layers):
                # Skip the first (highest priority) layer
                if i == 0:
                    continue
                
                # Get all features from higher priority layers
                higher_priority_geoms = []
                for higher_layer in sorted_layers[:i]:
                    for feature in higher_layer.getFeatures():
                        higher_priority_geoms.append(feature.geometry())
                
                # For each feature in current layer
                for feature in layer.getFeatures():
                    geom = feature.geometry()
                    
                    # Find intersections with higher priority features
                    for higher_geom in higher_priority_geoms:
                        if geom.intersects(higher_geom):
                            intersection = geom.intersection(higher_geom)
                            if not intersection.isEmpty():
                                # Add intersection to areas to remove
                                remove_feature = QgsFeature()
                                remove_feature.setGeometry(intersection)
                                areas_to_remove.startEditing()
                                areas_to_remove.addFeature(remove_feature)
                                areas_to_remove.commitChanges()
                    
                    processed_features += 1
                    progress.setValue(processed_features)
                    
                    if progress.wasCanceled():
                        return
                        
        except Exception as e:
            self.logger.error(f"Error in prepare_areas_to_remove_by_priority: {str(e)}")
            raise

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