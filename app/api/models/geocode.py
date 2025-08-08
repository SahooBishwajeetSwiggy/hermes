from pydantic import BaseModel

class GeocodeRequest(BaseModel):
    address: str

class ReverseGeocodeRequest(BaseModel):
    latitude: float
    longitude: float