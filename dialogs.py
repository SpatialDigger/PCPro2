from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton, QFileDialog, QWidget, QAbstractItemView,
    QListWidget, QListWidgetItem, QLabel, QDialog, QFormLayout, QSpinBox, QCheckBox, QDialogButtonBox, QDoubleSpinBox,
    QLineEdit, QHBoxLayout, QSplitter, QTextEdit, QMenu, QInputDialog, QColorDialog)
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtGui import QAction, QContextMenuEvent

import open3d as o3d
import numpy as np

from scipy.spatial import ConvexHull
import numpy as np

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt

from PyQt6.QtCore import pyqtSignal

class SampleDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sample Pointcloud")

        layout = QVBoxLayout(self)

        # Sample type input (dropdown)
        self.sample_type_label = QLabel("Sample Type:", self)
        layout.addWidget(self.sample_type_label)

        self.sample_type_combobox = QComboBox(self)
        self.sample_type_combobox.addItems(["Random Sample", "Regular Sample", "Voxel Downsample"])
        self.sample_type_combobox.currentTextChanged.connect(self.update_visibility)
        layout.addWidget(self.sample_type_combobox)

        # Percentage input
        self.percentage_label = QLabel("Sample Percentage (%):", self)
        layout.addWidget(self.percentage_label)

        self.percentage_spinbox = QDoubleSpinBox(self)
        self.percentage_spinbox.setRange(0.01, 100.0)
        self.percentage_spinbox.setDecimals(2)  # Allow precision up to 2 decimal places
        self.percentage_spinbox.setValue(10)  # Default value
        layout.addWidget(self.percentage_spinbox)

        # Voxel size input
        self.voxel_size_label = QLabel("Voxel Size:", self)
        layout.addWidget(self.voxel_size_label)

        self.voxel_size_spinbox = QDoubleSpinBox(self)
        self.voxel_size_spinbox.setRange(0.01, 10.0)  # Adjust range as needed
        self.voxel_size_spinbox.setDecimals(2)  # Allow precision up to 2 decimal places
        self.voxel_size_spinbox.setValue(0.1)  # Default value
        layout.addWidget(self.voxel_size_spinbox)

        # Dialog buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                                        self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        # Set initial visibility
        self.update_visibility()

    def update_visibility(self):
        """Toggle visibility of input fields based on the selected sampling type."""
        sample_type = self.sample_type_combobox.currentText()
        if sample_type == "Voxel Downsample":
            self.percentage_label.hide()
            self.percentage_spinbox.hide()
            self.voxel_size_label.show()
            self.voxel_size_spinbox.show()
        else:  # "Random Sample" or "Regular Sample"
            self.percentage_label.show()
            self.percentage_spinbox.show()
            self.voxel_size_label.hide()
            self.voxel_size_spinbox.hide()

    def get_percentage(self):
        """Retrieve the percentage input."""
        return self.percentage_spinbox.value()

    def get_sample_type(self):
        """Retrieve the selected sampling type."""
        return self.sample_type_combobox.currentText()

    def get_voxel_size(self):
        """Retrieve the voxel size input."""
        return self.voxel_size_spinbox.value()



class HullFilterDialog(QDialog):
    def __init__(self, point_clouds, hulls, parent_names, parent=None):
        """
        Initialize the HullFilterDialog.

        :param point_clouds: List of PointCloud objects.
        :param hulls: List of Hull3D objects.
        :param parent_names: List of parent names from the tree or data structure.
        :param parent: Optional parent widget for the dialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Filter Points by Hull Footprint")

        # Store inputs
        self.point_clouds = point_clouds
        self.hulls = hulls
        self.parent_names = parent_names

        # Layout setup
        layout = QVBoxLayout(self)

        # PointCloud selection
        layout.addWidget(QLabel("Select PointCloud:"))
        self.pointcloud_combobox = QComboBox()
        self.pointcloud_combobox.addItems([pc for pc in parent_names])
        layout.addWidget(self.pointcloud_combobox)

        # Hull3D selection
        layout.addWidget(QLabel("Select Hull3D(s):"))
        self.hull_combobox = QComboBox()
        self.hull_combobox.addItems([hull.name for hull in hulls])
        layout.addWidget(self.hull_combobox)

        # Parent name selection
        layout.addWidget(QLabel("Select Parent Name for Filtered Data:"))
        self.parent_name_combobox = QComboBox()
        self.parent_name_combobox.addItems(parent_names)
        layout.addWidget(self.parent_name_combobox)

        # Overlap checkbox
        self.overlap_checkbox = QCheckBox("Filter by Hull Overlap (If multiple hulls are selected)")
        layout.addWidget(self.overlap_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.reset_button = QPushButton("Reset")
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.reset_button)
        layout.addLayout(button_layout)

        # Signals
        self.apply_button.clicked.connect(self.accept)
        self.reset_button.clicked.connect(self.reset_dialog)

    def reset_dialog(self):
        """
        Reset the dialog selections to their default values.
        """
        self.pointcloud_combobox.setCurrentIndex(0)
        self.hull_combobox.setCurrentIndex(0)
        self.parent_name_combobox.setCurrentIndex(0)
        self.overlap_checkbox.setChecked(False)

class ConvexhullDialog_old(QDialog):
    def __init__(self, parent=None, points=None):
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
        self.save_button = QPushButton("Convex Hull")
        self.cancel_button = QPushButton("Cancel")
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Connect buttons
        self.save_button.clicked.connect(self.calculate_2d_convex_hull)
        self.cancel_button.clicked.connect(self.reject)

        self.points = points


class ConvexhullDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sample Pointcloud")

        layout = QVBoxLayout(self)

        # Sample type input (dropdown)
        self.sample_type_label = QLabel("Sample Type:", self)
        layout.addWidget(self.sample_type_label)




        # Dialog buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                                        self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

