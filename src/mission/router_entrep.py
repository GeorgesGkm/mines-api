from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import math
from datetime import date
from src.core.database import get_db
from ..mission import models, schemas
from src.users import models as models_user

from src.auth.dependencies import (
    get_current_user, 
    RoleChecker, 
    allow_admin, 
    allow_agent, 
    allow_directeur,
    allow_all
)

router = APIRouter(
    prefix="/entreprise",
    tags=["Gestion des Entreprises & Demandes de Titres"]
)

UPLOAD_TITRES_DIR = "static/documents_titres"


#CRUD ENTREPRISE
@router.post("/", response_model=schemas.EntrepriseResponse, status_code=status.HTTP_201_CREATED)
def inscrire_entreprise(
    entreprise: schemas.EntrepriseCreate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
    """
    Enregistrer une nouvelle entreprise minière dans le système.
    """
    db_ent = db.query(models.Entreprise).filter(models.Entreprise.code == entreprise.code).first()
    if db_ent:
        raise HTTPException(
            status_code=400, 
            detail=f"Une entreprise avec le code {entreprise.code} existe déjà."
        )
    
    nouvelle_entreprise = models.Entreprise(**entreprise.model_dump())
    db.add(nouvelle_entreprise)
    db.commit()
    db.refresh(nouvelle_entreprise)
    return nouvelle_entreprise


@router.get("/", response_model=schemas.EntreprisePaginationResponse)
def lister_entreprises(
    province: Optional[str] = None, 
    page: int = 1, 
    page_size: int = 10, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
    """
    Récupérer la liste paginée de toutes les entreprises, avec possibilité de filtrer par province.
    """
    if page < 1: page = 1
    if page_size < 1: page_size = 10

    query = db.query(models.Entreprise)
    if province:
        query = query.filter(models.Entreprise.province.ilike(f"%{province}%"))

    total_items = query.count()
    skip = (page - 1) * page_size
    entreprises = query.offset(skip).limit(page_size).all()
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "items": entreprises
    }


@router.get("/{code}", response_model=schemas.EntrepriseResponse)
def obtenir_entreprise(code: str, db: Session = Depends(get_db)):
    """
    Obtenir les détails complets d'une entreprise par son code.
    """
    entreprise = db.query(models.Entreprise).filter(models.Entreprise.code == code).first()
    if not entreprise:
        raise HTTPException(status_code=404, detail="Entreprise introuvable.")
    return entreprise


@router.patch("/{code}", response_model=schemas.EntrepriseResponse)
def modifier_entreprise(code: str, entreprise_update: schemas.EntrepriseUpdate, db: Session = Depends(get_db)):
    """
    Modifier partiellement les coordonnées ou identifiants d'une entreprise (Rccm, N_impot, Phone...).
    """
    db_ent = db.query(models.Entreprise).filter(models.Entreprise.code == code).first()
    if not db_ent:
        raise HTTPException(status_code=404, detail="Entreprise introuvable.")
    
    update_data = entreprise_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée fournie pour la mise à jour.")

    for key, value in update_data.items():
        setattr(db_ent, key, value)
        
    db.commit()
    db.refresh(db_ent)
    return db_ent


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_entreprise(
    code: str, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
    """
    Supprimer une entreprise du répertoire.
    """
    db_ent = db.query(models.Entreprise).filter(models.Entreprise.code == code).first()
    if not db_ent:
        raise HTTPException(status_code=404, detail="Entreprise introuvable.")
    
    db.delete(db_ent)
    db.commit()
    return None


# 2. INTRODUIRE UNE DEMANDE DE RENOUVELLEMENT DE TITRE (AVEC DOCUMENTS)

@router.post("/{code}/demande-titre", response_model=schemas.TitreMinierResponse, status_code=status.HTTP_201_CREATED)
async def introduire_demande_titre(
    code: str,
    numArret: str = Form(...),
    type_id: int = Form(...),
    date_octroi: Optional[date] = Form(None),
    date_fin: Optional[date] = Form(None),
    fichier_etude: UploadFile = File(...),         # Document d'étude de faisabilité
    fichier_impact: UploadFile = File(...),        # Document d'étude d'impact environnemental
    db: Session = Depends(get_db)
):

    entreprise = db.query(models.Entreprise).filter(models.Entreprise.code == code).first()
    if not entreprise:
        raise HTTPException(status_code=404, detail="Entreprise introuvable.")

    # 2. Sauvegarde des fichiers physiques
    path_etude = os.path.join(UPLOAD_TITRES_DIR, f"etude_{numArret}_{fichier_etude.filename}")
    path_impact = os.path.join(UPLOAD_TITRES_DIR, f"impact_{numArret}_{fichier_impact.filename}")

    with open(path_etude, "wb") as buffer:
        buffer.write(await fichier_etude.read())

    with open(path_impact, "wb") as buffer:
        buffer.write(await fichier_impact.read())

    # 3. Création de l'enregistrement de la demande de titre minier
    db_titre = models.TitreMinier(
        numArret=numArret,
        doc_etude=path_etude,
        doc_impactEnvir=path_impact,
        date_octroi=date_octroi,
        date_fin=date_fin,
        etat="EN_ATTENTE",  # Etat initial avant l'analyse des Divisions et de la Direction
        entreprise_code=code,
        type_id=type_id
    )

    db.add(db_titre)
    db.commit()
    db.refresh(db_titre)
    return db_titre