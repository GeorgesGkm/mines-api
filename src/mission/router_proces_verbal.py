from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import math
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
    prefix="/proces-verbal",
    tags=["Gestion des Procès-Verbaux & Auditions"]
)


@router.post("/types", response_model=schemas.TypePVResponse, status_code=status.HTTP_201_CREATED)
def creer_type_pv(
    type_pv: schemas.TypePVCreate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
    """
    Créer une nouvelle catégorie de PV. 
    """
    type_existant = db.query(models.TypePV).filter(models.TypePV.type_nom == type_pv.type_nom).first()
    if type_existant:
        raise HTTPException(
            status_code=400, 
            detail=f"Le type de PV '{type_pv.type_nom}' existe déjà."
        )

    nouveau_type = models.TypePV(**type_pv.model_dump())
    db.add(nouveau_type)
    db.commit()
    db.refresh(nouveau_type)
    return nouveau_type


@router.patch("/types/{code_type}", response_model=schemas.TypePVResponse)
def modifier_type_pv(
    code_type: int, 
    type_update: schemas.TypePVUpdate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)
):
    """
    Modifier partiellement le nom d'un type de PV via son ID unique (code_type).
    """
    db_type = db.query(models.TypePV).filter(models.TypePV.code_type == code_type).first()
    if not db_type:
        raise HTTPException(status_code=404, detail="Type de PV introuvable.")
    
    update_data = type_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée fournie pour la mise à jour.")

    for key, value in update_data.items():
        setattr(db_type, key, value)
        
    db.commit()
    db.refresh(db_type)
    return db_type


@router.delete("/types/{code_type}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_type_pv(
    code_type: int, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_directeur)

):
    """
    Supprimer un type de PV. 
    """
    db_type = db.query(models.TypePV).filter(models.TypePV.code_type == code_type).first()
    if not db_type:
        raise HTTPException(status_code=404, detail="Type de PV introuvable.")
    
    pv_lie = db.query(models.ProcesVerbal).filter(models.ProcesVerbal.type_code_id == code_type).first()
    if pv_lie:
        raise HTTPException(
            status_code=400, 
            detail="Impossible de supprimer ce type. Des procès-verbaux y sont rattachés en base de données."
        )

    db.delete(db_type)
    db.commit()
    return None


@router.post("/", response_model=schemas.ProcesVerbalResponse, status_code=status.HTTP_201_CREATED)
def rediger_pv_avec_questions(
    pv: schemas.ProcesVerbalCreate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)
):
    """
    Créer un Procès-Verbal et enregistrer directement toutes ses questions-réponses associées
    """
    mission = db.query(models.Mission).filter(models.Mission.n_ordre == pv.mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission associée introuvable.")
    
    pv_existant = db.query(models.ProcesVerbal).filter(models.ProcesVerbal.mission_id == pv.mission_id).first()
    if pv_existant:
        raise HTTPException(
            status_code=400, 
            detail=f"Un Procès-Verbal existe déjà pour cette mission."
        )

    db_pv_num = db.query(models.ProcesVerbal).filter(models.ProcesVerbal.num_pv == pv.num_pv).first()
    if db_pv_num:
        raise HTTPException(status_code=400, detail="Ce numéro de PV est déjà utilisé.")

    donnees_pv = pv.model_dump(exclude={"questions"})
    
    nouveau_pv = models.ProcesVerbal(**donnees_pv)
    db.add(nouveau_pv)
    
    db.flush() 

    if pv.questions:
        for q_r in pv.questions:
            nouvelle_ligne = models.QuestionReponse(
                num_pv=nouveau_pv.num_pv, # Liaison automatique grâce au numéro du PV
                num_ordre=q_r.num_ordre,
                question=q_r.question,
                response=q_r.response
            )
            db.add(nouvelle_ligne)

    db.commit()
    db.refresh(nouveau_pv)
    
    return nouveau_pv


@router.get("/", response_model=schemas.PVPaginationResponse)
def lister_proces_verbaux(
    type_code: Optional[str] = None, 
    page: int = 1, 
    page_size: int = 10, 
    db: Session = Depends(get_db),
):
    """
    Récupérer la liste paginée de tous les PV avec possibilité de filtrer par type (ex: PV d'Amende).
    """
    if page < 1: page = 1
    if page_size < 1: page_size = 10

    query = db.query(models.ProcesVerbal)
    if type_code:
        query = query.filter(models.ProcesVerbal.type_code == type_code)

    total_items = query.count()
    skip = (page - 1) * page_size
    pvs = query.offset(skip).limit(page_size).all()
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "items": pvs
    }


@router.get("/{num_pv}", response_model=schemas.ProcesVerbalResponse)
def obtenir_proces_verbal(
    num_pv: str, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)
):
    """
    Obtenir les détails d'un PV spécifique incluant ses questions-réponses (Audition).
    """
    pv = db.query(models.ProcesVerbal).filter(models.ProcesVerbal.num_pv == num_pv).first()
    if not pv:
        raise HTTPException(status_code=404, detail="Procès-Verbal introuvable.")
    return pv


@router.patch("/{num_pv}", response_model=schemas.ProcesVerbalResponse)
def modifier_proces_verbal(
    num_pv: str, 
    pv_update: schemas.ProcesVerbalUpdate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)
    ):
    """
    Modifier partiellement les données d'un PV (Changement du montant de l'amende, précision sur l'infraction).
    """
    db_pv = db.query(models.ProcesVerbal).filter(models.ProcesVerbal.num_pv == num_pv).first()
    if not db_pv:
        raise HTTPException(status_code=404, detail="Procès-Verbal introuvable.")
    
    # Sécurité : Si la mission liée est clôturée, on fige le PV
    if db_pv.mission and db_pv.mission.statut == "CLOTURE":
        raise HTTPException(status_code=400, detail="Impossible de modifier le PV d'une mission clôturée.")

    update_data = pv_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée fournie pour la mise à jour.")

    for key, value in update_data.items():
        setattr(db_pv, key, value)
        
    db.commit()
    db.refresh(db_pv)
    return db_pv


@router.delete("/{num_pv}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_proces_verbal(
    num_pv: str, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_dir_agent)
    ):
    """
    Supprimer un PV. Entraîne la suppression automatique de ses questions-réponses en cascade.
    """
    db_pv = db.query(models.ProcesVerbal).filter(models.ProcesVerbal.num_pv == num_pv).first()
    if not db_pv:
        raise HTTPException(status_code=404, detail="Procès-Verbal introuvable.")
    
    if db_pv.mission and db_pv.mission.statut == "CLOTURE":
        raise HTTPException(status_code=400, detail="Impossible de supprimer le PV d'une mission clôturée.")

    db.delete(db_pv)
    db.commit()
    return None


# 2. GESTION DES QUESTIONS / RÉPONSES (AUDITIONS)

@router.patch("/questions-reponses/{id_qr}", response_model=schemas.QuestionReponseResponse)
def modifier_ligne_audition(
    id_qr: int, 
    qr_update: schemas.QuestionReponseUpdate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)    
):
    """
    Modifier partiellement une ligne de question-réponse spécifique via son ID.
    """
    # 1. Rechercher la ligne de question-réponse
    db_qr = db.query(models.QuestionReponse).filter(models.QuestionReponse.id == id_qr).first()
    if not db_qr:
        raise HTTPException(status_code=404, detail="Ligne d'audition introuvable.")
    
    # 2. Sécurité : Vérifier si le PV lié n'est pas verrouillé par une mission clôturée
    if db_qr.proces_verbal and db_qr.proces_verbal.mission:
        if db_qr.proces_verbal.mission.statut == "CLOTURE":
            raise HTTPException(
                status_code=400, 
                detail="Impossible de modifier cette réponse. Le dossier de mission est définitivement clôturé."
            )

    # 3. Extraire les champs envoyés par l'application
    update_data = qr_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée valide fournie pour la mise à jour.")

    # 4. Appliquer les modifications dynamiquement
    for key, value in update_data.items():
        setattr(db_qr, key, value)
        
    db.commit()
    db.refresh(db_qr)
    return db_qr

@router.delete("/questions-reponses/{id_qr}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_une_ligne_audition(
    id_qr: int, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)
    ):
    """
    Supprimer une question-réponse spécifique d'un PV en cas d'erreur de saisie.
    """
    qr = db.query(models.QuestionReponse).filter(models.QuestionReponse.id == id_qr).first()
    if not qr:
        raise HTTPException(status_code=404, detail="Ligne d'audition introuvable.")
    
    db.delete(qr)
    db.commit()
    return None


