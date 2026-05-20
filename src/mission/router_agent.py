import math

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from src.core.database import get_db
from ..mission import models, schemas

router = APIRouter(
    prefix="/agent",
    tags=["Gestion des Agents & Missions (OPJ)"]
)

# =====================================================================
# 1. CRUD COMPLET : GESTION DES AGENTS
# =====================================================================

@router.post("/", response_model=schemas.AgentResponse, status_code=status.HTTP_201_CREATED)
def inscrire_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    """
    Créer un nouvel agent (OPJ de la DIMC) dans le système.
    """
    db_agent = db.query(models.Agent).filter(models.Agent.matricule == agent.matricule).first()
    if db_agent:
        raise HTTPException(
            status_code=400, 
            detail=f"Un agent avec le matricule {agent.matricule} existe déjà."
        )
    
    nouvel_agent = models.Agent(**agent.model_dump())
    db.add(nouvel_agent)
    db.commit()
    db.refresh(nouvel_agent)
    return nouvel_agent


@router.get("/", response_model=schemas.AgentPaginationResponse)
def lister_agents(page: int = 1, page_size: int = 10, db: Session = Depends(get_db)):
    """
    Récupérer la liste paginée de tous les agents inscrits.
    Idéal pour l'affichage dans un tableau ou une ListView infinie.
    """
    # Sécurité pour éviter les valeurs négatives ou nulles
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    # 1. Compter le nombre total d'agents dans la base
    total_items = db.query(models.Agent).count()

    # 2. Calculer le décalage (skip) pour SQL
    skip = (page - 1) * page_size

    # 3. Récupérer uniquement les éléments de la page demandée
    agents = db.query(models.Agent).offset(skip).limit(page_size).all()

    # 4. Calculer le nombre total de pages
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

    # 5. Renvoyer l'objet structuré complet
    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "items": agents
    }


@router.get("/{matricule}", response_model=schemas.AgentResponse)
def obtenir_agent(matricule: str, db: Session = Depends(get_db)):
    """
    Récupérer les détails d'un agent spécifique par son matricule.
    """
    agent = db.query(models.Agent).filter(models.Agent.matricule == matricule).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable.")
    return agent


@router.patch("/{matricule}", response_model=schemas.AgentResponse)
def modifier_agent(matricule: str, agent_update: schemas.AgentUpdate, db: Session = Depends(get_db)):
    """
    Modifier partiellement les informations d'un agent (PATCH).
    Seuls les champs envoyés dans la requête seront mis à jour.
    """
    db_agent = db.query(models.Agent).filter(models.Agent.matricule == matricule).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent introuvable.")
    
    # exclude_unset=True extrait uniquement les clés explicitement fournies par l'utilisateur
    update_data = agent_update.model_dump(exclude_unset=True)
    
    # S'il n'y a aucun champ envoyé, on évite un appel inutile à la base de données
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée valide n'a été fournie pour la mise à jour.")

    # Mise à jour dynamique des attributs fournis
    for key, value in update_data.items():
        setattr(db_agent, key, value)
        
    db.commit()
    db.refresh(db_agent)
    return db_agent


@router.delete("/{matricule}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_agent(matricule: str, db: Session = Depends(get_db)):
    """
    Supprimer un agent du système (par exemple en cas de retraite ou mutation).
    """
    db_agent = db.query(models.Agent).filter(models.Agent.matricule == matricule).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent introuvable.")
    
    db.delete(db_agent)
    db.commit()
    return None


# =====================================================================
# 2. AFFECTATION : ASSIGNER UN AGENT À UNE MISSION
# =====================================================================

@router.post("/assigner-mission", response_model=schemas.MissionResponse)
def assigner_agent_a_mission(n_ordre_mission: int, matricule_agent: str, db: Session = Depends(get_db)):
    """
    Assigne un agent (OPJ) à une mission spécifique. 
    Alimente automatiquement la table d'association 'mission_agent'.
    """
    # 1. Vérifier si la mission existe
    mission = db.query(models.Mission).filter(models.Mission.n_ordre == n_ordre_mission).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission introuvable.")
    
    # 2. Vérifier si l'agent existe
    agent = db.query(models.Agent).filter(models.Agent.matricule == matricule_agent).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable.")
    
    # 3. Sécurité workflow : On ne peut plus ajouter d'agent si la mission est clôturée
    if mission.statut == "CLOTURE":
        raise HTTPException(
            status_code=400, 
            detail="Impossible d'ajouter un agent à une mission déjà clôturée."
        )

    # 4. Vérifier si l'agent est déjà assigné pour éviter les doublons
    if agent in mission.agents:
        raise HTTPException(
            status_code=400, 
            detail="Cet agent est déjà assigné à cette mission."
        )
        
    # 5. Injection de la relation (SQLAlchemy s'occupe de la table intermédiaire)
    mission.agents.append(agent)
    db.commit()
    db.refresh(mission)
    return mission


# =====================================================================
# 3. WORKFLOW TERRAIN (RAPPEL DES ÉTAPES SUIVANTES)
# =====================================================================

@router.get("/mes-missions", response_model=List[schemas.MissionResponse])
def obtenir_mes_missions(matricule: str, db: Session = Depends(get_db)):
    """
    Permet à un agent de voir la liste complète de ses affectations.
    """
    agent = db.query(models.Agent).filter(models.Agent.matricule == matricule).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable.")
    return agent.missions