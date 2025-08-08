from fastapi import Depends, HTTPException, status
from typing import Optional

from app.db.json_db import JsonDB
from ..routes.auth import get_current_user
from ..models.users import UserResponse, UserRole

db = JsonDB()

async def verify_admin_or_warehouse_access(
    warehouse_id: str,
    current_user: UserResponse = Depends(get_current_user)
) -> None:
    """
    Verify if user is admin or has access to the specified warehouse
    Raises HTTPException if user doesn't have access
    """
    if current_user.role != UserRole.ADMIN and warehouse_id not in current_user.assigned_warehouses:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this warehouse"
        )

# Dependency for admin-only routes
async def verify_admin(
    current_user: UserResponse = Depends(get_current_user)
) -> None:
    """
    Verify if user is an admin
    Raises HTTPException if user is not an admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

# Custom dependency for vehicle operations
async def verify_vehicle_access(
    vehicle_id: str,
    current_user: UserResponse = Depends(get_current_user)
) -> None:
    """
    Verify if user has access to manage the specified vehicle
    Raises HTTPException if user doesn't have access
    """
    vehicle = db.find_one("vehicles", {"id": vehicle_id})
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    
    if current_user.role != UserRole.ADMIN and vehicle["warehouse_id"] not in current_user.assigned_warehouses:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this vehicle"
        )
