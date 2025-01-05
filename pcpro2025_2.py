import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QMenuBar, QFileDialog
)

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QSpinBox, QLabel, QDialogButtonBox, QDoubleSpinBox

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QContextMenuEvent
import open3d as o3d
import warnings

import random
import laspy

warnings.filterwarnings("ignore", category=DeprecationWarning)

from helpers import PreferencesDialog, LogWindow, PropertiesDialog
from filters import SampleDialog

import numpy as np


class Open3DViewer:
    def __init__(self, logger=None):
        self.vis = o3d.visualization.Visualizer()
        self.window_width = 800
        self.window_height = 600
        self.vis.create_window(width=self.window_width, height=self.window_height)
        self.view_control = self.vis.get_view_control()
        self.point_clouds = {}
        self.logger = logger
        self.visible_point_clouds = {}  # Track visible point clouds

    def log_message(self, message):
        if self.logger:
            self.logger(message)

    def add_pointcloud(self, point_cloud, parent_name, child_name):
        """Add point cloud to viewer and track it."""
        self.vis.add_geometry(point_cloud)
        self.point_clouds[(parent_name, child_name)] = point_cloud
        self.visible_point_clouds[(parent_name, child_name)] = True  # Mark as visible by default

    def toggle_pointcloud_visibility(self, parent_name, child_name, is_visible):
        """Toggle the visibility of the point cloud."""
        key = (parent_name, child_name)

        # Only toggle if visibility is different from current state
        if self.visible_point_clouds.get(key) != is_visible:
            point_cloud = self.point_clouds.get(key)
            if point_cloud:
                if is_visible:
                    self.vis.add_geometry(point_cloud)  # Add geometry if it's visible
                else:
                    self.vis.remove_geometry(point_cloud)  # Remove geometry if it's not visible
                self.visible_point_clouds[key] = is_visible  # Update visibility state

        self.update_viewer()

    def update_viewer(self):
        """Update the Open3D viewer."""
        self.vis.poll_events()
        self.vis.update_renderer()

    def close(self):
        """Close the Open3D viewer window."""
        self.vis.destroy_window()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pointcloud Viewer")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Dataset"])
        self.tree.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.tree)
        self.data = {}
        self.o3d_viewer = Open3DViewer(logger=self.add_log_message)
        self.log_window = LogWindow(self)
        self.create_menu_bar()
        self.viewer_update_timer = QTimer()
        self.viewer_update_timer.timeout.connect(self.o3d_viewer.update_viewer)
        self.viewer_update_timer.start(16)

    def add_pointcloud(self, file_path, transform_settings=None):
        try:
            # Import the point cloud data
            data = self.import_pointcloud(file_path, transform_settings)
            file_name = data["file_name"]

            if file_name not in self.data:
                # If the dataset is not already in self.data, add it
                self.data[file_name] = {
                    "Pointcloud": data["Pointcloud"],
                    "transform_settings": transform_settings,
                    "file_path": file_path,
                    "file_name": file_name,
                }

                # Create a new parent item for the tree
                parent_item = QTreeWidgetItem([file_name])
                parent_item.setFlags(parent_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                parent_item.setCheckState(0, Qt.CheckState.Checked)
                self.tree.addTopLevelItem(parent_item)
            else:
                # If the dataset is already in self.data, find the existing parent item
                parent_item = self._find_tree_item(file_name)

            # Expand the parent item to show the new child
            self.tree.expandItem(parent_item)

            # Create the child item for the point cloud
            pointcloud_item = QTreeWidgetItem(["Pointcloud"])
            pointcloud_item.setFlags(pointcloud_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            pointcloud_item.setCheckState(0, Qt.CheckState.Checked)
            parent_item.addChild(pointcloud_item)

            # Add the point cloud to the viewer with the parent name and child name
            self.o3d_viewer.add_pointcloud(data["Pointcloud"], file_name, "Pointcloud")
            self.add_log_message(f"Point cloud added: {file_name}")

        except Exception as e:
            self.add_log_message(f"Failed to add point cloud: {str(e)}")

    def add_sampled_pointcloud(self, parent_name, sampled_pc):
        if parent_name in self.data:
            # Correctly store the sampled point cloud
            self.data[parent_name]["sampled_pointcloud"] = sampled_pc

            # Find the parent tree item
            parent_item = self._find_tree_item(parent_name)
            if parent_item:
                # Add the "Sampled Pointcloud" tree item
                sampled_item = QTreeWidgetItem(["Sampled Pointcloud"])
                sampled_item.setFlags(sampled_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                sampled_item.setCheckState(0, Qt.CheckState.Checked)
                parent_item.addChild(sampled_item)

            # Add the sampled point cloud to the viewer with a unique name
            self.o3d_viewer.add_pointcloud(sampled_pc, f"{parent_name}_sampled")
            self.o3d_viewer.update_viewer()

            self.add_log_message(f"Sampled point cloud added under '{parent_name}'.")
        else:
            self.add_log_message(f"Parent '{parent_name}' not found in data.")

    def _find_tree_item(self, file_name):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.text(0) == file_name:
                return item
        return None

    def on_item_changed(self, item, column):
        is_checked = item.checkState(0) == Qt.CheckState.Checked

        # If it's a parent item, propagate the change to all its children
        if not item.parent():  # Parent item (no parent)
            parent_name = item.text(0)
            if parent_name in self.data:
                for i in range(item.childCount()):
                    child_item = item.child(i)
                    child_item.setCheckState(0, Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
                    child_name = child_item.text(0)
                    self.o3d_viewer.toggle_pointcloud_visibility(parent_name, child_name, is_checked)
        else:  # If it's a child item (point cloud)
            parent_name = item.parent().text(0)
            child_name = item.text(0)

            if parent_name in self.data:
                # Toggle the visibility of the specific point cloud
                self.o3d_viewer.toggle_pointcloud_visibility(parent_name, child_name, is_checked)
            else:
                self.add_log_message(f"Parent dataset '{parent_name}' not found.")

    def open_sample_dialog(self):
        # Retrieve selected items from the tree
        selected_items = self.tree.selectedItems()
        if not selected_items:
            self.add_log_message("No point clouds selected for sampling.")
            return

        print("Opening sample dialog...")  # Debugging

        # Define sampling methods as nested functions

        def sample_pointcloud_random(pointcloud, percentage):
            """Randomly sample the given point cloud based on percentage, retaining colors."""
            if not pointcloud or not pointcloud.has_points():
                print("No point cloud provided for random sampling.")
                return None

            points = np.asarray(pointcloud.points)  # Convert points to NumPy array
            colors = np.asarray(pointcloud.colors)  # Convert colors to NumPy array (if available)
            num_points = len(points)
            sample_size = int(num_points * (percentage / 100))

            if sample_size <= 0:
                print("Sample size is too small. Adjust the percentage.")
                return None

            # Randomly sample indices
            indices = random.sample(range(num_points), sample_size)
            sampled_points = points[indices]  # Sample points using the indices
            sampled_colors = colors[indices] if colors.size else None  # Sample colors (if present)

            # Create a new point cloud with sampled points and colors
            sampled_pc = o3d.geometry.PointCloud()
            sampled_pc.points = o3d.utility.Vector3dVector(sampled_points)
            if sampled_colors is not None:
                sampled_pc.colors = o3d.utility.Vector3dVector(sampled_colors)

            return sampled_pc

        def sample_pointcloud_regular(pointcloud, percentage):
            """Regularly sample the given point cloud based on percentage, retaining colors."""
            if not pointcloud or not pointcloud.has_points():
                print("No point cloud provided for regular sampling.")
                return None

            points = np.asarray(pointcloud.points)  # Convert points to a NumPy array
            colors = np.asarray(pointcloud.colors)  # Convert colors to a NumPy array (if available)
            num_points = len(points)
            sample_size = int(num_points * (percentage / 100))

            if sample_size <= 0:
                print("Sample size is too small. Adjust the percentage.")
                return None

            # Regular sampling: take every nth point
            step = max(1, num_points // sample_size)  # Ensure step is at least 1
            indices = list(range(0, num_points, step))[:sample_size]
            sampled_points = points[indices]  # Sample points using indices
            sampled_colors = colors[indices] if colors.size else None  # Sample colors (if present)

            # Create a new point cloud with sampled points and colors
            sampled_pc = o3d.geometry.PointCloud()
            sampled_pc.points = o3d.utility.Vector3dVector(sampled_points)
            if sampled_colors is not None:
                sampled_pc.colors = o3d.utility.Vector3dVector(sampled_colors)

            return sampled_pc

        def sample_pointcloud_voxel(pointcloud, voxel_size):
            """Voxel downsample the given point cloud based on voxel size."""
            if not pointcloud:
                self.add_log_message("No point cloud provided for voxel sampling.")
                return None

            if voxel_size <= 0:
                self.add_log_message("Invalid voxel size. Must be greater than zero.")
                return None

            sampled_pc = pointcloud.voxel_down_sample(voxel_size)
            return sampled_pc

        # Open the sample dialog
        dialog = SampleDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            sample_type = dialog.get_sample_type()

            # Check for sampling type and handle parameters accordingly
            if sample_type in ["Random Sample", "Regular Sample"]:
                percentage = dialog.get_percentage()
            elif sample_type == "Voxel Downsample":
                voxel_size = dialog.get_voxel_size()
            else:
                self.add_log_message(f"Invalid sample type: {sample_type}.")
                return

            for item in selected_items:
                # Determine the file name and check hierarchy
                if item.parent():  # If it's a child item
                    parent_name = item.parent().text(0)  # Parent holds the file name
                    child_name = item.text(0)  # Child text represents the cloud type
                else:  # If it's a top-level (parent) item
                    self.add_log_message("Top-level items cannot be sampled directly.")
                    continue

                # Ensure the point cloud is selected
                if child_name != "Pointcloud":
                    self.add_log_message(f"Skipping: {child_name}. Only 'Pointcloud' supports sampling.")
                    continue

                # Retrieve the point cloud data
                pointcloud_data = self.data.get(parent_name)
                if not pointcloud_data or "Pointcloud" not in pointcloud_data:
                    self.add_log_message(f"No valid point cloud found for {parent_name}. Skipping.")
                    continue

                original_pc = pointcloud_data["Pointcloud"]

                # Perform sampling
                sampled_pc = None
                if sample_type == "Random Sample":
                    sampled_pc = sample_pointcloud_random(original_pc, percentage)
                elif sample_type == "Regular Sample":
                    sampled_pc = sample_pointcloud_regular(original_pc, percentage)
                elif sample_type == "Voxel Downsample":
                    sampled_pc = sample_pointcloud_voxel(original_pc, voxel_size)
                else:
                    self.add_log_message(f"Invalid sample type: {sample_type}. Skipping {parent_name}.")
                    continue

                if not sampled_pc:
                    self.add_log_message(f"Sampling failed for {parent_name}.")
                    continue

                # Name and store the sampled point cloud
                sampled_file_name = "Sampled Pointcloud"

                self.data[parent_name][child_name] = sampled_pc



                # Add the sampled point cloud to the tree and viewer
                self.add_child_to_tree_and_data(item.parent(), sampled_file_name, sampled_pc)

                # Add sampled point cloud to the viewer
                self.o3d_viewer.add_pointcloud(sampled_pc, parent_name, child_name=sampled_file_name)
                self.add_log_message(f"Sampled pointcloud added: {sampled_file_name}")

                # Log the number of points in the sampled point cloud
                num_sampled_points = len(np.asarray(sampled_pc.points))
                self.add_log_message(f"Sampled pointcloud added: {sampled_file_name}, {num_sampled_points} points.")

            # Update the viewer
            self.o3d_viewer.update_viewer()
            self.add_log_message("Viewer updated with sampled pointclouds.")

    def add_child_to_tree_and_data(self, parent_item, child_name, data):
        """Adds a child item to the parent in the tree and updates the 'data' dictionary."""
        if not parent_item:
            self.add_log_message("Invalid parent item for tree update.")
            return

        # Create a new child item for the sampled point cloud
        child_item = QTreeWidgetItem([child_name])
        child_item.setCheckState(0, Qt.CheckState.Checked)  # Ensure checkbox is initialized as checked

        # Make the child item checkable
        child_item.setFlags(child_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

        # Add the child item to the parent
        parent_item.addChild(child_item)

        # Expand the parent item to show the new child
        self.tree.expandItem(parent_item)

        parent_name = parent_item.text(0)  # Parent name is the text of the parent item

        if parent_name not in self.data:
            self.data[parent_name] = {}

        # Store the sampled point cloud directly under the parent_name
        self.data[parent_name][child_name] = data

        # Ensure the point cloud is added to the Open3D viewer
        self.o3d_viewer.add_pointcloud(data, parent_name, child_name)
        self.add_log_message(f"{child_name} added")

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        view_menu = menu_bar.addMenu("View")

        add_pointcloud_action = QAction("Add Pointcloud", self)
        add_pointcloud_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(add_pointcloud_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_log_action = QAction("View Log", self)
        view_log_action.triggered.connect(self.log_window.show)
        view_menu.addAction(view_log_action)

        tools_menu = menu_bar.addMenu("Tools")

        filters_menu = tools_menu.addMenu("Filters")

        sample_action = QAction("Sample", self)
        sample_action.triggered.connect(self.open_sample_dialog)
        filters_menu.addAction(sample_action)

    def open_file_dialog(self):
        """Open file dialog to select a point cloud file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Pointcloud File", "",
            "Pointclouds (*.pcd *.las *.ply *.xyz *.xyzn *.xyzrgb *.pts)"
        )
        if file_path:
            self.add_pointcloud(file_path)

    def import_pointcloud(self, file_path, transform_settings):
        """Load and process a point cloud."""
        self.add_log_message(f"Importing point cloud: {file_path}...")
        if file_path.endswith(".las"):
            pointcloud = self.load_las_to_open3d_chunked(file_path, transform_settings)
        else:
            pointcloud = o3d.io.read_pointcloud(file_path)

        if not pointcloud or pointcloud.is_empty():
            raise ValueError("Imported point cloud is empty.")

        file_name = file_path.split("/")[-1]
        return {
            "Pointcloud": pointcloud,
            "transform_settings": transform_settings,
            "file_path": file_path,
            "file_name": file_name,
        }

    def load_las_to_open3d_chunked(self, file_path, transform_settings, max_points=1_000_000):
        """Load .las file and convert to Open3D point cloud in chunks."""

        with laspy.open(file_path) as las_file:
            header = las_file.header
            points_count = header.point_count

            points = []
            colors = []

            pointcloud = las_file.read()

            sample_x = pointcloud.x[0] if len(pointcloud.x) > 0 else 0
            sample_y = pointcloud.y[0] if len(pointcloud.y) > 0 else 0

            translate_x = (int(sample_x) // 1000) * 1000
            translate_y = (int(sample_y) // 1000) * 1000

            self.translation_values = {"x": translate_x, "y": translate_y}

            self.add_log_message(
                f"Automatically determined translation values: translate_x={translate_x}, translate_y={translate_y}")

            for start in range(0, points_count, max_points):
                end = min(start + max_points, points_count)
                chunk = pointcloud[start:end]

                x, y, z = np.array(chunk.x), np.array(chunk.y), np.array(chunk.z)

                x = x - translate_x
                y = y - translate_y

                points.append(np.column_stack((x, y, z)))

                if 'red' in chunk.point_format.dimension_names:
                    r = chunk.red / 65535.0
                    g = chunk.green / 65535.0
                    b = chunk.blue / 65535.0
                    colors.append(np.column_stack((r, g, b)))
                else:
                    colors.append(np.zeros((len(x), 3)))

            points = np.vstack(points)
            colors = np.vstack(colors)

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.colors = o3d.utility.Vector3dVector(colors)
        return pcd

    def add_log_message(self, message):
        self.log_window.add_message(message)

    def closeEvent(self, event):
        """Handle the close event to ensure Open3D viewer is closed."""
        self.o3d_viewer.close()
        super().closeEvent(event)


# used for checking, remove from production
def visualize_pointcloud(pointcloud):
    """
    Visualize a given Open3D point cloud.
    :param pointcloud: An instance of o3d.geometry.PointCloud
    """
    if not isinstance(pointcloud, o3d.geometry.PointCloud):
        print("Provided object is not a valid Open3D point cloud.")
        return

    # Create a visualization window
    o3d.visualization.draw_geometries(
        [pointcloud],
        window_name="Open3D Pointcloud Viewer",
        width=800,
        height=600,
        left=50,
        top=50,
        point_show_normal=False
    )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec())
