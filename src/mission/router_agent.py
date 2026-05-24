import math

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
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
    allow_dir_agent,
    allow_all
)

router = APIRouter(
    prefix="/agent",
    tags=["Gestion des Agents & Missions (OPJ)"]
)

@router.post("/", response_model=schemas.AgentResponse, status_code=status.HTTP_201_CREATED)
def inscrire_agent(
    agent: schemas.AgentCreate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
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
def lister_agents(
    page: int = 1, 
    page_size: int = 10, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
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
def obtenir_agent(
    matricule: str, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
    """
    Récupérer les détails d'un agent spécifique par son matricule.
    """
    agent = db.query(models.Agent).filter(models.Agent.matricule == matricule).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable.")
    return agent


@router.patch("/{matricule}", response_model=schemas.AgentResponse)
def modifier_agent(
    matricule: str, 
    agent_update: schemas.AgentUpdate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
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
def supprimer_agent(
    matricule: str, 
    db: Session = Depends(get_db), 
    current_user: models_user.User = Depends(allow_directeur)
):
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
def assigner_agent_a_mission(
    n_ordre_mission: int, 
    matricule_agent: str, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
    """
    Assigne un agent (OPJ) à une mission spécifique. 
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


# 3. WORKFLOW TERRAIN (RAPPEL DES ÉTAPES SUIVANTES)

@router.get("/mes-missions", response_model=schemas.MissionPaginationResponse)
def obtenir_mes_missions(
    page: int = 1, 
    page_size: int = 10, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_dir_agent)
):
    """
    Permet à un Directeur de voir l'intégralité des missions du système,
    et à un Agent de voir uniquement les missions auxquelles il est assigné.
    """
    # 1. Gestion de la pagination (validation des paramètres)
    if page < 1: page = 1
    if page_size < 1: page_size = 10
    skip = (page - 1) * page_size

    # Extraire les noms des rôles de l'utilisateur connecté
    user_roles = [r.name.lower() for r in current_user.user_rattache.roles] if current_user.user_rattache else []

    # 2. Construction dynamique de la requête selon le rôle
    if "directeur" in user_roles:
        # Le Directeur voit TOUTES les missions sans restriction
        query_missions = db.query(models.Mission)
        
    else:
        # C'est un Agent : On cherche sa fiche de personnel liée pour obtenir son matricule
        agent_fiche = db.query(models.Agent).filter(models.Agent.user_id == current_user.id).first()
        
        if not agent_fiche:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ce compte utilisateur n'est relié à aucune fiche de personnel SINA."
            )
        
        # L'Agent voit uniquement les missions où son matricule apparaît dans la relation
        query_missions = db.query(models.Mission).join(models.Mission.agents).filter(
            models.Agent.matricule == agent_fiche.matricule
        )

    # 3. Exécution de la pagination sur la requête choisie
    total_items = query_missions.count()
    missions_paginees = query_missions.order_by(models.Mission.n_ordre.desc()).offset(skip).limit(page_size).all()
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "items": missions_paginees
    }

