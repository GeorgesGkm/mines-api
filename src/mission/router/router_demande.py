from datetime import datetime
import math
import random
import string

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import not_
import os
from src.core.database import get_db
from src.mission import models, schemas
from src.auth.dependencies import allow_all

router = APIRouter(
    prefix="/demandes",
    tags=["Dépôt et Suivi des Demandes"]
)

# Dossier où seront stockés les PDF sur le serveur
UPLOAD_DIR = "static/documents_titres"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def generer_numero_demande_unique(db: Session) -> str:
    """
    Génère un numéro au format MINE-XXXX (ex: MINE-4829)
    et vérifie en BDD qu'il n'existe pas encore pour éviter les doublons.
    """
    while True:
        # Génère 4 chiffres aléatoires sous forme de chaîne
        chiffres = "".join(random.choices(string.digits, k=4))
        num_potentiel = f"MINE-{chiffres}"
        
        # Vérification d'unicité dans la table Demande
        existe = db.query(models.Demande).filter(models.Demande.numdem == num_potentiel).first()
        if not existe:
            return num_potentiel


#créer nouvelle demande
@router.post("/", response_model=schemas.DemandeResponse, status_code=status.HTTP_201_CREATED)
async def introduire_nouvelle_demande(
    entreprise_code: str = Form(..., description="Code unique de l'entreprise"),
    arrete_agrement: UploadFile = File(...),
    etude_faisabilite: UploadFile = File(...),
    etude_impact: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    L'entreprise introduit sa demande. 
    """
    # 1. Vérifier si l'entreprise existe
    entreprise = db.query(models.Entreprise).filter(models.Entreprise.code == entreprise_code).first()
    if not entreprise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"L'entreprise avec le code {entreprise_code} n'existe pas."
        )
    
    demande_active = db.query(models.Demande).filter(
        models.Demande.entreprise_code == entreprise_code,
        not_(models.Demande.statut.in_([
            models.StatutInstruction.REJETE, 
            models.StatutInstruction.VALIDE
        ]))
    ).first()

    if demande_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Dépôt impossible. Cette entreprise possède déjà une demande en cours d'instruction "
                f"({demande_active.numdem}) au statut actuel : '{demande_active.statut.value}'. "
                f"Le dossier doit être finalisé ou rejeté avant d'introduire une nouvelle demande."
            )
        )

    # 2. GÉNÉRATION AUTOMATIQUE DU NUMÉRO DE DEMANDE UNIQUE ───
    numdem = generer_numero_demande_unique(db)

    # 3. Création de la demande au statut initial DEPOT
    nouvelle_demande = models.Demande(
        numdem=numdem,
        entreprise_code=entreprise_code,
        statut=models.StatutInstruction.DEPOT
    )
    db.add(nouvelle_demande)
    db.flush() 

    # 4. Sauvegarde des 3 fichiers PDF avec le nouveau numéro généré
    fichiers_a_traiter = {
        "AGREMENT": arrete_agrement,
        "ETUDE_FAISABILITE": etude_faisabilite,
        "ETUDE_IMPACT": etude_impact
    }

    for type_cle, file_obj in fichiers_a_traiter.items():
        extension = os.path.splitext(file_obj.filename)[1].lower()
        if extension != ".pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le fichier pour {type_cle} doit être un PDF."
            )

        # Le nom du fichier sur le serveur utilisera le format : MINE-XXXX_AGREMENT.pdf
        nom_unique_fichier = f"{numdem}_{type_cle}{extension}"
        chemin_local = os.path.join(UPLOAD_DIR, nom_unique_fichier)

        # On force la conversion des antislashe Windows (\) en slashes Web (/)
        chemin_stockage_final = chemin_local.replace("\\", "/")
        
        with open(chemin_stockage_final, "wb") as buffer:
            buffer.write(await file_obj.read())

        # Enregistrement du document en BDD
        nouveau_doc = models.DocumentScanne(
            demande_num=numdem,
            type_fichier=type_cle,
            nom_fichier=file_obj.filename,
            chemin_stockage=chemin_stockage_final
        )
        db.add(nouveau_doc)

    
    db.commit()
    db.refresh(nouvelle_demande)
    return nouvelle_demande


@router.get("/{numdem}", response_model=schemas.DemandeResponse)
def obtenir_details_demande(numdem: str, db: Session = Depends(get_db), current_user = Depends(allow_all)):
    """
    Retourne la demande avec l'état précis de tous les avis (Province, Direction des mines) 
    ainsi que la liste des fichiers qui y sont attachés.
    """
    demande = db.query(models.Demande).filter(models.Demande.numdem == numdem).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande de renouvellement introuvable.")
    return demande

@router.get("/", response_model=schemas.DemandePaginatedResponse)
def lister_toutes_les_demandes(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Numéro de la page (commence à 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Nombre d'éléments par page (max 100)"),
    current_user = Depends(allow_all)
):
    """
    Récupère la liste de toutes les demandes d'instruction avec un système 
    de pagination.
    """
    # 1. Base de la requête SQL
    query = db.query(models.Demande)
    
    # 2. Calcul du nombre total d'éléments (Avant application de la limite de page)
    total_items = query.count()
    
    # 3. Calcul de l'index de départ (Offset)
    offset = (page - 1) * page_size
    
    # 4. Exécution de la requête avec la découpe SQL (Limit / Offset)
    demandes = query.order_by(models.Demande.datdem.desc())\
                    .offset(offset)\
                    .limit(page_size)\
                    .all()
                    
    # 5. Calcul du nombre total de pages
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1

    # 6. Retour de la structure paginée complète
    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "results": demandes
    }


@router.patch("/{numdem}", response_model=schemas.DemandeResponse)
def modifier_element_demande(
    numdem: str,
    payload: schemas.DemandeUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(allow_all) # 🛡️ Accès restreint aux gestionnaires
):
    """
    Permet de modifier dynamiquement n'importe quel attribut modifiable d'une demande 
    (Statut, Avis des entités, ou Code de l'entreprise associée).
    """
    # 1. Recherche de la demande existante
    db_demande = db.query(models.Demande).filter(models.Demande.numdem == numdem).first()
    if not db_demande:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La demande de renouvellement {numdem} n'existe pas."
        )

    # 2. Si le code entreprise est modifié, on vérifie que la nouvelle entreprise existe
    if payload.entreprise_code is not None:
        entreprise_existe = db.query(models.Entreprise).filter(models.Entreprise.codent == payload.entreprise_code).first()
        if not entreprise_existe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"L'entreprise avec le code {payload.entreprise_code} n'existe pas."
            )

    # 3. Extraction des données envoyées (ignore les champs absents du JSON)
    donnies_mises_a_jour = payload.model_dump(exclude_unset=True)
    
    if not donnies_mises_a_jour:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune donnée valide n'a été fournie pour la mise à jour."
        )

    # 4. Application dynamique des modifications sur l'objet SQL
    for clé, valeur in donnies_mises_a_jour.items():
        setattr(db_demande, clé, valeur)

    # 5. Validation en Base de données
    db.commit()
    db.refresh(db_demande)
    
    return db_demande


@router.patch("/{numdem}/avis-division-provinciale", response_model=schemas.DemandeResponse)
def valider_avis_division_provinciale(
    numdem: str, 
    avis: schemas.TypeAvis, 
    db: Session = Depends(get_db),
    current_user = Depends(allow_all)
):
    db_demande = db.query(models.Demande).filter(models.Demande.numdem == numdem).first()
    if not db_demande or db_demande.statut != models.StatutInstruction.ANALYSE_PROVINCIALE:
        raise HTTPException(status_code=400, detail="Cette demande n'est pas au niveau de la Division Provinciale.")

    db_demande.avis_division_provinciale = avis
    db_demande.date_avis_div_prov = datetime.utcnow()

    if avis == models.TypeAvis.FAVORABLE:
        # Le dossier passe mécaniquement à l'autorité supérieure : le Ministre Provincial
        db_demande.statut = models.StatutInstruction.ANALYSE_MINISTRE_PROV
    else:
        db_demande.statut = models.StatutInstruction.REJETE

    db.commit()
    db.refresh(db_demande)
    return db_demande


@router.patch("/{numdem}/avis-ministre-provincial", response_model=schemas.DemandeResponse)
def valider_avis_ministre_provincial(
    numdem: str, 
    avis: schemas.TypeAvis, 
    db: Session = Depends(get_db),
    current_user = Depends(allow_all)
):
    db_demande = db.query(models.Demande).filter(models.Demande.numdem == numdem).first()
    if not db_demande or db_demande.statut != models.StatutInstruction.ANALYSE_MINISTRE_PROV:
        raise HTTPException(status_code=400, detail="Cette demande n'est pas au niveau du Cabinet du Ministre Provincial.")

    db_demande.avis_ministre_provincial = avis
    db_demande.date_avis_min_prov = datetime.utcnow()

    if avis == models.TypeAvis.FAVORABLE:
        # Le dossier remonte maintenant au niveau national : la Direction des Mines
        db_demande.statut = models.StatutInstruction.ANALYSE_DIRECTION_MINES
    else:
        db_demande.statut = models.StatutInstruction.REJETE

    db.commit()
    db.refresh(db_demande)
    return db_demande


@router.patch("/{numdem}/avis-direction-mines", response_model=schemas.DemandeResponse)
def valider_avis_direction_mines(
    numdem: str, 
    avis: schemas.TypeAvis, 
    db: Session = Depends(get_db),
    current_user = Depends(allow_all) 
):
    db_demande = db.query(models.Demande).filter(models.Demande.numdem == numdem).first()
    if not db_demande or db_demande.statut != models.StatutInstruction.ANALYSE_DIRECTION_MINES:
        raise HTTPException(status_code=400, detail="Cette demande n'est pas au niveau de la Direction des Mines Nationale.")

    db_demande.avis_direction_mines = avis
    db_demande.date_avis_dir_mines = datetime.utcnow()

    if avis == models.TypeAvis.FAVORABLE:
        # Le flux est validé avec succès
        db_demande.statut = models.StatutInstruction.VALIDE
    else:
        db_demande.statut = models.StatutInstruction.REJETE

    db.commit()
    db.refresh(db_demande)
    return db_demande