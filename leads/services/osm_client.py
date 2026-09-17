"""
OpenStreetMap Client Service

Handles geocoding via Nominatim and business search via Overpass API.
"""
import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Configuration
USER_AGENT = getattr(settings, 'OSM_USER_AGENT', 'website-gap-finder/1.0')
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

COUNTRY_TO_REGION = {
    "germany": "DE", "deutschland": "DE", "de": "DE",
    "uk": "GB", "united kingdom": "GB", "england": "GB",
    "scotland": "GB", "wales": "GB", "northern ireland": "GB", "gb": "GB",
    "australia": "AU", "au": "AU",
    "usa": "US", "united states": "US", "us": "US",
    "canada": "CA", "ca": "CA",
    "france": "FR", "fr": "FR",
    "spain": "ES", "es": "ES",
    "italy": "IT", "it": "IT",
    "netherlands": "NL", "nl": "NL",
    "belgium": "BE", "be": "BE",
    "switzerland": "CH", "ch": "CH",
    "austria": "AT", "at": "AT",
    "poland": "PL", "pl": "PL",
    "sweden": "SE", "se": "SE",
    "norway": "NO", "no": "NO",
    "denmark": "DK", "dk": "DK",
    "finland": "FI", "fi": "FI",
    "ireland": "IE", "ie": "IE",
    "portugal": "PT", "pt": "PT",
    "greece": "GR", "gr": "GR",
    "japan": "JP", "jp": "JP",
    "singapore": "SG", "sg": "SG",
    "hong kong": "HK", "hk": "HK",
    "new zealand": "NZ", "nz": "NZ",
}

CATEGORY_TAG_ALIASES = {
    "hair salon": "hairdresser", "hairdresser": "hairdresser", "barber": "hairdresser",
    "beauty salon": "beauty", "nail salon": "beauty",
    "gym": "fitness_centre", "fitness": "fitness_centre",
    "lawyer": "lawyer", "law firm": "lawyer", "solicitor": "lawyer",
    "accountant": "accountant",
    "estate agent": "estate_agent", "real estate agent": "estate_agent", "realtor": "estate_agent",
    "dentist": "dentist", "doctor": "doctors", "gp": "doctors",
    "vet": "veterinary", "veterinarian": "veterinary",
    "car repair": "car_repair", "mechanic": "car_repair", "garage": "car_repair",
    "plumber": "plumber", "electrician": "electrician", "carpenter": "carpenter", "painter": "painter",
    "cafe": "cafe", "coffee shop": "cafe",
    "restaurant": "restaurant", "takeaway": "fast_food", "fast food": "fast_food",
    "bakery": "bakery", "butcher": "butcher",
    "pharmacy": "pharmacy", "chemist": "pharmacy",
    "bar": "bar", "pub": "pub",
    "hotel": "hotel", "guesthouse": "guest_house",
    "supermarket": "supermarket", "florist": "florist",
    "tailor": "tailor", "locksmith": "locksmith",
    "cleaner": "cleaning", "cleaning service": "cleaning",
}

TAG_FAMILIES = ["shop", "amenity", "craft", "office", "leisure", "tourism"]


class OSMClient:
    """Client for interacting with OpenStreetMap APIs."""

    def __init__(self, contact_email: Optional[str] = None):
        self.contact_email = contact_email or getattr(settings, 'OSM_CONTACT_EMAIL', '')
        self.user_agent = f"website-gap-finder/1.0 (contact: {self.contact_email})" if self.contact_email else USER_AGENT

    def geocode_city(self, city: str, country: str) -> tuple[str, str, str, str]:
        """
        Get bounding box for a city.

        Returns:
            tuple: (south, west, north, east) as strings
        """
        query = f"{city}, {country}" if country else city
        params = {"q": query, "format": "json", "limit": 1}
        url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if not data:
            raise ValueError(f"Could not find '{query}' on OpenStreetMap. Check spelling.")

        south, north, west, east = data[0]["boundingbox"]
        logger.info(f"Geocoded '{query}' to bbox: {south},{west},{north},{east}")
        return south, west, north, east

    def resolve_tag_value(self, category: str) -> str:
        """Resolve category name to OSM tag value."""
        key = category.strip().lower()
        return CATEGORY_TAG_ALIASES.get(key, key.replace(" ", "_"))

    def build_overpass_query(self, bbox: tuple, category_raw: str) -> str:
        """Build Overpass QL query for a category within bbox."""
        s, w, n, e = bbox
        bbox_str = f"{s},{w},{n},{e}"
        slug = self.resolve_tag_value(category_raw)
        safe_name = category_raw.replace('"', "").strip()

        tag_clauses = "\n  ".join(
            f'nwr["{fam}"="{slug}"]({bbox_str});' for fam in TAG_FAMILIES
        )
        name_clause = (
            f'nwr["name"~"{safe_name}",i]({bbox_str});' if safe_name else ""
        )

        return f"""[out:json][timeout:90];
(
  {tag_clauses}
  {name_clause}
);
out center tags;""".strip()

    def query_overpass(self, query: str) -> dict:
        """Execute Overpass query with fallback endpoints."""
        last_err = None
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                data = urllib.parse.urlencode({"data": query}).encode("utf-8")
                req = urllib.request.Request(
                    endpoint, data=data, headers={"User-Agent": self.user_agent}
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                last_err = e
                logger.warning(f"Overpass endpoint {endpoint} failed: {e}")
                continue
        raise RuntimeError(f"All Overpass mirrors failed. Last error: {last_err}")

    def parse_element(self, el: dict) -> Optional[dict]:
        """Parse OSM element to extract business info."""
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            return None

        center = el.get("center", {})
        lat = el.get("lat", center.get("lat"))
        lon = el.get("lon", center.get("lon"))

        street_line = " ".join(
            p for p in [tags.get("addr:housenumber", ""), tags.get("addr:street", "")] if p
        )
        full_address = ", ".join(
            p
            for p in [
                street_line,
                tags.get("addr:postcode", ""),
                tags.get("addr:city", ""),
            ]
            if p
        )

        phone = (
            tags.get("phone")
            or tags.get("contact:phone")
            or tags.get("contact:mobile")
            or tags.get("mobile")
            or ""
        ).strip()
        website = (
            tags.get("website")
            or tags.get("contact:website")
            or ""
        ).strip()

        return {
            "osm_id": f"{el.get('type')}/{el.get('id')}",
            "name": name,
            "address": full_address,
            "phone": phone,
            "website": website,
            "lat": lat,
            "lon": lon,
        }

    def search_category(self, bbox: tuple, category: str) -> list[dict]:
        """Search for businesses in a category within bbox."""
        query = self.build_overpass_query(bbox, category)
        data = self.query_overpass(query)
        elements = data.get("elements", [])

        results = []
        for el in elements:
            parsed = self.parse_element(el)
            if parsed:
                results.append(parsed)
        return results