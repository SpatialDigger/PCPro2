import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QMenuBar, QFileDialog,
    QAbstractItemView, QCheckBox, QHBoxLayout, QPushButton
)

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QComboBox, QFormLayout,
                             QSpinBox, QLabel, QDialogButtonBox, QDoubleSpinBox)


from PyQt6.QtCore import Qt

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QContextMenuEvent
from shapely.geometry import Point,  Polygon, MultiLineString, LineString
from shapely.ops import unary_union
import open3d as o3d
import warnings

import random
import laspy
import numpy as np
warnings.filterwarnings("ignore", category=DeprecationWarning)

from helpers import PreferencesDialog, LogWindow, PropertiesDialog
from dialogs import SampleDialog, ConvexhullDialog, HullFilterDialog
from viewer import Open3DViewer


class DistanceFilterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Distance Filter Settings")
        self.setModal(True)

        layout = QVBoxLayout()

        # Minimum distance input field
        self.min_distance_label = QLabel("Minimum Distance:")
        self.min_distance_input = QDoubleSpinBox()
        self.min_distance_input.setRange(0.0, 1000.0)
        self.min_distance_input.setValue(0.05)  # Default value

        # Comparison type selection dropdown
        self.comparison_type_label = QLabel("Comparison Type:")
        self.comparison_type_combo = QComboBox()
        self.comparison_type_combo.addItems([
            "Greater Than", "Greater Than or Equal To",
            "Less Than", "Less Than or Equal To",
            "Equal To", "Not Equal To"
        ])

        # Add inputs to the form layout
        form_layout = QFormLayout()
        form_layout.addRow(self.min_distance_label, self.min_distance_input)
        form_layout.addRow(self.comparison_type_label, self.comparison_type_combo)

        layout.addLayout(form_layout)

        # Dialog buttons: Ok and Cancel
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        # Set the dialog's layout
        self.setLayout(layout)

    def get_min_distance(self):
        """Returns the entered minimum distance."""
        return self.min_distance_input.value()

    def get_comparison_type(self):
        """Returns the selected comparison type."""
        return self.comparison_type_combo.currentText()


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

        # Set multi-selection mode
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        self.tree.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.tree)
        self.data = {}
        self.o3d_viewer = Open3DViewer(logger=self.add_log_message)
        self.log_window = LogWindow(self)
        self.create_menu_bar()
        self.viewer_update_timer = QTimer()
        self.viewer_update_timer.timeout.connect(self.o3d_viewer.update_viewer)
        self.viewer_update_timer.start(16)
        print(o3d.__version__)

    def selected_items(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            self.add_log_message("No items selected for filtering.")
            return
        return selected_items



















    def remove_selected_items(self):
        """Removes the selected items from both the tree and the data dictionary."""
        selected_items = self.selected_items()

        # Use a set to keep track of parents whose children should not be double-processed
        processed_parents = set()

        # Process selected items
        for item in selected_items:
            parent_item = item.parent()
            if parent_item is None:
                # This is a top-level item (a parent)
                parent_name = item.text(0)
                if parent_name not in processed_parents:
                    self.add_log_message(f"Removing parent '{parent_name}' and all its children.")
                    self.remove_from_tree_and_data(parent_name)
                    processed_parents.add(parent_name)
            else:
                # This is a child item
                parent_name = parent_item.text(0)
                child_name = item.text(0)
                # Ensure the parent is not being processed later
                if parent_name not in processed_parents:
                    self.add_log_message(f"Removing child '{child_name}' under parent '{parent_name}'.")
                    self.remove_from_tree_and_data(parent_name, child_name)

    def remove_from_tree_and_data(self, parent_name, child_name=None):
        """
        Removes an item (either parent and all its children or a specific child)
        from both the tree and the data dictionary.
        """
        # Check if the parent exists in the data dictionary
        if parent_name not in self.data:
            self.add_log_message(f"remove_from_tree_and_data: Parent '{parent_name}' not found in data.")
            return

        # If no child is specified, remove the parent and all its children
        if child_name is None:
            # Remove the parent data from the dictionary
            del self.data[parent_name]
            self.add_log_message(
                f"remove_from_tree_and_data: Removed parent '{parent_name}' and all its children from data dictionary.")

            # Remove the parent item from the tree
            parent_item = self._find_tree_item(parent_name)
            if parent_item:
                index = self.tree.indexOfTopLevelItem(parent_item)
                if index != -1:
                    self.tree.takeTopLevelItem(index)
                    self.add_log_message(
                        f"remove_from_tree_and_data: Removed parent '{parent_name}' and all its children from tree.")

            # Remove the parent and its children from the Open3D viewer
            self.o3d_viewer.remove_item(parent_name)
            self.add_log_message(
                f"remove_from_tree_and_data: Removed parent '{parent_name}' and all its children from Open3D viewer.")
            return

        # If a child name is provided, handle removing only the child
        # Check if the child exists under the parent in the data dictionary
        if child_name not in self.data[parent_name]:
            self.add_log_message(
                f"remove_from_tree_and_data: Child '{child_name}' not found under parent '{parent_name}' in data.")
            return

        # Remove the child data from the dictionary
        del self.data[parent_name][child_name]
        self.add_log_message(f"remove_from_tree_and_data: Removed child '{child_name}' from data dictionary.")

        # If the parent has no more children, optionally remove it from the dictionary
        if not self.data[parent_name]:
            del self.data[parent_name]
            self.add_log_message(
                f"remove_from_tree_and_data: Removed parent '{parent_name}' from data dictionary as it has no more children.")

        # Remove the child item from the tree
        parent_item = self._find_tree_item(parent_name)
        if parent_item:
            for i in range(parent_item.childCount()):
                child_item = parent_item.child(i)
                if child_item.text(0) == child_name:
                    parent_item.removeChild(child_item)
                    self.add_log_message(f"remove_from_tree_and_data: Removed child '{child_name}' from tree.")
                    break
            else:
                self.add_log_message(
                    f"remove_from_tree_and_data: Child '{child_name}' not found under parent '{parent_name}' in tree.")

        # Optionally, remove the parent item from the tree if it has no more children
        if parent_item and parent_item.childCount() == 0:
            index = self.tree.indexOfTopLevelItem(parent_item)
            if index != -1:
                self.tree.takeTopLevelItem(index)
                self.add_log_message(
                    f"remove_from_tree_and_data: Removed parent '{parent_name}' from tree as it has no more children.")

        # Remove the child from the Open3D viewer
        self.o3d_viewer.remove_item(parent_name, child_name)
        self.add_log_message(f"remove_from_tree_and_data: Removed '{child_name}' from Open3D viewer.")

    def filter_points_by_hull_footprint(self):
        """Filters points from a selected Open3D point cloud that fall within the footprint of a selected line set (3D convex hull)."""
        selected_items = self.selected_items()

        # Separate selected point clouds and line sets
        selected_point_clouds = []
        selected_line_sets = []
        for item in selected_items:
            parent_name = item.parent().text(0) if item.parent() else None
            child_name = item.text(0)
            key = (parent_name, child_name)

            if key in self.o3d_viewer.items:
                o3d_item = self.o3d_viewer.items[key]
                if isinstance(o3d_item, o3d.geometry.PointCloud):
                    selected_point_clouds.append(o3d_item)
                elif isinstance(o3d_item, o3d.geometry.LineSet):
                    selected_line_sets.append(o3d_item)

        if not selected_point_clouds or not selected_line_sets:
            self.add_log_message("At least one point cloud and one line set must be selected.")
            return

        # Iterate through selected point clouds and line sets
        for point_cloud in selected_point_clouds:
            for line_set in selected_line_sets:
                # Flatten the point cloud (remove z-coordinate)
                points = np.asarray(point_cloud.points)
                colors = np.asarray(point_cloud.colors)  # Get RGB values
                points_2d = points[:, :2]

                # Extract edges from the line set
                lines = np.asarray(line_set.lines)
                vertices = np.asarray(line_set.points)
                vertices_2d = vertices[:, :2]

                # Ensure the line set forms a closed loop (by appending the first vertex at the end if necessary)
                if not np.array_equal(vertices_2d[0], vertices_2d[-1]):
                    vertices_2d = np.vstack([vertices_2d, vertices_2d[0]])

                # Create LineString objects for each edge (i.e., face of the convex hull in 2D)
                edges = []
                for i in range(len(vertices_2d) - 1):
                    edge = LineString([vertices_2d[i], vertices_2d[i + 1]])
                    edges.append(edge)

                # Merge all line segments into a single polygon
                merged_polygon = unary_union(edges)
                if isinstance(merged_polygon, Polygon):
                    polygon = merged_polygon
                else:
                    # If we get multiple separate polygons, merge them into one (using convex hull if needed)
                    polygon = merged_polygon.convex_hull

                # Filter points inside the polygon (keep the 3D structure)
                filtered_points = []
                filtered_colors = []
                for i, point in enumerate(points_2d):
                    if polygon.contains(Point(point)):
                        # Append the original 3D point and corresponding color (RGB)
                        filtered_points.append(points[i])
                        filtered_colors.append(colors[i])

                if not filtered_points:
                    self.add_log_message("No points found inside the polygon.")
                    continue

                # Create a new point cloud from filtered points, restoring Z-coordinate
                new_point_cloud = o3d.geometry.PointCloud()
                new_point_cloud.points = o3d.utility.Vector3dVector(np.array(filtered_points))
                new_point_cloud.colors = o3d.utility.Vector3dVector(np.array(filtered_colors))  # Add RGB values

                # Generate the child name for the new point cloud
                base_child_name = "pointcloud_in_3dhull"
                child_name = base_child_name

                # Check if a point cloud with this name already exists under the parent
                parent_name = None
                for item in selected_items:
                    # if item.text(0) == point_cloud.name:
                    if item.text(0) == child_name:
                        parent_name = item.parent().text(0) if item.parent() else None
                        break

                # If parent_name is None (which should not happen in this case), fallback to the first point cloud's parent
                if parent_name is None:
                    parent_name = selected_items[0].parent().text(0) if selected_items[
                        0].parent() else "Filtered Point Clouds"

                # Ensure unique child name by checking if it exists under the parent
                existing_children = self.data.get(parent_name, {}).keys()
                counter = 1
                while child_name in existing_children:
                    child_name = f"{base_child_name}_{counter}"
                    counter += 1

                # Add the new point cloud to the tree and data using add_child_to_tree_and_data
                self.add_child_to_tree_and_data(parent_name, child_name, new_point_cloud)

                self.add_log_message(f"Added filtered point cloud '{child_name}' under '{parent_name}'.")

    def open_sample_dialog(self):
        selected_items = self.selected_items()

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
                data = self.data.get(parent_name)
                if not data:
                    self.add_log_message(f"No valid point cloud found for {parent_name}. Skipping.")
                    continue

                point_dataset = data[child_name]

                # Perform sampling
                sampled_pc = None
                if sample_type == "Random Sample":
                    sampled_pc = sample_pointcloud_random(point_dataset, percentage)
                elif sample_type == "Regular Sample":
                    sampled_pc = sample_pointcloud_regular(point_dataset, percentage)
                elif sample_type == "Voxel Downsample":
                    sampled_pc = sample_pointcloud_voxel(point_dataset, voxel_size)
                else:
                    self.add_log_message(f"Invalid sample type: {sample_type}. Skipping {parent_name}.")
                    continue

                if not sampled_pc:
                    self.add_log_message(f"Sampling failed for {parent_name}.")
                    continue

                # Name and store the sampled point cloud
                sampled_file_name = "Sampled Pointcloud"

                self.data[parent_name][sampled_file_name] = sampled_pc

                # Add the sampled point cloud to the tree and viewer
                # parent = item.parent()
                self.add_child_to_tree_and_data(parent_name, "Sampled Pointcloud", sampled_pc)

                # Add sampled point cloud to the viewer
                self.o3d_viewer.add_item(sampled_pc, parent_name, "Sampled Pointcloud")
                self.add_log_message(f"Sampled pointcloud added: {sampled_file_name}")

                # Log the number of points in the sampled point cloud
                num_sampled_points = len(np.asarray(sampled_pc.points))
                self.add_log_message(f"Sampled pointcloud added: {sampled_file_name}, {num_sampled_points} points.")

            # Update the viewer
            self.o3d_viewer.update_viewer()
            self.add_log_message("Viewer updated with sampled pointclouds.")

    def add_child_to_tree_and_data(self, parent_name, child_name, data):
        """Handles adding both parent and child items to the tree and updating the data dictionary."""
        # Check if the parent item exists in the tree; create it if not
        parent_item = self._find_tree_item(parent_name)
        if not parent_item:
            # Create the parent item
            parent_item = QTreeWidgetItem([parent_name])
            parent_item.setFlags(parent_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            parent_item.setCheckState(0, Qt.CheckState.Checked)
            self.tree.addTopLevelItem(parent_item)
            self.tree.expandItem(parent_item)

            self.add_log_message(f"add_child_to_tree_and_data: Created new parent item '{parent_name}' in tree.")

        # Check if the parent exists in the data dictionary; create it if not
        if parent_name not in self.data:
            self.data[parent_name] = {}
            self.add_log_message(f"add_child_to_tree_and_data: Created new parent '{parent_name}' in data dictionary.")

        # Add the child item to the parent in the tree
        child_item = QTreeWidgetItem([child_name])
        child_item.setCheckState(0, Qt.CheckState.Checked)  # Initialize checkbox as checked
        child_item.setFlags(child_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        parent_item.addChild(child_item)
        self.tree.expandItem(parent_item)

        self.add_log_message(
            f"add_child_to_tree_and_data: Adding child '{child_name}' under parent '{parent_name}' in tree.")

        # Add the child data to the dictionary under the parent
        self.data[parent_name][child_name] = data

        # Ensure the point cloud is added to the Open3D viewer
        self.o3d_viewer.add_item(data, parent_name, child_name)
        self.add_log_message(f"add_child_to_tree_and_data: '{child_name}' added to Open3D viewer.")

        # import pprint
        #
        # # Assuming self.data is a dictionary
        # pprint.pprint(self.data)

    def open_file_dialog(self):
        """Open file dialog to select point cloud files."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Pointcloud Files", "",
            "Pointclouds (*.pcd *.las *.ply *.xyz *.xyzn *.xyzrgb *.pts)"
        )
        if file_paths:
            for file_path in file_paths:
                self.add_pointcloud(file_path)

    def add_pointcloud(self, file_path, transform_settings=None):
        """Handles importing a point cloud and adding it to the tree and data dictionary."""
        try:
            # Import the point cloud data
            data = self.import_pointcloud(file_path, transform_settings)
            file_name = data["file_name"]

            # Add the point cloud as a child under the file name
            self.add_child_to_tree_and_data(
                parent_name=file_name,
                child_name="Pointcloud",
                data=data["Pointcloud"]
            )

            # Store additional metadata in the parent data dictionary
            self.data[file_name].update({
                "transform_settings": transform_settings,
                "file_path": file_path,
                "file_name": file_name,
            })

            self.add_log_message(f"Point cloud successfully added for file '{file_name}'.")
        except Exception as e:
            self.add_log_message(f"Failed to add point cloud: {str(e)}")

    def _find_tree_item(self, file_name):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.text(0) == file_name:
                return item
        return None

    def on_item_changed(self, item):
        is_checked = item.checkState(0) == Qt.CheckState.Checked

        # Prevent infinite loops
        self.tree.blockSignals(True)
        try:
            # Parent-level changes
            if not item.parent():
                parent_name = item.text(0)
                for i in range(item.childCount()):
                    child_item = item.child(i)
                    child_item.setCheckState(0, Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
                    child_name = child_item.text(0)
                    self.o3d_viewer.toggle_item_visibility(parent_name, child_name, is_checked)
            else:  # Child-level changes
                parent_name = item.parent().text(0)
                child_name = item.text(0)
                self.o3d_viewer.toggle_item_visibility(parent_name, child_name, is_checked)
        finally:
            self.tree.blockSignals(False)

    def merge_items(self):
        """
        Merge selected Open3D objects of the same type and add the result to the tree.
        The merged data is added as a new parent with a child named according to the data type.
        """
        # Retrieve selected items from the tree
        selected_items = self.selected_items()

        if len(selected_items) < 2:
            self.add_log_message("Select at least two items to merge.")
            return None

        # Retrieve Open3D objects and their parents from the tree
        open3d_objects = []
        parent_names = []
        for item in selected_items:
            parent = item.parent()
            if parent is None:
                self.add_log_message(f"Item '{item.text(0)}' has no parent; skipping.")
                return None
            parent_name = parent.text(0)
            if parent_name not in parent_names:
                parent_names.append(parent_name)  # Avoid duplicates
            item_name = item.text(0)
            open3d_object = self.data[parent_name][item_name]
            open3d_objects.append(open3d_object)

        if len(parent_names) > 2:
            self.add_log_message("Merging is limited to two different parents.")
            return None

        # Ensure all items are of the same type
        first_item_type = type(open3d_objects[0])
        if not all(isinstance(obj, first_item_type) for obj in open3d_objects):
            self.add_log_message("Cannot merge items of different types.")
            return None

        # Merge Open3D objects
        if first_item_type == o3d.geometry.PointCloud:
            self.add_log_message("Merging PointClouds...")
            merged_object = o3d.geometry.PointCloud()
            for obj in open3d_objects:
                merged_object += obj  # Assuming PointCloud supports `+=` for merging
            child_name = "Pointcloud"
        elif first_item_type == o3d.geometry.LineSet:
            self.add_log_message("Merging LineSets...")
            merged_object = o3d.geometry.LineSet()
            for obj in open3d_objects:
                merged_object += obj  # Assuming LineSet supports `+=` for merging
            child_name = "LineSet"
        elif first_item_type == o3d.geometry.TriangleMesh:
            self.add_log_message("Merging TriangleMeshes...")
            merged_object = o3d.geometry.TriangleMesh()
            for obj in open3d_objects:
                merged_object += obj  # Assuming TriangleMesh supports `+=` for merging
            child_name = "TriangleMesh"
        else:
            self.add_log_message(f"Merging for type '{first_item_type.__name__}' is not supported.")
            return None

        # Create a new parent name based on the parent filenames
        new_parent_name = f"{parent_names[0]}_{parent_names[1]}"

        # Add the merged object to the tree and data structure using the helper method
        self.add_child_to_tree_and_data(new_parent_name, child_name, merged_object)

        # Log success
        self.add_log_message(f"Merged items added to the tree under '{new_parent_name}'.")


#####################################################################################
    # def filter_points_by_distance(self):
    #     """Filters points from two selected point clouds based on the minimum distance between them."""
    #
    #     # Retrieve selected items from the GUI or context
    #     selected_items = self.selected_items()
    #
    #     # Separate selected point clouds
    #     selected_point_clouds = []
    #     for item in selected_items:
    #         parent_name = item.parent().text(0) if item.parent() else None
    #         child_name = item.text(0)
    #         key = (parent_name, child_name)
    #
    #         if key in self.o3d_viewer.items:
    #             o3d_item = self.o3d_viewer.items[key]
    #             if isinstance(o3d_item, o3d.geometry.PointCloud):
    #                 selected_point_clouds.append(o3d_item)
    #
    #     if len(selected_point_clouds) != 2:
    #         self.add_log_message("Exactly two point clouds must be selected.")
    #         return
    #
    #     # Extract the two point clouds
    #     pc1, pc2 = selected_point_clouds
    #
    #     # Inside the filter_points_by_distance method
    #     dialog = DistanceFilterDialog(self)
    #     if dialog.exec() == QDialog.DialogCode.Accepted:  # Change to this
    #         min_distance = dialog.get_min_distance()
    #         comparison_type = dialog.get_comparison_type()
    #
    #     # # Show the distance filter dialog to get the parameters
    #     # dialog = DistanceFilterDialog(self)  # Show the dialog
    #     # if dialog.exec() == QDialog.Accepted:
    #     #     min_distance = dialog.get_min_distance()  # Get the minimum distance
    #     #     comparison_type = dialog.get_comparison_type()  # Get the comparison type
    #
    #         # Compute the filtered point clouds based on distance
    #         filtered_pc1, filtered_pc2 = self.filter_points_by_distance_logic(pc1, pc2, min_distance, comparison_type)
    #
    #         if filtered_pc1 is None or filtered_pc2 is None:
    #             self.add_log_message("No points met the distance criteria.")
    #             return
    #
    #         # Generate the child names for the new point clouds
    #         base_child_name = "filtered_pointcloud_by_distance"
    #         child_name_1 = base_child_name + "_1"
    #         child_name_2 = base_child_name + "_2"
    #
    #         # Get parent name (fallback to "Filtered Point Clouds")
    #         parent_name = selected_items[0].parent().text(0) if selected_items[0].parent() else "Filtered Point Clouds"
    #
    #         # Ensure unique child names under the parent
    #         existing_children = self.data.get(parent_name, {}).keys()
    #         counter = 1
    #         while child_name_1 in existing_children:
    #             child_name_1 = f"{base_child_name}_{counter}"
    #             counter += 1
    #         counter = 1
    #         while child_name_2 in existing_children:
    #             child_name_2 = f"{base_child_name}_{counter}"
    #             counter += 1
    #

    #
    #         # Add the new point clouds to the tree and data
    #         self.add_child_to_tree_and_data(parent_name, child_name_1, filtered_pc1)
    #         self.add_child_to_tree_and_data(parent_name, child_name_2, filtered_pc2)
    #
    #         self.add_log_message(
    #             f"Added filtered point clouds '{child_name_1}' and '{child_name_2}' under '{parent_name}'.")

    def filter_points_by_distance(self):
        """Filters points from two selected point clouds based on the minimum distance between them."""

        # Retrieve selected items from the GUI or context
        selected_items = self.selected_items()

        # Separate selected point clouds along with their parents
        selected_point_clouds = []
        parent_child_mapping = {}  # Maps point clouds to their respective parents

        for item in selected_items:
            parent_name = item.parent().text(0) if item.parent() else None
            child_name = item.text(0)
            key = (parent_name, child_name)

            if key in self.o3d_viewer.items:
                o3d_item = self.o3d_viewer.items[key]
                if isinstance(o3d_item, o3d.geometry.PointCloud):
                    selected_point_clouds.append(o3d_item)
                    parent_child_mapping[o3d_item] = parent_name

        if len(selected_point_clouds) != 2:
            self.add_log_message("Exactly two point clouds must be selected.")
            return

        # Extract the two point clouds
        pc1, pc2 = selected_point_clouds

        # Show the distance filter dialog to get the parameters
        dialog = DistanceFilterDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            min_distance = dialog.get_min_distance()
            comparison_type = dialog.get_comparison_type()

            # Compute the filtered point clouds based on distance
            filtered_pc1, filtered_pc2 = self.filter_points_by_distance_logic(pc1, pc2, min_distance, comparison_type)

            if filtered_pc1 is None or filtered_pc2 is None:
                self.add_log_message("No points met the distance criteria.")
                return

            # Generate the child names for the new point clouds
            base_child_name = "filtered_pointcloud_by_distance"

            def generate_unique_name(base_name, existing_children):
                counter = 1
                unique_name = base_name
                while unique_name in existing_children:
                    unique_name = f"{base_name}_{counter}"
                    counter += 1
                return unique_name

            # Add the filtered point clouds to their respective parents
            for filtered_pc, original_pc in zip([filtered_pc1, filtered_pc2], [pc1, pc2]):
                parent_name = parent_child_mapping.get(original_pc, "Filtered Point Clouds")
                existing_children = self.data.get(parent_name, {}).keys()

                child_name = generate_unique_name(base_child_name, existing_children)

                # Add the new point cloud to the tree and data
                self.add_child_to_tree_and_data(parent_name, child_name, filtered_pc)

                self.add_log_message(
                    f"Added filtered point cloud '{child_name}' under '{parent_name}'.")

    def filter_points_by_distance_logic(self, pc1, pc2, min_distance, comparison_type):
        """Performs the distance filtering logic between two point clouds."""
        # Compute distances from each point in pc1 to the nearest point in pc2
        distances = np.asarray(o3d.geometry.PointCloud.compute_point_cloud_distance(pc1, pc2))


        # Apply the distance filter based on comparison_type
        if comparison_type == "Greater Than":
            filter_mask = distances > min_distance
        elif comparison_type == "Greater Than or Equal To":
            filter_mask = distances >= min_distance
        elif comparison_type == "Less Than":
            filter_mask = distances < min_distance
        elif comparison_type == "Less Than or Equal To":
            filter_mask = distances <= min_distance
        elif comparison_type == "Equal To":
            filter_mask = np.isclose(distances, min_distance)  # Using np.isclose for floating point equality
        elif comparison_type == "Not Equal To":
            filter_mask = ~np.isclose(distances, min_distance)
        else:
            raise ValueError(f"Unknown comparison type: {comparison_type}")

        # Apply the filter mask to pc1
        filtered_points1 = np.asarray(pc1.points)[filter_mask]

        # Repeat for the second point cloud, comparing distances from points in pc2 to pc1
        distances_reverse = np.asarray(o3d.geometry.PointCloud.compute_point_cloud_distance(pc2, pc1))
        if comparison_type == "Greater Than":
            filter_mask2 = distances_reverse > min_distance
        elif comparison_type == "Greater Than or Equal To":
            filter_mask2 = distances_reverse >= min_distance
        elif comparison_type == "Less Than":
            filter_mask2 = distances_reverse < min_distance
        elif comparison_type == "Less Than or Equal To":
            filter_mask2 = distances_reverse <= min_distance
        elif comparison_type == "Equal To":
            filter_mask2 = np.isclose(distances_reverse, min_distance)
        elif comparison_type == "Not Equal To":
            filter_mask2 = ~np.isclose(distances_reverse, min_distance)

        filtered_points2 = np.asarray(pc2.points)[filter_mask2]

        if not filtered_points1.any() or not filtered_points2.any():
            return None, None  # No points passed the filter

        # Create new point clouds from the filtered points
        filtered_pc1 = o3d.geometry.PointCloud()
        filtered_pc1.points = o3d.utility.Vector3dVector(filtered_points1)

        filtered_pc2 = o3d.geometry.PointCloud()
        filtered_pc2.points = o3d.utility.Vector3dVector(filtered_points2)

        return filtered_pc1, filtered_pc2





    #####################################################################################










    def open_convexhull3d_dialog(self):
        # Retrieve selected items from the tree
        selected_items = self.selected_items()

        print("Not opening ConvexHull dialog...")  # Debugging
        for item in selected_items:
            # Determine the file name and check hierarchy
            if item.parent():  # If it's a child item
                parent_name = item.parent().text(0)  # Parent holds the file name
                child_name = item.text(0)  # Child text represents the cloud type
            else:  # If it's a top-level (parent) item
                self.add_log_message("Top-level items cannot be sampled directly.")
                continue

            # Retrieve the point cloud data
            data = self.data.get(parent_name)
            if not data:
                self.add_log_message(f"No valid point cloud found for {parent_name}. Skipping.")
                continue
            point_dataset = data[child_name]
            # Perform convexhull
            def hull3d(point_cloud):
                # Compute the convex hull of the point cloud
                hull, _ = point_cloud.compute_convex_hull()

                # Create a LineSet from the convex hull
                hull_ls = o3d.geometry.LineSet.create_from_triangle_mesh(hull)
                return hull_ls

            hull_tri = hull3d(point_dataset)

            if not hull_tri:
                self.add_log_message(f"Sampling failed for {parent_name}.")
                continue

            # Name and store the sampled point cloud
            # sampled_file_name = "Hull3D"
            self.data[parent_name]["Hull3D"] = hull_tri

            # Add the sampled point cloud to the tree and viewer
            self.add_child_to_tree_and_data(parent_name, "Hull3D", hull_tri)

            # Add Hull to the viewer
            self.o3d_viewer.add_item(hull_tri, parent_name, "Hull3D")
            self.add_log_message(f"Sampled pointcloud added: Hull3D")

        # Update the viewer
        self.o3d_viewer.update_viewer()
        self.add_log_message("Viewer updated with ConvexHull.")

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

        convexhull_action = QAction("Convexhull 3D", self)
        convexhull_action.triggered.connect(self.open_convexhull3d_dialog)
        filters_menu.addAction(convexhull_action)

        merge_action = QAction("Merge", self)
        merge_action.triggered.connect(self.merge_items)
        filters_menu.addAction(merge_action)


        filter_points_by_hull_footprint_action = QAction("Hull footprint", self)
        filter_points_by_hull_footprint_action.triggered.connect(self.filter_points_by_hull_footprint)
        filters_menu.addAction(filter_points_by_hull_footprint_action)


        remove_items_action = QAction("Remove Items", self)
        remove_items_action.triggered.connect(self.remove_selected_items)
        filters_menu.addAction(remove_items_action)

        between_distance_action = QAction("Between Distance", self)
        between_distance_action.triggered.connect(self.filter_points_by_distance)
        filters_menu.addAction(between_distance_action)

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
    # if not isinstance(pointcloud, o3d.geometry.PointCloud):
    #     print("Provided object is not a valid Open3D point cloud.")
    #     return

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
