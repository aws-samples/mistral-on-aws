import numpy as np
import base64
from typing import List
from pathlib import Path


def haversine_distance(
    source_lat: float, source_lon: float, targets_latlon: List[List[float]]
) -> np.ndarray:
    # Convert degrees to radians
    targets = np.array(targets_latlon)
    lats = targets[:, 0]
    lons = targets[:, 1]
    lat1_rad, lon1_rad = np.radians(source_lat), np.radians(source_lon)
    lats_rad, lons_rad = np.radians(lats), np.radians(lons)

    # Differences in coordinates
    dlat = lats_rad - lat1_rad
    dlon = lons_rad - lon1_rad

    # Haversine formula
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1_rad) * np.cos(lats_rad) * np.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    distances = 6371.0 * c  # Radius of Earth in kilometers

    return distances


def to_minutes(duration_str: str) -> float:
    total_seconds = int(duration_str.replace("s", ""))
    total_minutes = float(format(total_seconds / 60.0, ".1f"))
    return total_minutes


def load_image_file_to_bytes(file_name: str) -> bytes:
    with Path(file_name).open(mode="rb") as f_in:
        image_data = f_in.read()
        return image_data


def load_image_file_to_b64(file_name: str) -> str:
    image_data = load_image_file_to_bytes(file_path=file_name)
    b64_encoded_data = base64.b64encode(image_data)
    return b64_encoded_data.decode("utf-8")


def get_file_extension(file_name: str) -> str:
    return Path(file_name).suffix.replace(".", "")
