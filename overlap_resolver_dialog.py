from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
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
        
    def add_layer(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Shapefile", "", "Shapefiles (*.shp)")
            
        if file_path:
            layer = QgsVectorLayer(file_path, os.path.basename(file_path), "ogr")
            if layer.isValid():
                self.input_layers.append(layer)
                self.listLayers.addItem(layer.name())
            else:
                QMessageBox.warning(self, "Warning", "Invalid layer!")
                
    def remove_layer(self):
        current_row = self.listLayers.currentRow()
        if current_row >= 0:
            self.listLayers.takeItem(current_row)
            self.input_layers.pop(current_row)
            
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