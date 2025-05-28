import logging
import os
from datetime import datetime
from qgis.core import QgsMessageLog
from qgis.PyQt.QtWidgets import QMessageBox

class PluginLogger:
    def __init__(self, plugin_name):
        self.plugin_name = plugin_name
        self.logger = logging.getLogger(plugin_name)
        self.logger.setLevel(logging.DEBUG)
        
        # Create logs directory in user's home directory
        self.log_dir = os.path.join(os.path.expanduser('~'), 'qgis_plugin_logs')
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # Create log file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = os.path.join(self.log_dir, f'{plugin_name}_{timestamp}.log')
        
        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        
        # Log initial message
        self.logger.info(f"Plugin {plugin_name} started")
        
    def debug(self, message):
        """Log debug message"""
        self.logger.debug(message)
        QgsMessageLog.logMessage(message, self.plugin_name, QgsMessageLog.INFO)
        
    def info(self, message):
        """Log info message"""
        self.logger.info(message)
        QgsMessageLog.logMessage(message, self.plugin_name, QgsMessageLog.INFO)
        
    def warning(self, message):
        """Log warning message"""
        self.logger.warning(message)
        QgsMessageLog.logMessage(message, self.plugin_name, QgsMessageLog.WARNING)
        
    def error(self, message, show_dialog=False):
        """Log error message"""
        self.logger.error(message)
        QgsMessageLog.logMessage(message, self.plugin_name, QgsMessageLog.CRITICAL)
        if show_dialog:
            QMessageBox.critical(None, "Error", message)
            
    def critical(self, message, show_dialog=True):
        """Log critical message"""
        self.logger.critical(message)
        QgsMessageLog.logMessage(message, self.plugin_name, QgsMessageLog.CRITICAL)
        if show_dialog:
            QMessageBox.critical(None, "Critical Error", message)
            
    def get_log_file_path(self):
        """Get the path to the current log file"""
        return self.log_file
        
    def show_log_location(self):
        """Show a message box with the log file location"""
        QMessageBox.information(None, "Log File Location", 
                              f"Log file is located at:\n{self.log_file}") 