from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from ..models.users import UserResponse, UserCreate, UserUpdate, UserRole
from ..routes.auth import get_current_admin
from ...db.json_db import JsonDB

router = APIRouter()
db = JsonDB()

@router.get("/users", response_model=List[UserResponse])
async def list_users(current_user: UserResponse = Depends(get_current_admin)):
    users = db.find_all("users")
    return users

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_admin)
):
    user = db.find_one("users", {"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.post("/users", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    current_user: UserResponse = Depends(get_current_admin)
):
    if db.find_one("users", {"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user_dict = user.model_dump()
    created_user = db.insert_one("users", user_dict)
    return UserResponse(**created_user)

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: UserResponse = Depends(get_current_admin)
):
    user = db.find_one("users", {"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = user_update.model_dump(exclude_unset=True)
    
    # Verify warehouses exist
    if "assigned_warehouses" in update_data:
        for warehouse_id in update_data["assigned_warehouses"]:
            warehouse = db.find_one("warehouses", {"id": warehouse_id})
            if not warehouse:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Warehouse {warehouse_id} not found"
                )
    
    updated_user = db.update_one("users", {"id": user_id}, update_data)
    return UserResponse(**updated_user)

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_admin)
):
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    if not db.delete_one("users", {"id": user_id}):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": "User deleted successfully"}

@router.post("/users/{user_id}/warehouses/{warehouse_id}")
async def assign_warehouse(
    user_id: str,
    warehouse_id: str,
    current_user: UserResponse = Depends(get_current_admin)
):
    user = db.find_one("users", {"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    warehouse = db.find_one("warehouses", {"id": warehouse_id})
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found"
        )
    
    assigned_warehouses = set(user.get("assigned_warehouses", []))
    assigned_warehouses.add(warehouse_id)
    
    db.update_one(
        "users",
        {"id": user_id},
        {"assigned_warehouses": list(assigned_warehouses)}
    )
    
    return {"message": "Warehouse assigned successfully"}

@router.delete("/users/{user_id}/warehouses/{warehouse_id}")
async def unassign_warehouse(
    user_id: str,
    warehouse_id: str,
    current_user: UserResponse = Depends(get_current_admin)
):
    user = db.find_one("users", {"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    assigned_warehouses = set(user.get("assigned_warehouses", []))
    if warehouse_id not in assigned_warehouses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Warehouse not assigned to user"
        )
    
    assigned_warehouses.remove(warehouse_id)
    
    # If this was the active warehouse, clear it
    update_data = {"assigned_warehouses": list(assigned_warehouses)}
    if user.get("active_warehouse_id") == warehouse_id:
        update_data["active_warehouse_id"] = None
    
    db.update_one("users", {"id": user_id}, update_data)
    
    return {"message": "Warehouse unassigned successfully"}
