import json


class ConfigLoader():
    """
    Reads and stores all configuration:
    - camera intrinsics
    - distortion coefficients
    - HSV color ranges
    """

    def __init__(self, path="config/configs/config.json"):
        self.path = path

        # Will be filled after load()
        self.intrinsics = None
        self.distortion = None
        self.color_ranges_hsv = {}

    def load(self):
        """Load the JSON configuration file."""
        with open(self.path, "r") as f:
            data = json.load(f)

        camera = data.get("camera", {})
        self.intrinsics = camera.get("intrinsics")
        self.distortion = camera.get("distortion")

        ranges = data.get("color_ranges", {})
        self.color_ranges_hsv = ranges

    def is_loaded(self):
        return self.intrinsics is not None and self.distortion is not None
