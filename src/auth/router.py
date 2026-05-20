from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from src.auth.dependencies import get_current_user
from src.users import schemas
from src.core.database import get_db
from src.auth.security import verify_password, get_password_hash, create_access_token
from src.users import models
from src.auth import tokenBlackList_models

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Votre compte a été désactivé. Veuillez contacter l'administrateur."
        )

    # Récupérer les noms des rôles pour le token
    role_names = [role.name for role in user.roles]

    # Création du Token avec infos additionnelles
    access_token = create_access_token(data={
        "sub": user.email, 
        "name": f"{user.full_name} {user.first_name}",
        "roles": role_names
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_name": f"{user.full_name} {user.first_name}",
        "user_roles": role_names
    }

@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user) # Optionnel: vérifie si déjà connecté
):
    # Ajouter le token à la blacklist
    blacklisted_token = tokenBlackList_models.TokenBlacklist(token=token)
    db.add(blacklisted_token)
    db.commit()
    
    return {"message": "Déconnexion réussie. Le token a été révoqué."}
