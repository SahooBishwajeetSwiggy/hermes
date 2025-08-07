from fastapi import APIRouter, HTTPException, Body
from typing import List
import uuid
from datetime import datetime, timezone

from app.api.models.warehouses import Warehouse, WarehouseCreate, WarehouseUpdate
from app.db.json_db import JsonDB

router = APIRouter()
db = JsonDB()

@router.post("/", response_model=Warehouse)
async def create_warehouse(warehouse: WarehouseCreate):
    warehouse_data = warehouse.dict()
    warehouse_data["id"] = str(uuid.uuid4())
    warehouse_data["created_at"] = datetime.now(timezone.utc)
    warehouse_data["updated_at"] = datetime.now(timezone.utc)
    
    result = db.insert_one("warehouses", warehouse_data)
    
    db.yaml_config.update_warehouse_config(result["id"], db)
    
    return result

@router.get("/", response_model=List[Warehouse])
async def list_warehouses():
    return db.find_all("warehouses")

@router.get("/{warehouse_id}", response_model=Warehouse)
async def get_warehouse(warehouse_id: str):
    warehouse = db.find_one("warehouses", {"id": warehouse_id})
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse

@router.put("/{warehouse_id}", response_model=Warehouse)
async def update_warehouse(warehouse_id: str, warehouse: WarehouseUpdate):
    update_data = warehouse.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = db.update_one("warehouses", {"id": warehouse_id}, update_data)
    if not result:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    if "config" in update_data or "operating_hours" in update_data:
        db.yaml_config.update_warehouse_config(warehouse_id, db)
    
    return result

@router.delete("/{warehouse_id}")
async def delete_warehouse(warehouse_id: str):
    success = db.delete_one("warehouses", {"id": warehouse_id})

    if not success:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    else:
        db.yaml_config._delete_warehouse_config(warehouse_id)
    return {"message": "Warehouse deleted successfully"}
