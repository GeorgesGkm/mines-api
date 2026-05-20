import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import math
from datetime import date
from src.core.database import get_db
from ..mission import models, schemas

router = APIRouter(
    prefix="/mission",
    tags=["Gestion des Missions & Circuit de Validation"]
)

# Dossier où seront sauvegardées les notes explicatives sur le serveur
UPLOAD_DIR = "uploads/notes_explicatives"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# =====================================================================
# 1. CRÉATION AVEC TÉLÉVERSEMENT DE LA NOTE EXPLICATIVE (AGENT)
# =====================================================================

@router.post("/proposer", response_model=schemas.MissionResponse, status_code=status.HTTP_201_CREATED)
async def proposer_mission_avec_note(
    objet: str = Form(...),
    province: Optional[str] = Form(None),
    date_debut: Optional[date] = Form(None),
    date_fin: Optional[date] = Form(None),
    mode_transport: Optional[str] = Form(None),
    entreprise_code: Optional[str] = Form(None),
    agent_matricules: List[str] = Form([]), # Reçu sous forme de liste de chaînes
    fichier: UploadFile = File(...),   # Le fichier joint obligatoire
    db: Session = Depends(get_db)
):
    """
    Étape 1 : L'agent propose une mission en téléversant le fichier 
    de la note explicative. Le statut initial passe automatiquement à 'PROPOSE'.
    """
    if fichier:
        base_static_dir = "static/note_explicative"
        os.makedirs(base_static_dir, exist_ok=True)
        
        extension = os.path.splitext(fichier.filename)[1].lower()
        nom_sans_extension = os.path.splitext(fichier.filename)[0]
        nom_unique = uuid.uuid4().hex[:6]
        
        # On crée UN SEUL nom de fichier cohérent
        nom_fichier_final = f"{nom_unique}-filename={nom_sans_extension}{extension}"
        
        # Chemin complet pour l'écriture sur le disque
        file_location = os.path.join(base_static_dir, nom_fichier_final)
        
        # URL relative pour la base de données (ce qui sera servi par FastAPI)
        file_path = f"/static/note_explicative/{nom_fichier_final}"

        try:
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(fichier.file, buffer)
        finally:
            fichier.file.close()

    # 2. Création de l'enregistrement de la mission
    db_mission = models.Mission(
        objet=objet,
        province=province,
        date_debut=date_debut,
        date_fin=date_fin,
        statut="PROPOSE", # Circuit initial
        mode_transport=mode_transport,
        entreprise_code=entreprise_code,
        note_explicative=file_path # Sauvegarde du chemin
    )

    # 3. Association des agents (OPJ) concernés
    if agent_matricules:
        agents = db.query(models.Agent).filter(models.Agent.matricule.in_(agent_matricules)).all()
        db_mission.agents = agents

    db.add(db_mission)
    db.commit()
    db.refresh(db_mission)
    return db_mission


# =====================================================================
# 2. LE CIRCUIT DE VALIDATION (DIRECTEUR -> SG -> MINISTRE)
# =====================================================================

@router.patch("/{n_ordre}/avancer-workflow", response_model=schemas.MissionResponse)
def avancer_workflow_mission(n_ordre: int, update_statut: schemas.MissionStatutUpdate, db: Session = Depends(get_db)):
    """
    Permet aux différentes autorités d'interagir avec le projet de mission :
    - Le Directeur valide -> 'VALIDE_DIR' (Projet d'ordre de mission établi)
    - Le SG approuve -> 'APPROUVE_SG'
    - Le Ministre signe -> 'SIGNE_MINISTRE'
    - L'Agent retire au cabinet -> 'RETIRE'
    """
    mission = db.query(models.Mission).filter(models.Mission.n_ordre == n_ordre).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Ordre de mission introuvable.")

    statuts_autorises = ["VALIDE_DIR", "APPROUVE_SG", "SIGNE_MINISTRE", "RETIRE", "EN_COURS"]
    if update_statut.statut not in statuts_autorises:
        raise HTTPException(status_code=400, detail="Statut de workflow non conforme pour cette étape.")

    # Validation de transition logique simple
    if update_statut.statut == "SIGNE_MINISTRE":
        # Logique métier additionnelle : on enregistre le moment de signature
        mission.date_signature = date.today()

    mission.statut = update_statut.statut
    db.commit()
    db.refresh(mission)
    return mission


# =====================================================================
# 3. CONSULTATION & SUIVI DES MISSIONS (ADMIN / RECHERCHE)
# =====================================================================

@router.get("/", response_model=schemas.MissionPaginationResponse)
def lister_toutes_les_missions(
    statut: Optional[str] = None, 
    page: int = 1, 
    page_size: int = 10, 
    db: Session = Depends(get_db)
):
    """
    Liste paginée de toutes les missions du système, avec possibilité de filtrer par statut 
    (ex: Voir tous les projets 'APPROUVE_SG' en attente de la signature du Ministre).
    """
    # Sécurité pour éviter les index négatifs ou nuls
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    # 1. Initialiser la requête de base
    query = db.query(models.Mission)
    
    # 2. Appliquer le filtre de statut si l'utilisateur l'a fourni
    if statut:
        query = query.filter(models.Mission.statut == statut)

    # 3. Compter le total d'éléments *après* avoir appliqué le filtre
    total_items = query.count()

    # 4. Calculer le décalage (skip) pour la base de données
    skip = (page - 1) * page_size

    # 5. Récupérer les données spécifiques à la page demandée
    missions = query.offset(skip).limit(page_size).all()

    # 6. Calculer le nombre total de pages
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

    # 7. Renvoyer la réponse structurée
    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "items": missions
    }


@router.get("/{n_ordre}", response_model=schemas.MissionResponse)
def obtenir_details_mission(n_ordre: int, db: Session = Depends(get_db)):
    """
    Récupérer une mission précise avec ses agents assignés et le PV lié s'il existe.
    """
    mission = db.query(models.Mission).filter(models.Mission.n_ordre == n_ordre).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission introuvable.")
    return mission


@router.delete("/{n_ordre}", status_code=status.HTTP_204_NO_CONTENT)
def annuler_mission(n_ordre: int, db: Session = Depends(get_db)):
    """
    Permet de supprimer ou d'annuler un projet de mission s'il n'est pas encore signé.
    """
    mission = db.query(models.Mission).filter(models.Mission.n_ordre == n_ordre).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission introuvable.")
    
    if mission.statut in ["SIGNE_MINISTRE", "EN_COURS", "CLOTURE"]:
        raise HTTPException(status_code=400, detail="Impossible de supprimer une mission déjà signée ou exécutée.")

    # Optionnel : Supprimer le fichier physique associé sur le serveur
    if mission.note_explicative_path and os.path.exists(mission.note_explicative_path):
        os.remove(mission.note_explicative_path)

    db.delete(mission)
    db.commit()
    return None