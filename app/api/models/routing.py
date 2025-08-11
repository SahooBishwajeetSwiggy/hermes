from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Union, Annotated
import re

class FieldMapping(BaseModel):
    id: str = Field("Order ID", description="Order ID")
    od: str = Field("Order Date", description="Order Date")
    loc: str = Field("Location ID", description="Location ID")
    ed: str = Field("Customer Execution Date", description="Customer Execution Date")
    st: str = Field("Customer Slot Start", description="Customer Slot Start")
    et: str = Field("Customer Slot End", description="Customer Slot End")
    lat: str = Field("Customer Location Latitude", description="Customer Location Latitude")
    lng: str = Field("Customer Location Longitude", description="Customer Location Longitude")
    amt: str = Field("Amount", description="Amount")
    wt: str = Field("Weight", description="Weight")
    wu: str = Field("Weight Unit", description="Weight Unit")
    pd: str = Field("Customer Promised Date", description="Customer Promised Date")
    sid: str = Field("Slot ID", description="Slot ID")
    sz: str = Field("Size", description="Size")


class DeliveryBase(BaseModel):
    id: str = Field(..., description="Order ID")
    od: str = Field(..., description="Order Date and Time (DD/MM/YY HH:MM)")
    loc: str = Field(..., description="Location ID")
    ed: str = Field(..., description="Customer Execution Date (DD/MM/YY)")
    st: str = Field(..., description="Customer Slot Start (DD/MM/YY HH:MM)")
    et: str = Field(..., description="Customer Slot End (DD/MM/YY HH:MM)")
    lat: Annotated[float, Field(strict=True, ge=-90, le=90)] = Field(..., description="Latitude")
    lng: Annotated[float, Field(strict=True, ge=-180, le=180)] = Field(..., description="Longitude")
    amt: str = Field(..., description="Order amount as string")
    wt: float = Field(..., description="Weight")
    wu: str = Field(..., description="Weight Unit (e.g., KG)")
    pd: str = Field(..., description="Promised Delivery Date (DD/MM/YY)")
    sid: Optional[Union[str, int]] = Field("", description="Slot ID if available")
    sz: Annotated[int, Field(strict=True, ge=0)] = Field(..., description="Size indicator")


class DeliveryInput(DeliveryBase):
    pass


class DeliveryOutput(DeliveryBase):
    vehicle_id: int = Field(..., description="Assigned vehicle ID")
    vehicle_type: str = Field(..., description="Assigned vehicle type")
    planned_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")] = Field(..., description="Planned delivery time")


class RoutingInput(BaseModel):
    fields: FieldMapping = Field(default_factory=FieldMapping)
    deliveries: List[DeliveryInput]


class RouteStop(BaseModel):
    location: str
    arrival_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")]
    departure_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")]


class VehicleRoute(BaseModel):
    sequence: List[str]
    start_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")]
    end_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")]
    stops: List[RouteStop]

    @field_validator("stops", mode="before")
    def parse_stops(cls, v):
        parsed = []
        for stop in v:
            if isinstance(stop, str):
                m = re.match(r"^(.+?)\((\d{1,2}:\d{2})-(\d{1,2}:\d{2})\)$", stop)
                if not m:
                    raise ValueError(f"Invalid stop format: {stop}")
                parsed.append({
                    "location": m.group(1),
                    "arrival_time": m.group(2),
                    "departure_time": m.group(3)
                })
            else:
                parsed.append(stop)
        return parsed

class VehicleOutput(BaseModel):
    vehicle_id: int
    vehicle_type: str
    total_load: float
    total_distance: float
    delivery_ids: List[str]
    route: VehicleRoute


class RoutingSolutionOutput(BaseModel):
    fields: FieldMapping = Field(default_factory=FieldMapping)
    deliveries: List[DeliveryOutput]
    vehicles: List[VehicleOutput]
    report: str
    dropped_deliveries: List[DeliveryInput]
