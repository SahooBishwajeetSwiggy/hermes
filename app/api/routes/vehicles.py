from fastapi import APIRouter, HTTPException, Body, Depends
from typing import List
import uuid
from datetime import datetime, timezone

from app.api.models.vehicles import Vehicle, VehicleCreate, VehicleUpdate
from app.db.json_db import JsonDB
from app.api.auth.permissions import verify_admin_or_warehouse_access, verify_vehicle_access
from app.api.routes.auth import get_current_user
from app.api.models.users import UserResponse, UserRole

router = APIRouter()
db = JsonDB()

@router.post("/", response_model=Vehicle)
async def create_vehicle(
    vehicle: VehicleCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    if current_user.role != UserRole.ADMIN and vehicle.warehouse_id not in current_user.assigned_warehouses:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this warehouse"
        )

    warehouse = db.find_one("warehouses", {"id": vehicle.warehouse_id})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    vehicle_data = vehicle.dict()
    vehicle_data["id"] = str(uuid.uuid4())
    vehicle_data["created_at"] = datetime.now(timezone.utc)
    vehicle_data["updated_at"] = datetime.now(timezone.utc)
    
    global_config = db.yaml_config.get_global_config()
    if vehicle.vehicle_type not in global_config.get("vehicle_types", {}):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid vehicle type. Must be one of: {list(global_config['vehicle_types'].keys())}"
        )
    
    result = db.insert_one("vehicles", vehicle_data)
    
    db.yaml_config.update_warehouse_config(vehicle.warehouse_id, db)
    
    return result

@router.get("/", response_model=List[Vehicle])
async def list_all_vehicles(current_user: UserResponse = Depends(get_current_user)):
    vehicles = db.find_all("vehicles")
    return vehicles

@router.get("/assigned", response_model=List[Vehicle])
async def list_assigned_vehicles(current_user: UserResponse = Depends(get_current_user)):
    vehicles = db.find_all("vehicles")
    if current_user.role != UserRole.ADMIN:
        # Filter vehicles based on user's warehouse access
        vehicles = [v for v in vehicles if v["warehouse_id"] in current_user.assigned_warehouses]
    return vehicles

@router.get("/{vehicle_id}", response_model=Vehicle)
async def get_vehicle(vehicle_id: str):
    vehicle = db.find_one("vehicles", {"id": vehicle_id})
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle

@router.put("/{vehicle_id}", response_model=Vehicle)
async def update_vehicle(
    vehicle_id: str,
    vehicle: VehicleUpdate,
    _: None = Depends(verify_vehicle_access)
):
    current_vehicle = db.find_one("vehicles", {"id": vehicle_id})
    if not current_vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    update_data = vehicle.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)

    global_config = db.yaml_config.get_global_config()

    if vehicle.vehicle_type and vehicle.vehicle_type not in global_config.get("vehicle_types", {}):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid vehicle type. Must be one of: {list(global_config['vehicle_types'].keys())}"
        )
    
    result = db.update_one("vehicles", {"id": vehicle_id}, update_data)
    if not result:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Update both old and new warehouse configs if warehouse changed
    if "warehouse_id" in update_data and update_data["warehouse_id"] != current_vehicle["warehouse_id"]:
        db.yaml_config.update_warehouse_config(current_vehicle["warehouse_id"], db)
        db.yaml_config.update_warehouse_config(update_data["warehouse_id"], db)
    else:
        db.yaml_config.update_warehouse_config(current_vehicle["warehouse_id"], db)
    
    return result

@router.delete("/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: str,
    _: None = Depends(verify_vehicle_access)
):
    vehicle = db.find_one("vehicles", {"id": vehicle_id})
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    warehouse_id = vehicle["warehouse_id"]
    
    success = db.delete_one("vehicles", {"id": vehicle_id})
    if not success:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    db.yaml_config.update_warehouse_config(warehouse_id, db)

    return {"message": "Vehicle deleted successfully"}
