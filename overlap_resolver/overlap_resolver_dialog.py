from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox, QRadioButton, QVBoxLayout, QWidget, QLabel, QListWidget
from qgis.core import QgsProject, QgsVectorLayer
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'overlap_resolver_dialog.ui'))

class OverlapResolverDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(OverlapResolverDialog, self).__init__(parent)
        self.setupUi(self)
        
        # Connect signals
        self.btnAddLayer.clicked.connect(self.add_layer)
        self.btnRemoveLayer.clicked.connect(self.remove_layer)
        self.btnBrowseOutput.clicked.connect(self.browse_output)
        
        # Initialize lists
        self.input_layers = []
        self.output_path = None
        
        # Add resolution method selection
        self.resolution_method = "datetime"  # Default to datetime
        self.radioDatetime = QRadioButton("Resolve by DateTime")
        self.radioPriority = QRadioButton("Resolve by Layer Priority")
        self.radioDatetime.setChecked(True)
        
        # Add layer priority list
        self.labelPriority = QLabel("Layer Priority (drag to reorder):")
        self.listPriority = QListWidget()
        self.listPriority.setDragDropMode(QListWidget.InternalMove)
        
        # Add widgets to layout
        layout = self.layout()
        layout.addWidget(self.radioDatetime)
        layout.addWidget(self.radioPriority)
        layout.addWidget(self.labelPriority)
        layout.addWidget(self.listPriority)
        
        # Connect radio buttons
        self.radioDatetime.toggled.connect(self.on_resolution_method_changed)
        self.radioPriority.toggled.connect(self.on_resolution_method_changed)
        
    def on_resolution_method_changed(self):
        if self.radioDatetime.isChecked():
            self.resolution_method = "datetime"
            self.labelPriority.setVisible(False)
            self.listPriority.setVisible(False)
        else:
            self.resolution_method = "priority"
            self.labelPriority.setVisible(True)
            self.listPriority.setVisible(True)
            self.update_priority_list()
            
    def update_priority_list(self):
        self.listPriority.clear()
        for layer in self.input_layers:
            self.listPriority.addItem(layer.name())
            
    def add_layer(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Shapefile", "", "Shapefiles (*.shp)")
            
        if file_path:
            layer = QgsVectorLayer(file_path, os.path.basename(file_path), "ogr")
            if layer.isValid():
                self.input_layers.append(layer)
                self.listLayers.addItem(layer.name())
                if self.resolution_method == "priority":
                    self.listPriority.addItem(layer.name())
            else:
                QMessageBox.warning(self, "Warning", "Invalid layer!")
                
    def remove_layer(self):
        current_row = self.listLayers.currentRow()
        if current_row >= 0:
            self.listLayers.takeItem(current_row)
            self.input_layers.pop(current_row)
            if self.resolution_method == "priority":
                self.listPriority.takeItem(current_row)
            
    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output", "", "Shapefiles (*.shp)")
            
        if file_path:
            self.output_path = file_path
            self.txtOutputPath.setText(file_path)
            
    def get_input_layers(self):
        return self.input_layers
        
    def get_output_path(self):
        return self.output_path
        
    def get_resolution_method(self):
        return self.resolution_method
        
    def get_layer_priorities(self):
        priorities = {}
        for i in range(self.listPriority.count()):
            layer_name = self.listPriority.item(i).text()
            for layer in self.input_layers:
                if layer.name() == layer_name:
                    priorities[layer.id()] = i
                    break
        return priorities 