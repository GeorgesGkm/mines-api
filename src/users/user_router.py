from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from src.users import schemas
from src.auth.dependencies import RoleChecker, get_current_user
from src.core.database import get_db
from src.auth.security import verify_password, get_password_hash, create_access_token
from src.core.email import send_email
from src.users import models
from src.auth.dependencies import allow_admin
from src.auth.dependencies import allow_all

router = APIRouter()


# --- CRUD RÔLES ---
@router.post("/roles", response_model=schemas.RoleResponse, dependencies=[Depends(allow_admin)])
def creer_role(role: schemas.RoleCreate, db: Session = Depends(get_db)):
    db_role = models.Role(**role.dict())
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role

@router.get("/roles", response_model=List[schemas.RoleResponse], dependencies=[Depends(allow_admin)])
def lister_roles(db: Session = Depends(get_db)):
    return db.query(models.Role).all()

# --- MODIFIER UN RÔLE ---
@router.put("/roles/{role_id}", response_model=schemas.RoleResponse, dependencies=[Depends(allow_admin)])
def modifier_role(role_id: int, role_update: schemas.RoleCreate, db: Session = Depends(get_db)):
    db_role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Rôle introuvable")
    
    db_role.name = role_update.name
    db_role.description = role_update.description
    
    db.commit()
    db.refresh(db_role)
    return db_role

# --- SUPPRIMER UN RÔLE ---
@router.delete("/roles/{role_id}", dependencies=[Depends(allow_admin)])
def supprimer_role(role_id: int, db: Session = Depends(get_db)):
    db_role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Rôle introuvable")
    
    # Sécurité : vérifier si le rôle est utilisé
    if db_role.users:
        raise HTTPException(
            status_code=400, 
            detail="Impossible de supprimer ce rôle car il est assigné à des utilisateurs."
        )
    
    db.delete(db_role)
    db.commit()
    return {"message": "Rôle supprimé avec succès."}

# --- CRUD USERS ---
@router.post("/users", response_model=schemas.UserResponse, dependencies=[Depends(allow_admin)])
def creer_utilisateur(user: schemas.UserCreate, 
                      background_tasks: BackgroundTasks,
                      db: Session = Depends(get_db)):
    
    # Vérifier si l'email existe
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    

    hashed_pwd = get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        hashed_password=hashed_pwd,
        full_name=user.full_name,
        first_name = user.first_name
    )
    
    # Ajouter les rôles par ID
    if user.role_ids:
        roles = db.query(models.Role).filter(models.Role.id.in_(user.role_ids)).all()
        new_user.roles = roles

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Envoi du mail en arrière-plan pour ne pas ralentir la requête
    background_tasks.add_task(
        send_email, 
        user.email, 
        user.full_name, 
        user.password
        )

    return new_user

@router.get("/users", response_model=List[schemas.UserResponse], dependencies=[Depends(allow_admin)])
def lister_utilisateurs(db: Session = Depends(get_db)):
    return db.query(models.User).all()

# --- MODIFIER UN UTILISATEUR par l'admin ---
@router.patch("/users/{user_id}", dependencies=[Depends(allow_admin)])
def update_user(user_id: int, payload: schemas.UserUpdate, background_tasks: BackgroundTasks,
                db: Session = Depends(get_db)):
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    
    # Extraire uniquement les données envoyées (ignore les None par défaut)
    update_data = payload.model_dump(exclude_unset=True)

    # Gestion spécifique des rôles
    if "role_ids" in update_data:
        new_roles = db.query(models.Role).filter(models.Role.id.in_(update_data["role_ids"])).all()
        db_user.roles = new_roles # SQLAlchemy gère la table de liaison automatiquement
        del update_data["role_ids"] # On l'enlève pour ne pas le passer au setattr

    # Gestion du mot de passe
    if "password" in update_data:
        db_user.hashed_password = get_password_hash(update_data["password"])

        email_dest = update_data.get("email", db_user.email)
        nom_dest = update_data.get("full_name", db_user.full_name)
        password_dest = update_data["password"]

        background_tasks.add_task(
        send_email, 
        email_dest,
        nom_dest,
        password_dest
        )
        del update_data["password"]


    # Mise à jour du reste (nom, email, etc.)
    for key, value in update_data.items():
        setattr(db_user, key, value)

    try:
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour")
    return {"message": "Utilisateur mis à jour"}

# --- DÉSACTIVER UN UTILISATEUR (Soft Delete) ---
@router.patch("/users/{user_id}/desactiver", dependencies=[Depends(allow_admin)])
def desactiver_utilisateur(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    
    # On inverse l'état actuel : True devient False, False devient True
    db_user.is_active = not db_user.is_active
    
    db.commit()
    db.refresh(db_user) # On rafraîchit pour renvoyer l'état à jour
    
    status_label = "activé" if db_user.is_active else "désactivé"
    return {
        "message": f"L'utilisateur {db_user.full_name} a été {status_label}.",
        "new_status": db_user.is_active
    }

# --- SUPPRIMER UN UTILISATEUR (Permanent) ---
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(allow_admin)])
def supprimer_utilisateur(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    
    db.delete(db_user)
    db.commit()
    return None

@router.patch("/me/update", response_model=schemas.UserResponse, dependencies=[Depends(allow_all)])
def modifier_mon_profil(
    obj_update: schemas.UserSelfUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Modifier le nom s'il est fourni
    if obj_update.full_name:
        current_user.full_name = obj_update.full_name
    
    # 2. Modifier le nom s'il est fourni
    if obj_update.first_name:
        current_user.first_name = obj_update.first_name

    # 3. Modifier l'email s'il est fourni (et vérifier s'il n'est pas déjà pris)
    if obj_update.email and obj_update.email != current_user.email:
        email_exists = db.query(models.User).filter(models.User.email == obj_update.email).first()
        if email_exists:
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé.")
        current_user.email = obj_update.email

    # 4. Modifier le mot de passe (si l'ancien et le nouveau sont fournis)
    if obj_update.new_password:
        if not obj_update.old_password:
            raise HTTPException(status_code=400, detail="L'ancien mot de passe est requis pour le modifier.")
        
        # Vérification de l'ancien mot de passe
        if not verify_password(obj_update.old_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect.")
        
        # Hachage du nouveau
        current_user.hashed_password = get_password_hash(obj_update.new_password)

    db.commit()
    db.refresh(current_user)
    return current_user
