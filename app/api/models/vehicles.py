from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Set
from datetime import datetime, timezone
import uuid
from app.db.json_db import JsonDB

def get_vehicle_types() -> Set[str]:
    """Get the list of available vehicle types from global config"""
    db = JsonDB()
    global_config = db.yaml_config.get_global_config()
    return set(global_config.get('vehicle_types', {}).keys())

class VehicleBase(BaseModel):
    """
    Base model for Vehicle with common attributes
    """
    name: str = Field(..., 
        description="Name or identifier of the vehicle",
        example="Vehicle-001")
    vehicle_type: str = Field(..., 
        description="Type of vehicle (EV_3W, TATA_ACE_4W, BIKE_2W)",
        example="EV_3W")
    warehouse_id: str = Field(...,
        description="ID of the warehouse this vehicle is assigned to")
    registration_number: str = Field(..., 
        description="Vehicle registration number",
        example="KA01AB1234")
    driver_name: Optional[str] = Field(None, 
        description="Name of the assigned driver",
        example="John Doe")
    driver_contact: Optional[str] = Field(None, 
        description="Contact number of the driver",
        example="+91-9876543210")
    availability_status: bool = Field(True, 
        description="Whether the vehicle is currently available")
    total_distance_today: float = Field(0.0,
        description="Total distance covered today in meters",
        example=0.0)

    @field_validator('vehicle_type')
    def validate_vehicle_type(cls, v):
        allowed_types = get_vehicle_types()
        if v not in allowed_types:
            raise ValueError(f"Invalid vehicle type. Must be one of: {list(allowed_types)}")
        return v

    class Config:
        schema_extra = {
            "example": {
                "name": "EV-001",
                "vehicle_type": "EV_3W",
                "registration_number": "KA01AB1234",
                "driver_name": "John Doe",
                "driver_contact": "+91-9876543210",
                "availability_status": True,
                "current_capacity": 450.0,
                "total_distance_today": 0.0
            }
        }

class VehicleCreate(VehicleBase):
    """
    Model for creating a new vehicle
    """
    pass

class Vehicle(VehicleBase):
    """
    Complete vehicle model with system fields
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the vehicle")
    created_at: datetime = Field(default_factory=datetime.now(timezone.utc),
        description="Timestamp when the vehicle was created")
    updated_at: datetime = Field(default_factory=datetime.now(timezone.utc),
        description="Timestamp when the vehicle was last updated")

class VehicleUpdate(BaseModel):
    """
    Model for updating vehicle information
    """
    name: Optional[str] = None
    vehicle_type: Optional[str] = None
    registration_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_contact: Optional[str] = None
    availability_status: Optional[bool] = None
    current_capacity: Optional[float] = None
    total_distance_today: Optional[float] = None

    class Config:
        schema_extra = {
            "example": {
                "driver_name": "Jane Doe",
                "availability_status": False
            }
        }
