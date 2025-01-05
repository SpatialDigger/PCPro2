from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton, QFileDialog, QWidget, QAbstractItemView,
    QListWidget, QListWidgetItem, QLabel, QDialog, QFormLayout, QSpinBox, QCheckBox, QDialogButtonBox,
    QLineEdit, QHBoxLayout, QSplitter, QTextEdit, QMenu, QInputDialog, QColorDialog)
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtGui import QAction, QContextMenuEvent

import numpy as np

class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setGeometry(200, 200, 400, 300)

        # Example settings layout
        layout = QVBoxLayout()

        self.some_setting_label = QLabel("Some Setting:")
        self.some_setting_input = QLineEdit()
        layout.addWidget(self.some_setting_label)
        layout.addWidget(self.some_setting_input)

        # Add buttons
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Connect buttons
        self.save_button.clicked.connect(self.save_preferences)
        self.cancel_button.clicked.connect(self.reject)

    def save_preferences(self):
        # Logic to save preferences can go here
        print(f"Saved setting: {self.some_setting_input.text()}")
        self.accept()

class PropertiesDialog(QDialog):
    def __init__(self, point_cloud_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Point Cloud Properties")

        self.layout = QVBoxLayout()

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.layout.addWidget(self.text_area)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)
        self.layout.addWidget(self.button_box)

        self.setLayout(self.layout)

        self.fill_properties(point_cloud_data)

    def fill_properties(self, point_cloud_data):
        point_cloud = point_cloud_data["point_cloud"]
        transform_settings = point_cloud_data["transform_settings"]

        point_count = len(np.asarray(point_cloud.points))
        bbox = point_cloud.get_axis_aligned_bounding_box()
        bounding_box = bbox.get_extent()

        level = point_cloud_data.get("level", "None")

            # transform_info = f"Translation (X, Y, Z): {transform_settings['x_digits']}, {transform_settings['y_digits']}, {transform_settings['localize_z']}"
        point_cloud_info = f"Point Cloud File: {point_cloud_data['file_name']}\n"
        point_cloud_info += f"Point Count: {point_count}\n"
        point_cloud_info += f"Bounding Box Extents: X: {bounding_box[0]:.2f}, Y: {bounding_box[1]:.2f}, Z: {bounding_box[2]:.2f}\n"
        point_cloud_info += f"Original Location: {point_cloud_data['file_path']}\n"
        point_cloud_info += f"Assigned Level: {level}\n"
        if all(key in transform_settings for key in ['x_digits', 'y_digits', 'localize_z']):
            transform_info = f"Translation (X, Y, Z): {transform_settings['x_digits']}, {transform_settings['y_digits']}, {transform_settings['localize_z']}"
            point_cloud_info += f"Transform Settings: {transform_info}"

        self.text_area.setText(point_cloud_info)

class LogWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Event Log")
        self.setGeometry(200, 200, 600, 400)

        self.layout = QVBoxLayout()

        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.layout.addWidget(self.log_text_edit)

        self.clear_button = QPushButton("Clear Log")
        self.clear_button.clicked.connect(self.clear_log)
        self.layout.addWidget(self.clear_button)

        self.setLayout(self.layout)

    def add_message(self, message):
        self.log_text_edit.append(message)

    def clear_log(self):
        self.log_text_edit.clear()