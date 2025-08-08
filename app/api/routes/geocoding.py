from fastapi import APIRouter, HTTPException, Query
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError

from app.api.models.geocode import GeocodeRequest, ReverseGeocodeRequest

router = APIRouter()
geolocator = Nominatim(user_agent="route_planner_geocoding")

@router.post("/geocode")
async def geocode(request: GeocodeRequest):
    try:
        location = geolocator.geocode(request.address)
        if not location:
            raise HTTPException(status_code=404, detail="Address not found")
        return {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "address": location.address
        }
    except GeocoderServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reverse-geocode")
async def reverse_geocode(request: ReverseGeocodeRequest):
    try:
        location = geolocator.reverse((request.latitude, request.longitude), exactly_one=True)
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
        return {
            "address": location.address,
            "latitude": location.latitude,
            "longitude": location.longitude
        }
    except GeocoderServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))