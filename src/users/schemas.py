from pydantic import BaseModel, ConfigDict, EmailStr
from typing import List, Optional

# --- RÔLES ---
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(RoleBase):
    pass

class RoleResponse(RoleBase):
    id: int
    class Config: from_attributes = True

# --- UTILISATEURS ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    first_name: str
    is_active: bool = True

class UserCreate(UserBase):
    password: str
    role_ids: List[int] = [] # Liste des IDs des rôles à assigner
    
    

class UserResponse(UserBase):
    id: int
    roles: List[RoleResponse]
    class Config: from_attributes = True

class UserSelfUpdate(BaseModel):
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    email: Optional[EmailStr] = None
    old_password: Optional[str] = None # Requis pour valider le changement
    new_password: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None 
    role_ids: Optional[List[int]] = None # Liste des IDs des nouveaux rôles

    # Configuration pour la compatibilité avec SQLAlchemy
    model_config = ConfigDict(from_attributes=True)


# --- AUTH ---
class Token(BaseModel):
    access_token: str
    token_type: str
    user_name: str
    user_roles: List[str]