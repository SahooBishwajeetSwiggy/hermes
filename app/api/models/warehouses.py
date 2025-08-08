from pydantic import BaseModel, Field, field_validator, conint, confloat
from typing import List, Optional, Dict
from datetime import datetime, time, timezone
import uuid

class TimeWindow(BaseModel):
    """
    Model for representing operating time windows
    """
    start: time = Field(..., 
        description="Start time of operations",
        example="09:00")
    end: time = Field(..., 
        description="End time of operations",
        example="18:00")

    class Config:
        schema_extra = {
            "example": {
                "start": "09:00",
                "end": "18:00"
            }
        }

class WarehouseConfig(BaseModel):
    """
    Model for warehouse-specific configuration
    """
    average_speed: int = Field(10,
        description="Average vehicle speed in km/h",
        gt=0)
    depot_index: int = Field(0,
        description="Index of depot location",
        ge=0)
    enable_time_windows: bool = Field(True,
        description="Whether to enable time window constraints")
    service_time: int = Field(5,
        description="Service time in minutes",
        gt=0)

    @field_validator('average_speed')
    def validate_speed(cls, v):
        if v <= 0:
            raise ValueError("Average speed must be greater than 0")
        return v

    @field_validator('service_time')
    def validate_times(cls, v):
        if v <= 0:
            raise ValueError("Time values must be greater than 0")
        return v

class WarehouseBase(BaseModel):
    """
    Base model for Warehouse with common attributes
    """
    name: str = Field(..., 
        description="Name of the warehouse",
        example="Main Depot")
    address: str = Field(..., 
        description="Full address of the warehouse",
        example="123 Main St, Bangalore, Karnataka")
    latitude: float = Field(..., 
        description="Latitude coordinate of the warehouse",
        example=12.9716)
    longitude: float = Field(..., 
        description="Longitude coordinate of the warehouse",
        example=77.5946)
    contact_number: Optional[str] = Field(None, 
        description="Contact number for the warehouse",
        example="+91-9876543210")
    operating_hours: TimeWindow = Field(
        default=TimeWindow(
            start=time(9, 0),
            end=time(18, 0)
        ),
        description="Operating hours of the warehouse"
    )
    config: Optional[WarehouseConfig] = Field(
        default=WarehouseConfig(),
        description="Warehouse-specific configuration"
    )

    class Config:
        schema_extra = {
            "example": {
                "name": "Main Depot",
                "address": "123 Main St, Bangalore, Karnataka",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "contact_number": "+91-9876543210",
                "operating_hours": {
                    "start": "09:00",
                    "end": "18:00"
                },
                "config": {
                    "average_speed": 10.0,
                    "depot_index": 0,
                    "enable_time_windows": True,
                    "service_time": 5,
                }
            }
        }

class WarehouseCreate(WarehouseBase):
    """
    Model for creating a new warehouse
    """
    pass

class Warehouse(WarehouseBase):
    """
    Complete warehouse model with system fields
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the warehouse")
    created_at: datetime = Field(default_factory=datetime.now(timezone.utc),
        description="Timestamp when the warehouse was created")
    updated_at: datetime = Field(default_factory=datetime.now(timezone.utc),
        description="Timestamp when the warehouse was last updated")

class WarehouseUpdate(BaseModel):
    """
    Model for updating warehouse information
    """
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contact_number: Optional[str] = None
    operating_hours: Optional[TimeWindow] = None
    config: Optional[WarehouseConfig] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Depot Name",
                "operating_hours": {
                    "start": "08:00",
                    "end": "20:00"
                }
            }
        }
