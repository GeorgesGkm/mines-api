from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.auth.security import get_password_hash
from src.users.models import User, Role

def init_db():
    """Fonction pour initialiser les données de base."""
    db: Session = SessionLocal()
    try:
        # 1. Création des rôles
        roles_to_create = ["admin", "user"]
        role_objects = {}
        
        for role_name in roles_to_create:
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(name=role_name)
                db.add(role)
                db.commit()
                db.refresh(role)
            role_objects[role_name] = role

        # 2. Création de l'Admin par défaut
        admin_email = "admin@gouv.com"
        admin_exists = db.query(User).filter(User.email == admin_email).first()
        
        if not admin_exists:
            new_admin = User(
                email=admin_email,
                hashed_password=get_password_hash("123"),
                full_name = "Admin Syst",
                first_name = "Admin Syst",
                # On lui assigne les deux rôles via la table de liaison
                roles=[role_objects["admin"], role_objects["user"]]
            )
            db.add(new_admin)
            db.commit()
            print(f"✅ Admin créé : {admin_email}")
        else:
            print("ℹ️ L'admin existe déjà.")

    except Exception as e:
        print(f"❌ Erreur d'initialisation : {e}")
        db.rollback()
    finally:
        db.close()