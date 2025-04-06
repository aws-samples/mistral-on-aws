from typing import Dict, Any, List
import httpx
import os
import json
from dotenv import load_dotenv
from pathlib import Path
from utils import haversine_distance, to_minutes

GOOGLE_WEATHER_API_ENDPOINT = (
    "https://weather.googleapis.com/v1/currentConditions:lookup"
)
GOOGLE_MAPS_GEOCODE_API_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_ROUTES_API_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
VELIB_STATIONS_FILE_PATH = "./assets/velib_stations.json"
VELIB_SERVICE_URL = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json"

CREDENTIALS_VARIABLES = [
    "GOOGLE_WEATHER_API_KEY",
    "GOOGLE_MAPS_GEOCODE_API_KEY",
    "GOOGLE_ROUTES_API_KEY",
]

load_dotenv()
for var in CREDENTIALS_VARIABLES:
    if not os.environ.get(var, None):
        raise ValueError(f"Missing env variable for credentials: {var}")


def _geocode(address: str) -> Dict[str, float]:
    url = GOOGLE_MAPS_GEOCODE_API_ENDPOINT
    headers = {"Content-Type": "application/json"}
    params = {"address": address, "key": os.getenv("GOOGLE_MAPS_GEOCODE_API_KEY")}
    try:
        resp = httpx.get(url=url, headers=headers, params=params)
        resp.raise_for_status()
        resp_json = resp.json()
        return resp_json["results"][0]["geometry"]["location"]
    except Exception as exc:
        print(f"Error when requesting {url}: {exc}")
        raise


def _parse_legs(legs: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for leg in legs:
        for step in leg["steps"]:
            instruction = step["navigationInstruction"]["instructions"]
            distance = step["distanceMeters"]
            line = f"{instruction} ({distance}m)"
            out.append(line)
    return out


def get_weather(address: str) -> Dict[str, Any]:
    location_lat_lon = _geocode(address=address)
    url = GOOGLE_WEATHER_API_ENDPOINT
    headers = {"Content-Type": "application/json"}
    params = {
        "location.latitude": location_lat_lon["lat"],
        "location.longitude": location_lat_lon["lng"],
        "key": os.getenv("GOOGLE_WEATHER_API_KEY"),
    }
    try:
        resp = httpx.get(url=url, headers=headers, params=params)
        resp.raise_for_status()
        resp_json = resp.json()
        return {
            "description": resp_json["weatherCondition"]["description"]["text"],
            "temperature": resp_json["temperature"]["degrees"],
        }
    except Exception as exc:
        print(f"Error when requesting {url}: {exc}")


def get_nearest_velib_station(address: str) -> Dict[str, Any]:
    locations_lat_lon = _geocode(address=address)
    with Path(VELIB_STATIONS_FILE_PATH).open(mode="r") as f_in:
        stations_data = json.load(f_in).get("data").get("stations")

        station_names_by_id = {
            str(item["station_id"]): item["name"] for item in stations_data
        }

        station_ids = [item["station_id"] for item in stations_data]
        positions = [[item["lat"], item["lon"]] for item in stations_data]
        distances = haversine_distance(
            source_lat=locations_lat_lon["lat"],
            source_lon=locations_lat_lon["lng"],
            targets_latlon=positions,
        )
        sorted_distances = [
            (sid, dist) for sid, dist in zip(station_ids, distances.tolist())
        ]
        sorted_distances.sort(key=lambda x: x[1])
        nearest_station = {
            "name": station_names_by_id[str(sorted_distances[0][0])],
            "id": str(sorted_distances[0][0]),
            "distance_km": sorted_distances[0][1],
        }
        return nearest_station


def get_remaining_bikes(station_id: str) -> Dict[str, Any]:
    try:
        resp = httpx.get(url=VELIB_SERVICE_URL)
        station_live_data = resp.json().get("data").get("stations")
        station_live_availability_by_id = {
            str(item["station_id"]): item["numBikesAvailable"]
            for item in station_live_data
        }
        return {"nb_remaining_bikes": station_live_availability_by_id[station_id]}

    except httpx.HTTPStatusError as exc:
        print(
            f"Request failed with status code {exc.response.status_code}: {exc.response.text}"
        )
    except httpx.RequestError as exc:
        print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
    except Exception as exc:
        print(f"An unexpected error occurred: {exc}")
        raise


def get_biking_itinerary(
    origin_address: str, destination_address: str
) -> Dict[str, Any]:
    origin_lat_lon = _geocode(origin_address)
    destination_lat_lon = _geocode(destination_address)
    try:
        url = GOOGLE_ROUTES_API_ENDPOINT
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": os.getenv("GOOGLE_ROUTES_API_KEY"),
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.legs",
        }
        payload = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": origin_lat_lon["lat"],
                        "longitude": origin_lat_lon["lng"],
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": destination_lat_lon["lat"],
                        "longitude": destination_lat_lon["lng"],
                    }
                }
            },
            "travelMode": "BICYCLE",
            "languageCode": "fr",
            "units": "METRIC",
        }
        resp = httpx.post(url=url, headers=headers, json=payload)
        resp.raise_for_status()
        resp_json = resp.json()
        route = resp_json["routes"][0]
        # Itinerary
        itinerary = _parse_legs(route["legs"])
        # Distance + duration
        distance_km = float(format(route["distanceMeters"] / 1000.0, ".2f"))
        duration_min = to_minutes(route["duration"])
        return {
            "itinerary": itinerary,
            "distance_km": distance_km,
            "duration_min": duration_min,
        }
    except httpx.HTTPStatusError as exc:
        print(
            f"Request failed with status code {exc.response.status_code}: {exc.response.text}"
        )
    except httpx.RequestError as exc:
        print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
    except Exception as exc:
        print(f"An unexpected error occurred: {exc}")


tool_map = {
    "get_weather": get_weather,
    "get_nearest_velib_station": get_nearest_velib_station,
    "get_remaining_bikes": get_remaining_bikes,
    "get_biking_itinerary": get_biking_itinerary,
}
