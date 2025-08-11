from fastapi import APIRouter, HTTPException, Body, Depends
from typing import List
import uuid
from datetime import datetime, timezone
from copy import deepcopy

from app.api.models.warehouses import Warehouse, WarehouseCreate, WarehouseUpdate
from app.db.json_db import JsonDB
from app.api.auth.permissions import verify_admin, verify_admin_or_warehouse_access, verify_admin_or_warehouse_access
from app.api.routes.auth import get_current_user
from app.api.models.users import UserResponse, UserRole

router = APIRouter()
db = JsonDB()

@router.post("/", response_model=Warehouse)
async def create_warehouse(
    warehouse: WarehouseCreate,
    _: None = Depends(verify_admin)
):
    warehouse_data = warehouse.dict()
    warehouse_data["id"] = str(uuid.uuid4())
    warehouse_data["created_at"] = datetime.now(timezone.utc)
    warehouse_data["updated_at"] = datetime.now(timezone.utc)
    
    result = db.insert_one("warehouses", warehouse_data)
    
    db.yaml_config.update_warehouse_config(result["id"], db)
    
    return result

@router.get("/", response_model=List[Warehouse])
async def list_warehouses(current_user: UserResponse = Depends(get_current_user)):
    warehouses = db.find_all("warehouses")
    return warehouses

@router.get("/assigned", response_model=List[Warehouse])
async def list_assigned_warehouses(current_user: UserResponse = Depends(get_current_user)):
    warehouses = []
    for warehouse_id in current_user.assigned_warehouses:
        warehouse = db.find_one("warehouses", {"id": warehouse_id})
        if warehouse:
            warehouses.append(warehouse)
    return warehouses

@router.get("/{warehouse_id}", response_model=Warehouse)
async def get_warehouse(warehouse_id: str):
    warehouse = db.find_one("warehouses", {"id": warehouse_id})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse

def deep_update(original: dict, updates: dict) -> dict:
    """
    Recursively update a dict with another dict, only updating provided fields.
    """
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(original.get(k), dict):
            original[k] = deep_update(original.get(k, {}), v)
        else:
            original[k] = v
    return original

@router.put("/{warehouse_id}", response_model=Warehouse)
async def update_warehouse(
    warehouse_id: str,
    warehouse: WarehouseUpdate,
    _: None = Depends(verify_admin_or_warehouse_access)
):
    update_data = warehouse.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)

    # Fetch the existing warehouse
    existing = db.find_one("warehouses", {"id": warehouse_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    # Deep update for nested fields
    updated = deep_update(deepcopy(existing), update_data)

    result = db.update_one("warehouses", {"id": warehouse_id}, updated)
    if not result:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    # Update config in YAML if relevant fields changed
    if "city" in update_data or "config" in update_data or "operating_hours" in update_data or "latitude" in update_data or "longitude" in update_data:
        db.yaml_config.update_warehouse_config(warehouse_id, db)
    
    return result

@router.delete("/{warehouse_id}")
async def delete_warehouse(
    warehouse_id: str,
    _: None = Depends(verify_admin)
):
    success = db.delete_one("warehouses", {"id": warehouse_id})

    if not success:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    else:
        db.yaml_config._delete_warehouse_config(warehouse_id)

        # Remove warehouse id from users' assigned warehouses
        users = db.find_all("users")
        updated = False
        for user in users:
            if "assigned_warehouses" in user and warehouse_id in user["assigned_warehouses"]:
                user["assigned_warehouses"].remove(warehouse_id)
                updated = True
        if updated:
            db._write_collection("users", users)
        
    return {"message": "Warehouse deleted successfully"}
