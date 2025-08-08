from fastapi import APIRouter, HTTPException, Body, Depends
from typing import Dict, List, Union
from pathlib import Path

from app.db.json_db import JsonDB
from pydantic import BaseModel
from app.api.auth.permissions import verify_admin, verify_admin_or_warehouse_access
from app.api.routes.auth import get_current_user
from app.api.models.users import UserResponse, UserRole

class GlobalConfig(BaseModel):
    vehicle_types: Dict
    auth: Dict

router = APIRouter()
db = JsonDB()

@router.get("/global")
async def get_global_config(_: None = Depends(verify_admin)):
    """
    Get global configuration including available vehicle types and default settings
    """
    return db.yaml_config.get_global_config()

@router.get("/warehouses")
async def get_all_warehouse_configs(current_user: UserResponse = Depends(get_current_user)):
    """
    Get configurations for all warehouses
    """
    configs = db.yaml_config.get_warehouse_config()
    print(configs)
    if current_user.role != UserRole.ADMIN:
        # Filter configs based on user's warehouse access
        configs = [config for config in configs if config.get("warehouse_id") in current_user.assigned_warehouses]
    return configs

@router.get("/warehouses/{warehouse_id}")
async def get_warehouse_config(
    warehouse_id: str,
    _: None = Depends(verify_admin_or_warehouse_access)
):
    """
    Get configuration for a specific warehouse
    """
    config = db.yaml_config.get_warehouse_config(warehouse_id)
    if not config:
        raise HTTPException(status_code=404, detail="Warehouse config not found")
    return config

@router.post("/warehouses/{warehouse_id}/update")
async def update_warehouse_config(
    warehouse_id: str,
    _: None = Depends(verify_admin_or_warehouse_access)
):
    """
    Manually trigger config update for a warehouse.
    Use this to rebuild config if it gets out of sync.
    """
    warehouse = db.find_one("warehouses", {"id": warehouse_id})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    
    config = db.yaml_config.update_warehouse_config(warehouse_id, db)
    if not config:
        raise HTTPException(status_code=500, detail="Failed to update config")
    return config

@router.put("/global", response_model=Dict)
async def update_global_config(
    config: Dict[str, Dict[str, dict]] = Body(...),
    _: None = Depends(verify_admin)
):
    """
    Update the global configuration.
    Expects a simplified schema matching the YAML structure:
    {
        "vehicle_types": {
            "EV_3W": { "capacity": 450, ... },
            ...
        }
    }
    """
    current_config = db.yaml_config.get_global_config()
    current_types = set(current_config.get("vehicle_types", {}).keys())
    new_types = set(config.get("vehicle_types", {}).keys())
    
    # Check for removed vehicle types
    removed_types = current_types - new_types
    if removed_types:
        # Check if any vehicles of removed types exist
        for removed_type in removed_types:
            vehicles = [v for v in db.find_all("vehicles") if v.get("vehicle_type") == removed_type]
            if vehicles:
                warehouses = {v["warehouse_id"]: None for v in vehicles}
                warehouse_names = {w["id"]: w["name"] for w in db.find_all("warehouses") if w["id"] in warehouses}
                detail = f"Cannot remove vehicle type {removed_type}. "
                for v in vehicles:
                    detail += f"\nWarehouse '{warehouse_names.get(v['warehouse_id'])}' has vehicle '{v['name']}' of this type."
                raise HTTPException(status_code=400, detail=detail)

    path = db.yaml_config._get_global_config_path()
    db.yaml_config._write_yaml(path, config)
    
    # Propagate vehicle type updates to all warehouse configs
    for warehouse in db.find_all("warehouses"):
        # Get current warehouse config to preserve vehicle counts
        warehouse_config = db.yaml_config.get_warehouse_config(warehouse["id"])
        db.yaml_config.update_warehouse_config(warehouse["id"], db)
    
    return config
