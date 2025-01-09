import open3d as o3d

class Open3DViewer:
    def __init__(self, logger=None):
        self.vis = o3d.visualization.Visualizer()
        # self.vis = o3d.visualization.VisualizerWithEditing()
        self.window_width = 800
        self.window_height = 600
        self.vis.create_window(width=self.window_width, height=self.window_height)
        self.view_control = self.vis.get_view_control()
        self.items = {}
        self.logger = logger
        self.visible_items = {}  # Track visible point clouds

    def log_message(self, message):
        if self.logger:
            self.logger(message)

    def add_item(self, item, parent_name, child_name):
        """Add geometry to the viewer and track it uniquely."""
        if (parent_name, child_name) not in self.items:
            self.vis.add_geometry(item)
            self.items[(parent_name, child_name)] = item
            self.visible_items[(parent_name, child_name)] = True  # Default to visible
        else:
            self.log_message(f"Item '{child_name}' under '{parent_name}' already exists.")

    def remove_item(self, parent_name, child_name=None):
        """Remove an item (or all items under a parent) from the viewer."""
        if child_name is None:
            # Remove all items under the parent
            keys_to_remove = [key for key in self.items if key[0] == parent_name]
            for key in keys_to_remove:
                item = self.items[key]
                if self.visible_items.get(key, False):
                    self.vis.remove_geometry(item)
                del self.items[key]
                del self.visible_items[key]
                self.log_message(f"Removed item '{key[1]}' under parent '{key[0]}' from viewer.")
        else:
            # Remove a specific child item
            key = (parent_name, child_name)
            if key in self.items:
                item = self.items[key]
                if self.visible_items.get(key, False):
                    self.vis.remove_geometry(item)
                del self.items[key]
                del self.visible_items[key]
                self.log_message(f"Removed item '{child_name}' under parent '{parent_name}' from viewer.")
            else:
                self.log_message(f"Item '{child_name}' under parent '{parent_name}' not found in viewer.")

        # Refresh the viewer: clear all geometries and re-add remaining ones
        self.vis.clear_geometries()
        for item in self.items.values():
            self.vis.add_geometry(item)

        self.update_viewer()

    def toggle_item_visibility(self, parent_name, child_name, is_visible):
        """Toggle the visibility of the geometry."""
        key = (parent_name, child_name)

        if key in self.items:
            item = self.items[key]

            if is_visible:
                # Add geometry back if not already visible
                if not self.visible_items.get(key, False):
                    self.vis.add_geometry(item)
            else:
                # Remove geometry if currently visible
                if self.visible_items.get(key, False):
                    self.vis.remove_geometry(item)

            # Update visibility state
            self.visible_items[key] = is_visible
            self.log_message(
                f"Visibility toggled for {child_name} under {parent_name}: {'Visible' if is_visible else 'Hidden'}")

            # Refresh the viewer
            self.update_viewer()

    def update_viewer(self):
        """Update the Open3D viewer."""
        self.vis.poll_events()
        self.vis.update_renderer()

    def close(self):
        """Close the Open3D viewer window."""
        self.vis.destroy_window()