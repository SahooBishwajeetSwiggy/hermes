import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from typing import List, Optional
from ..models.users import UserCreate, UserResponse, UserLogin, Token, UserRole
from ..models.warehouses import Warehouse
from ..auth.utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    verify_token
)
from ...db.json_db import JsonDB

router = APIRouter()
db = JsonDB()
bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> UserResponse:
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    user = db.find_one("users", {"id": payload.get("sub")})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return UserResponse(**user)

async def get_current_admin(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    if db.find_one("users", {"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    user_dict = user.model_dump()
    user_dict["id"] = str(uuid.uuid4())
    user_dict["password"] = get_password_hash(user_dict["password"])
    user_dict["role"] = UserRole.USER
    user_dict["assigned_warehouses"] = []
    user_dict["active_warehouse_id"] = None

    created_user = db.insert_one("users", user_dict)
    return UserResponse(**created_user)

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    user = db.find_one("users", {"email": credentials.email})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(data={"sub": user["id"]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/select-warehouse/{warehouse_id}")
async def select_warehouse(
    warehouse_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    # Verify warehouse exists and user has access
    warehouse = db.find_one("warehouses", {"id": warehouse_id})
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found"
        )
    
    if warehouse_id not in current_user.assigned_warehouses:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this warehouse"
        )
    
    # Update user's active warehouse
    updated_user = db.update_one(
        "users",
        {"id": current_user.id},
        {"active_warehouse_id": warehouse_id}
    )
    
    return {"message": "Warehouse selected successfully"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    return current_user

