from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session, joinedload
from src.core.database import get_db
from src.core.config import settings
from src.users import models
from src.auth.tokenBlackList_models import TokenBlacklist

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    is_revoked = db.query(TokenBlacklist).filter(TokenBlacklist.token == token).first()
    if is_revoked:
        raise HTTPException(
            status_code=401, 
            detail="Ce token a été révoqué. Veuillez vous reconnecter."
        )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.email == email).first()

    if user is None:
        raise credentials_exception    

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte inactif")
    
    return user

class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, user: models.User = Depends(get_current_user)):
        # On vérifie si l'un des rôles de l'utilisateur est dans la liste autorisée
        user_role_names = [role.name for role in user.roles]
        for role in self.allowed_roles:
            if role in user_role_names:
                return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas les permissions nécessaires"
        )


allow_admin = RoleChecker(["admin"])
allow_user = RoleChecker(["user"])
allow_all = RoleChecker(["admin", "user", "chef_service"])
allow_all_courrier = RoleChecker(["admin", "chef_service", "secretaire", "agent_courrier"])