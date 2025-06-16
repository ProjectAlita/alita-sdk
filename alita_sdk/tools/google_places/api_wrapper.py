import logging
from typing import Any, Dict, List, Optional

import googlemaps
from pydantic import create_model, Field, field_validator, PrivateAttr, SecretStr

from ..elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)


# TODO: review langchain-google-community: places_api.py
class GooglePlacesAPIWrapper(BaseToolApiWrapper):
    api_key: Optional[SecretStr] = None
    results_count: Optional[int] = None
    _client: Optional[googlemaps.Client] = PrivateAttr()

    @field_validator('api_key', mode="before")
    @classmethod
    def validate_toolkit(cls, api_key: Optional[str]) -> Optional[str]:
        if api_key:
            cls._client = googlemaps.Client(key=api_key)
        return api_key

    def places(self, query: str) -> str:
        """Retrieve places based on a query using Google Places API."""
        client_places = self._client.places(query) if self._client else {}
        search_results = client_places.get("results", [])
        num_to_return = len(search_results)

        if num_to_return == 0:
            return "Google Places did not find any places that match the description."

        num_to_return = min(num_to_return, self.results_count) if self.results_count else num_to_return

        places: List[str] = [
            self.fetch_place_details(result["place_id"])
            for result in search_results[:num_to_return]
            if self.fetch_place_details(result["place_id"]) is not None
        ]

        return "\n".join([f"{i + 1}. {place}" for i, place in enumerate(places)])

    def find_near(self, current_location_query: str, target: str, radius: Optional[int] = 3000) -> str:
        """Find places near a specific location using Google Places API."""
        logger.info(f"Google Places API query: {current_location_query}, target: {target}, radius: {radius}")
        if not self._client:
            return "Google Maps client is not initialized."

        geocode_result = self._client.geocode(current_location_query)
        if not geocode_result:
            return f"Provided current location {current_location_query} is not found."

        location = geocode_result[0].get('geometry', {}).get('location', {})
        nearby_places = self._client.places_nearby(location=location, keyword=target, radius=radius)
        return str(nearby_places.get('results', []))

    def fetch_place_details(self, place_id: str) -> Optional[str]:
        """Fetch detailed information about a place using its place ID."""
        if not self._client:
            logging.error("Google Maps client is not initialized.")
            return None

        try:
            place_details = self._client.place(place_id)
            formatted_details = self.format_place_details(place_details)
            return formatted_details
        except Exception as e:
            logging.error(f"Error fetching place details for place_id {place_id}: {e}")
            return None

    @staticmethod
    def format_place_details(place_details: Dict[str, Any]) -> Optional[str]:
        result = place_details.get("result", {})
        name = result.get("name", "Unknown")
        address = result.get("formatted_address", "Unknown")
        phone_number = result.get("formatted_phone_number", "Unknown")
        website = result.get("website", "Unknown")
        place_id = result.get("place_id", "Unknown")

        formatted_details = (
            f"{name}\nAddress: {address}\n"
            f"Google place ID: {place_id}\n"
            f"Phone: {phone_number}\nWebsite: {website}\n\n"
        )
        return formatted_details

    def get_available_tools(self):
        return [
            {
                "name": "places",
                "ref": self.places,
                "description": self.places.__doc__,
                "args_schema": create_model(
                    "GooglePlacesSchema",
                    query=(str, Field(description="Query for google maps"))
                ),
            },
            {
                "name": "find_near",
                "ref": self.find_near,
                "description": self.find_near.__doc__,
                "args_schema": create_model(
                    "GooglePlacesFindNearSchema",
                    current_location_query=(
                    str, Field(description="Detailed user query of current user location or where to start from")),
                    target=(str, Field(description="The target location or query which user wants to find", default=None)),
                    radius=(Optional[int], Field(description="The radius of the search. This is optional field", default=3000))
                ),
            }
        ]