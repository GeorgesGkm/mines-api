from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from src.core.database import get_db
from src.mission import models, schemas
from src.auth.dependencies import allow_admin, allow_directeur, allow_all

router = APIRouter(
    prefix="/titre",
    tags=["Titres Miniers"]
)


# CRUD : ETAT TITRE ("Renouvelé", "Déchu", "Refusé")
@router.post("/etats", response_model=schemas.EtatTitreResponse, status_code=status.HTTP_201_CREATED)
def creer_etat_titre(
    payload: schemas.EtatTitreCreate, 
    db: Session = Depends(get_db), 
    current_user = Depends(allow_admin)
):
    """Crée un nouvel état possible pour les titres."""
    existe = db.query(models.EtatTitre).filter(models.EtatTitre.libetattit.ilike(payload.libetattit)).first()
    if existe:
        raise HTTPException(status_code=400, detail="Cet état de titre existe déjà.")
    
    nouvel_etat = models.EtatTitre(libetattit=payload.libetattit)
    db.add(nouvel_etat)
    db.commit()
    db.refresh(nouvel_etat)
    return nouvel_etat


@router.get("/etats", response_model=List[schemas.EtatTitreResponse])
def lister_etats_titre(db: Session = Depends(get_db), current_user = Depends(allow_admin)):
    """Tout le monde (y compris l'application Flutter) peut lire la liste des états."""
    return db.query(models.EtatTitre).all()


@router.patch("/etats/{codetattit}", response_model=schemas.EtatTitreResponse)
def modifier_etat_titre(
    codetattit: int, 
    payload: schemas.EtatTitreCreate, 
    db: Session = Depends(get_db), 
    current_user = Depends(allow_admin)
):
    """Modifie le libellé d'un état."""
    db_etat = db.query(models.EtatTitre).filter(models.EtatTitre.codetattit == codetattit).first()
    if not db_etat:
        raise HTTPException(status_code=404, detail="État de titre introuvable.")
    
    db_etat.libetattit = payload.libetattit
    db.commit()
    db.refresh(db_etat)
    return db_etat


@router.delete("/etats/{codetattit}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_etat_titre(codetattit: int, db: Session = Depends(get_db), current_user = Depends(allow_admin)):
    """Supprime un état (uniquement s'il n'est lié à aucun titre existant)."""
    db_etat = db.query(models.EtatTitre).filter(models.EtatTitre.codetattit == codetattit).first()
    if not db_etat:
        raise HTTPException(status_code=404, detail="État de titre introuvable.")
    
    # Sécurité de clé étrangère logicielle pour éviter les crashs
    titres_lies = db.query(models.TitreMinier).filter(models.TitreMinier.codetattit == codetattit).first()
    if titres_lies:
        raise HTTPException(status_code=400, detail="Suppression impossible : cet état est actuellement utilisé par des titres.")
        
    db.delete(db_etat)
    db.commit()
    return None


# =====================================================================
# CRUD : TYPE TITRE ("PE", "PR", "PER", etc.)
# =====================================================================

@router.post("/types", response_model=schemas.TypeTitreResponse, status_code=status.HTTP_201_CREATED)
def creer_type_titre(
    payload: schemas.TypeTitreCreate, 
    db: Session = Depends(get_db), 
    current_user = Depends(allow_admin)
):
    """Crée un nouveau type de titre minier."""
    existe = db.query(models.TypeTitre).filter(models.TypeTitre.libtyptit.ilike(payload.libtyptit)).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ce type de titre existe déjà.")
    
    nouveau_type = models.TypeTitre(libtyptit=payload.libtyptit)
    db.add(nouveau_type)
    db.commit()
    db.refresh(nouveau_type)
    return nouveau_type


@router.get("/types", response_model=List[schemas.TypeTitreResponse])
def lister_types_titre(db: Session = Depends(get_db), current_user = Depends(allow_admin)):
    """Récupère tous les types de titres pour alimenter les listes déroulantes de Flutter."""
    return db.query(models.TypeTitre).all()


@router.patch("/types/{codtyptit}", response_model=schemas.TypeTitreResponse)
def modifier_type_titre(codtyptit: int, payload: schemas.TypeTitreCreate, db: Session = Depends(get_db), current_user = Depends(allow_admin)):
    db_type = db.query(models.TypeTitre).filter(models.TypeTitre.codtyptit == codtyptit).first()
    if not db_type:
        raise HTTPException(status_code=404, detail="Type de titre introuvable.")
    
    db_type.libtyptit = payload.libtyptit
    db.commit()
    db.refresh(db_type)
    return db_type


@router.delete("/types/{codtyptit}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_type_titre(codtyptit: int, db: Session = Depends(get_db), current_user = Depends(allow_admin)):
    db_type = db.query(models.TypeTitre).filter(models.TypeTitre.codtyptit == codtyptit).first()
    if not db_type:
        raise HTTPException(status_code=404, detail="Type de titre introuvable.")
        
    titres_lies = db.query(models.TitreMinier).filter(models.TitreMinier.codtyptit == codtyptit).first()
    if titres_lies:
        raise HTTPException(status_code=400, detail="Suppression impossible : ce type est lié à des titres existants.")
        
    db.delete(db_type)
    db.commit()
    return None


# =====================================================================
# 1. ENREGISTREMENT / CRÉATION DIRECTE (POST)
# =====================================================================
@router.post("/", response_model=schemas.TitreMinierResponse, status_code=status.HTTP_201_CREATED)
def creer_titre_minier(
    payload: schemas.TitreMinierCreate, 
    db: Session = Depends(get_db), 
    current_user = Depends(allow_directeur)
):
    """
    Permet d'enregistrer manuellement un titre minier (ex: titres historiques ou préexistants).
    """
    
    # Vérifier l'unicité du numéro d'arrêté
    existe = db.query(models.TitreMinier).filter(models.TitreMinier.naretag == payload.naretag).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ce numéro d'arrêté de titre existe déjà.")
    
    # Vérification de l'existence des clés étrangères de référence
    etat = db.query(models.EtatTitre).filter(models.EtatTitre.codetattit == payload.codetattit).first()
    ttype = db.query(models.TypeTitre).filter(models.TypeTitre.codtyptit == payload.codtyptit).first()
    if not etat or not ttype:
        raise HTTPException(status_code=400, detail="L'état ou le type de titre spécifié n'existe pas.")

    nouveau_titre = models.TitreMinier(**payload.model_dump())
    db.add(nouveau_titre)
    db.commit()
    db.refresh(nouveau_titre)
    return nouveau_titre


# =====================================================================
# 2. RECHERCHE MULTI-CRITÈRES & LISTING (GET)
# =====================================================================
@router.get("/", response_model=List[schemas.TitreMinierDetailResponse])
def lister_et_rechercher_titres(
    db: Session = Depends(get_db),
    type_id: Optional[int] = Query(None, description="Filtrer par type (PE, PR...)"),
    etat_id: Optional[int] = Query(None, description="Filtrer par état (Renouvelé, Déchu...)"),
    recherche: Optional[str] = Query(None, description="Recherche par N° Arrêté, code ou nom de l'entreprise"),
    current_user = Depends(allow_all)
):
    """
    Endpoint de recherche global pour alimenter les tableaux de bord et filtres de recherche Flutter.
    """
    
    query = db.query(
        models.TitreMinier.naretag,
        models.TitreMinier.ndocetudfai,
        models.TitreMinier.ndocimpenv,
        models.TitreMinier.datoctroitit,
        models.TitreMinier.datfinval,
        models.TitreMinier.demande_num,
        models.TitreMinier.codetattit,
        models.TitreMinier.codtyptit,
        models.EtatTitre.libetattit.label("lib_etat"),
        models.TypeTitre.libtyptit.label("lib_type"),
        models.Entreprise.code.label("code_entreprise"),
        models.Entreprise.nomenclature.label("nom_entreprise")
    ).join(models.EtatTitre, models.TitreMinier.codetattit == models.EtatTitre.codetattit)\
     .join(models.TypeTitre, models.TitreMinier.codtyptit == models.TypeTitre.codtyptit)\
     .outerjoin(models.Demande, models.TitreMinier.demande_num == models.Demande.numdem)\
     .outerjoin(models.Entreprise, models.Demande.entreprise_code == models.Entreprise.code)

    if type_id:
        query = query.filter(models.TitreMinier.codtyptit == type_id)
    if etat_id:
        query = query.filter(models.TitreMinier.codetattit == etat_id)
    if recherche:
        query = query.filter(
            (models.TitreMinier.naretag.ilike(f"%{recherche}%")) | 
            (models.Entreprise.codent.ilike(f"%{recherche}%")) |
            (models.Entreprise.noment.ilike(f"%{recherche}%"))
        )

    return query.all()


# =====================================================================
# 3. CONSULTATION PAR ID / N° ARRÊTÉ (GET BY ID)
# =====================================================================
@router.get("/{naretag}", response_model=schemas.TitreMinierDetailResponse)
def obtenir_titre_par_arrete(naretag: str, db: Session = Depends(get_db), current_user = Depends(allow_all)):
    """
    Récupère la fiche complète d'un titre minier via son numéro d'arrêté unique.
    """
    titre = db.query(
        models.TitreMinier.naretag,
        models.TitreMinier.ndocetudfai,
        models.TitreMinier.ndocimpenv,
        models.TitreMinier.datoctroitit,
        models.TitreMinier.datfinval,
        models.TitreMinier.demande_num,
        models.TitreMinier.codetattit,
        models.TitreMinier.codtyptit,
        models.EtatTitre.libetattit.label("lib_etat"),
        models.TypeTitre.libtyptit.label("lib_type"),
        models.Entreprise.code.label("code_entreprise"),
        models.Entreprise.nomenclature.label("nom_entreprise")
    ).join(models.EtatTitre, models.TitreMinier.codetattit == models.EtatTitre.codetattit)\
     .join(models.TypeTitre, models.TitreMinier.codtyptit == models.TypeTitre.codtyptit)\
     .outerjoin(models.Demande, models.TitreMinier.demande_num == models.Demande.numdem)\
     .outerjoin(models.Entreprise, models.Demande.entreprise_code == models.Entreprise.code)\
     .filter(models.TitreMinier.naretag == naretag).first()

    if not titre:
        raise HTTPException(status_code=404, detail="Titre minier introuvable.")
    return titre


# =====================================================================
# 4. MODIFICATION PARTIELLE / TECHNIQUE (PATCH)
# =====================================================================
@router.patch("/{naretag}", response_model=schemas.TitreMinierResponse)
def modifier_titre_minier(
    naretag: str, 
    payload: schemas.TitreMinierUpdate, 
    db: Session = Depends(get_db), 
    current_user = Depends(allow_directeur)
):
    """
    Permet de corriger des données sur le titre (correction de dates, changement de références de documents).
    """
    db_titre = db.query(models.TitreMinier).filter(models.TitreMinier.naretag == naretag).first()
    if not db_titre:
        raise HTTPException(status_code=404, detail="Titre minier introuvable.")

    # Application dynamique des modifications fournies dans le JSON
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_titre, key, value)

    db.commit()
    db.refresh(db_titre)
    return db_titre


# =====================================================================
# 5. ENDPOINT MÉTIER : ACTION ADMINISTRATIVE DE SÉCURITÉ (CHANGER ÉTAT)
# =====================================================================
@router.patch("/{naretag}/changer-etat", status_code=status.HTTP_200_OK)
def forcer_changement_etat_titre(
    naretag: str, 
    nouveau_codetat: int = Query(..., description="ID du nouvel état à appliquer"), 
    db: Session = Depends(get_db), 
    current_user = Depends(allow_admin) # 🛡️ Uniquement l'administrateur système (IT)
):
    """
    Endpoint de coercition : Permet de déclarer un titre manuellement comme 'Déchu', 'Suspendu' ou 'Refusé'
    à la suite d'une décision administrative ou juridique, en dehors du workflow classique.
    """
    db_titre = db.query(models.TitreMinier).filter(models.TitreMinier.naretag == naretag).first()
    if not db_titre:
        raise HTTPException(status_code=404, detail="Titre minier introuvable.")

    etat_existe = db.query(models.EtatTitre).filter(models.EtatTitre.codetattit == nouveau_codetat).first()
    if not etat_existe:
        raise HTTPException(status_code=400, detail="Le code d'état spécifié n'existe pas dans le référentiel.")

    db_titre.codetattit = nouveau_codetat
    db.commit()
    return {"message": f"Le titre {naretag} a été modifié avec succès. Nouvel état : {etat_existe.libetattit}"}


# =====================================================================
# 6. SUPPRESSION DÉFINITIVE (DELETE)
# =====================================================================
@router.delete("/{naretag}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_titre_minier(naretag: str, db: Session = Depends(get_db), current_user = Depends(allow_admin)):
    """
    Supprime définitivement un enregistrement de titre minier (réservé aux corrections d'erreurs lourdes).
    """
    db_titre = db.query(models.TitreMinier).filter(models.TitreMinier.naretag == naretag).first()
    if not db_titre:
        raise HTTPException(status_code=404, detail="Titre minier introuvable.")
        
    db.delete(db_titre)
    db.commit()
    return None