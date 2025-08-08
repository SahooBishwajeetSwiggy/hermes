from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class UserBase(BaseModel):
    """
    Base model for User with common attributes
    """
    email: EmailStr = Field(...,
        description="User's email address",
        example="user@example.com")
    username: str = Field(...,
        description="Unique username for the user",
        example="john_doe")
    full_name: str = Field(...,
        description="User's full name",
        example="John Doe")

class UserCreate(UserBase):
    """
    Model for creating a new user (registration)
    """
    password: str = Field(...,
        description="Password for the account (min length 8)",
        min_length=8,
        example="strongP@ssword123")

class UserResponse(UserBase):
    """
    Complete user model returned by the API
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the user")
    role: UserRole = Field(default=UserRole.USER,
        description="Role of the user (set by system)")
    assigned_warehouses: List[str] = Field(default_factory=list,
        description="List of warehouse IDs assigned to the user")
    active_warehouse_id: Optional[str] = Field(None,
        description="Currently active warehouse ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the user was created")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the user was last updated")

class UserUpdate(BaseModel):
    """
    Model for updating user information
    """
    full_name: Optional[str] = Field(None,
        description="Updated full name of the user")
    password: Optional[str] = Field(None,
        description="Updated password for the account")
    assigned_warehouses: Optional[List[str]] = Field(None,
        description="Updated list of assigned warehouses")
    active_warehouse_id: Optional[str] = Field(None,
        description="Updated active warehouse ID")

class UserLogin(BaseModel):
    """
    Model for user login
    """
    email: EmailStr
    password: str = Field(...,
        description="Password for the account",
        min_length=8,
        example="strongP@ssword123")

class Token(BaseModel):
    """
    Model for JWT token
    """
    access_token: str
    token_type: str = "bearer"
