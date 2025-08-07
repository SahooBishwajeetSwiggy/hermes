from fastapi import APIRouter, HTTPException, Body
from typing import List
import uuid
from datetime import datetime, timezone

from app.api.models.vehicles import Vehicle, VehicleCreate, VehicleUpdate
from app.db.json_db import JsonDB

router = APIRouter()
db = JsonDB()

@router.post("/", response_model=Vehicle)
async def create_vehicle(vehicle: VehicleCreate):
    vehicle_data = vehicle.dict()
    vehicle_data["id"] = str(uuid.uuid4())
    vehicle_data["created_at"] = datetime.now(timezone.utc)
    vehicle_data["updated_at"] = datetime.now(timezone.utc)
    
    # Set initial capacity based on vehicle type from config
    vehicle_types_config = {
        "EV_3W": 450,
        "TATA_ACE_4W": 900,
        "BIKE_2W": 20
    }
    vehicle_data["current_capacity"] = vehicle_types_config.get(vehicle_data["vehicle_type"])
    
    result = db.insert_one("vehicles", vehicle_data)
    return result

@router.get("/", response_model=List[Vehicle])
async def list_vehicles():
    return db.find_all("vehicles")

@router.get("/{vehicle_id}", response_model=Vehicle)
async def get_vehicle(vehicle_id: str):
    vehicle = db.find_one("vehicles", {"id": vehicle_id})
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle

@router.put("/{vehicle_id}", response_model=Vehicle)
async def update_vehicle(vehicle_id: str, vehicle: VehicleUpdate):
    update_data = vehicle.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = db.update_one("vehicles", {"id": vehicle_id}, update_data)
    if not result:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return result

@router.delete("/{vehicle_id}")
async def delete_vehicle(vehicle_id: str):
    success = db.delete_one("vehicles", {"id": vehicle_id})
    if not success:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return {"message": "Vehicle deleted successfully"}
