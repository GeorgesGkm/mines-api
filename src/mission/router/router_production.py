from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from src.core.database import get_db
from src.mission import models, schemas
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
    prefix="/production",
    tags=["Collecte des Données d'Exploitation Minière"]
)

@router.post("/", response_model=schemas.ProductionResponse, status_code=status.HTTP_201_CREATED)
def enregistrer_production_et_substances(
    payload: schemas.ProductionCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(allow_agent)
):
    """
    Enregistre une production et ses substances associées, puis retourne le format complet.
    """
    # 1. Contrôle de la Mission
    mission = db.query(models.Mission).filter(models.Mission.n_ordre == payload.mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission de contrôle introuvable.")
    if mission.statut == "CLOTURE":
        raise HTTPException(status_code=400, detail="Impossible d'ajouter des données à une mission clôturée.")

    # 2. Contrôle de l'Entreprise
    entreprise = db.query(models.Entreprise).filter(models.Entreprise.code == payload.entreprise_code).first()
    if not entreprise:
        raise HTTPException(status_code=404, detail="Entreprise minière introuvable.")

    # 3. Contrôle de l'unicité de la Production
    db_prod = db.query(models.Production).filter(models.Production.code_prod == payload.code_prod).first()
    if db_prod:
        raise HTTPException(status_code=400, detail="Ce code de production existe déjà.")

    # 4. Insertion de la Production principale
    nouvelle_production = models.Production(
        code_prod=payload.code_prod,
        datprod=payload.datprod,
        nbCarat=payload.nbCarat,
        entreprise_code=payload.entreprise_code,
        mission_id=payload.mission_id
    )
    db.add(nouvelle_production)
    db.flush() 

    # 5. Traitement des substances déclarées
    if payload.substances_declarees:
        for sub_data in payload.substances_declarees:
            
            # Recherche par libellé (Insensible à la casse)
            substance_existe = db.query(models.Substance).filter(
                models.Substance.libSub.ilike(sub_data.libSub)
            ).first()
            
            # Si elle n'existe pas, on la crée à la volée
            if not substance_existe:
                substance_existe = models.Substance(
                    libSub=sub_data.libSub,
                    mont=sub_data.mont,
                    carat=sub_data.carat,
                    date_cont=sub_data.date_cont if sub_data.date_cont else date.today()
                )
                db.add(substance_existe)
                db.flush() 

            # 6. Insertion dans la table d'association production_substance
            association = models.ProductionSubstance(
                production_code=nouvelle_production.code_prod,
                substance_code=substance_existe.code_sub, 
                centre_ach=sub_data.centre_ach,
                nb_exp=sub_data.nb_exp,
                valbon=sub_data.valbon,
                val_decl=sub_data.val_decl,
                mpc_decl=sub_data.mpc_decl
            )
            db.add(association)

    # Validation de la transaction globale
    db.commit()
    db.refresh(nouvelle_production)
    
    # 7. Formatage de la réponse pour s'aligner sur ProductionResponse
    substances_aggregations = []
    for prod_sub in nouvelle_production.substances:
        substances_aggregations.append({
            "substance_code": prod_sub.substance_code,
            "libSub": prod_sub.substance.libSub if prod_sub.substance else "",
            "mont": prod_sub.substance.mont if prod_sub.substance else 0.0,
            "carat": prod_sub.substance.carat if prod_sub.substance else 0.0,
            "date_cont": prod_sub.substance.date_cont if prod_sub.substance else None,
            "centre_ach": prod_sub.centre_ach,
            "nb_exp": prod_sub.nb_exp,
            "valbon": prod_sub.valbon,
            "val_decl": prod_sub.val_decl,
            "mpc_decl": prod_sub.mpc_decl
        })

    return {
        "code_prod": nouvelle_production.code_prod,
        "datprod": nouvelle_production.datprod,
        "nbCarat": nouvelle_production.nbCarat,
        "entreprise_code": nouvelle_production.entreprise_code,
        "mission_id": nouvelle_production.mission_id,
        "substances_declarees": substances_aggregations
    }


@router.get("/mission/{mission_id}", response_model=List[schemas.ProductionResponse])
def obtenir_productions_par_mission(
    mission_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(allow_agent)
):
    # 1. Vérifier la mission
    mission = db.query(models.Mission).filter(models.Mission.n_ordre == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission introuvable.")

    # 2. Récupérer les productions
    productions = db.query(models.Production).filter(models.Production.mission_id == mission_id).all()
    
    reponse_formatee = []
    
    for prod in productions:
        substances_aggregations = []
        
        for prod_sub in prod.substances:
            substances_aggregations.append({
                "substance_code": prod_sub.substance_code,
                "libSub": prod_sub.substance.libSub if prod_sub.substance else "",
                "mont": prod_sub.substance.mont if prod_sub.substance else 0.0,
                "carat": prod_sub.substance.carat if prod_sub.substance else 0.0,
                "date_cont": prod_sub.substance.date_cont if prod_sub.substance else None,
                "centre_ach": prod_sub.centre_ach,
                "nb_exp": prod_sub.nb_exp,
                "valbon": prod_sub.valbon,
                "val_decl": prod_sub.val_decl,
                "mpc_decl": prod_sub.mpc_decl
            })
            
        # ─── ALIGNEMENT CLÉ-SCHÉMA ───
        reponse_formatee.append({
            "code_prod": prod.code_prod,
            "datprod": prod.datprod,
            "nbCarat": prod.nbCarat,
            "entreprise_code": prod.entreprise_code,
            "mission_id": prod.mission_id,
            "substances_declarees": substances_aggregations  # ◄── Utilisez exactement ce nom de clé
        })
        
    return reponse_formatee


@router.patch("/{code_prod}")
def modifier_production(
    code_prod: str, 
    payload: schemas.ProductionUpdate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)
):
    """
    1. Modifier les informations générales d'une production
    """
    db_prod = db.query(models.Production).filter(models.Production.code_prod == code_prod).first()
    if not db_prod:
        raise HTTPException(status_code=404, detail="Enregistrement de production introuvable.")
    
    if db_prod.mission and db_prod.mission.statut == "CLOTURE":
        raise HTTPException(status_code=400, detail="Modification interdite : la mission associée est clôturée.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_prod, key, value)

    db.commit()
    db.refresh(db_prod)
    return db_prod


@router.patch("/substance/{code_sub}")
def modifier_substance_referentiel(
    code_sub: int, 
    payload: schemas.SubstanceUpdate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)
):
    """
    2. Modifier la fiche de la substance elle-même dans le référentiel (ex: corriger le libellé).
    """
    db_sub = db.query(models.Substance).filter(models.Substance.code_sub == code_sub).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Substance introuvable.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_sub, key, value)

    db.commit()
    db.refresh(db_sub)
    return db_sub


@router.patch("/{code_prod}/substance/{code_sub}", response_model=schemas.ProductionSubstanceResponse)
def modifier_valeurs_production_substance(
    code_prod: str, 
    code_sub: int, 
    payload: schemas.ProductionSubstanceUpdate, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)
):
    """
    3. Modifier les valeurs spécifiques déclarées pour UNE substance durant UNE production précise
    """
    # Trouver la ligne précise dans la table d'association (Clé primaire composite)
    db_assoc = db.query(models.ProductionSubstance).filter(
        models.ProductionSubstance.production_code == code_prod,
        models.ProductionSubstance.substance_code == code_sub
    ).first()

    if not db_assoc:
        raise HTTPException(status_code=404, detail="Liaison production/substance introuvable.")

    # Sécurité : Remonter à la mission pour vérifier son statut
    if db_assoc.production and db_assoc.production.mission:
        if db_assoc.production.mission.statut == "CLOTURE":
            raise HTTPException(status_code=400, detail="Modification impossible : le dossier de mission est clôturé.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_assoc, key, value)

    db.commit()
    db.refresh(db_assoc)
    return db_assoc

@router.delete("/{code_prod}/substance/{code_sub}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_substance_de_production(
    code_prod: str, 
    code_sub: int, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)
):
    """
    Retirer une substance spécifique d'une déclaration de production.
    (Supprime la ligne uniquement dans la table d'association production_substance).
    """
    # 1. Rechercher la ligne d'association
    db_assoc = db.query(models.ProductionSubstance).filter(
        models.ProductionSubstance.production_code == code_prod,
        models.ProductionSubstance.substance_code == code_sub
    ).first()

    if not db_assoc:
        raise HTTPException(status_code=404, detail="Cette substance n'est pas liée à cette production.")

    # 2. Sécurité : Empêcher la suppression si la mission est clôturée
    if db_assoc.production and db_assoc.production.mission:
        if db_assoc.production.mission.statut == "CLOTURE":
            raise HTTPException(
                status_code=400, 
                detail="Suppression impossible : le dossier de cette mission a été définitivement clôturé."
            )

    # 3. Supprimer la liaison
    db.delete(db_assoc)
    db.commit()
    return None

@router.delete("/{code_prod}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_production_complete(
    code_prod: str, 
    db: Session = Depends(get_db),
    current_user: models_user.User = Depends(allow_agent)
):
    """
    Supprime l'intégralité d'une fiche de production ainsi que toutes ses liaisons 
    dans la table production_substance.
    """
    # 1. Rechercher la production globale
    db_prod = db.query(models.Production).filter(models.Production.code_prod == code_prod).first()
    if not db_prod:
        raise HTTPException(status_code=404, detail="Enregistrement de production introuvable.")

    # 2. Sécurité : Vérifier le verrou de clôture de la mission
    if db_prod.mission and db_prod.mission.statut == "CLOTURE":
        raise HTTPException(
            status_code=400, 
            detail="Suppression interdite : les données de cette mission sont verrouillées (statut CLOTURE)."
        )

    # 3. Supprimer d'abord explicitement les substances associées pour éviter les conflits de clé étrangère
    db.query(models.ProductionSubstance).filter(
        models.ProductionSubstance.production_code == code_prod
    ).delete()

    # 4. Supprimer la production parente
    db.delete(db_prod)
    db.commit()
    return None